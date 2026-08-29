"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { apiJson } from "../lib/api";
import { formatDateTime, money } from "../lib/format";
import type { Activity, Analytics } from "../lib/types";

function BarChart({
  items,
  valueKey,
  labelKey,
  formatValue,
  color = "#3d7a5f",
}: {
  items: Record<string, string | number>[];
  valueKey: string;
  labelKey: string;
  formatValue?: (n: number) => string;
  color?: string;
}) {
  const max = Math.max(1, ...items.map((i) => Number(i[valueKey]) || 0));
  return (
    <div className="dash-bars">
      {items.map((item) => {
        const value = Number(item[valueKey]) || 0;
        const pct = Math.round((value / max) * 100);
        return (
          <div className="dash-bar-row" key={String(item[labelKey])}>
            <span className="dash-bar-label">{String(item[labelKey])}</span>
            <div className="dash-bar-track">
              <div
                className="dash-bar-fill"
                style={{ width: `${pct}%`, background: color }}
              />
            </div>
            <strong className="dash-bar-value">
              {formatValue ? formatValue(value) : value}
            </strong>
          </div>
        );
      })}
    </div>
  );
}

function SparkBars({ series }: { series: { date: string; count: number }[] }) {
  const max = Math.max(1, ...series.map((s) => s.count));
  return (
    <div className="dash-spark" aria-label="Atividade dos últimos 7 dias">
      {series.map((s) => {
        const h = Math.max(8, Math.round((s.count / max) * 72));
        const day = s.date.slice(8); // DD
        return (
          <div className="dash-spark-col" key={s.date} title={`${s.date}: ${s.count}`}>
            <div className="dash-spark-bar" style={{ height: h }} />
            <span>{day}</span>
            <small>{s.count}</small>
          </div>
        );
      })}
    </div>
  );
}

export default function DashboardPage() {
  const [analytics, setAnalytics] = useState<Analytics | null>(null);
  const [activity, setActivity] = useState<Activity[]>([]);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    try {
      setError("");
      const [overview, acts] = await Promise.all([
        apiJson<Analytics>("/api/v1/analytics/overview"),
        apiJson<Activity[]>("/api/v1/analytics/activity"),
      ]);
      setAnalytics(overview);
      setActivity(acts);
    } catch (e) {
      setError((e as Error).message);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const charts = analytics?.charts;
  const hasFunnel = useMemo(
    () => (charts?.crm_funnel ?? []).some((x) => x.count > 0),
    [charts],
  );
  const hasFinance = useMemo(
    () => (charts?.finance_mix ?? []).some((x) => x.cents > 0),
    [charts],
  );
  const hasSpark = useMemo(
    () => (charts?.activity_7d ?? []).some((x) => x.count > 0),
    [charts],
  );

  return (
    <>
      <header>
        <div>
          <span>OPERAÇÃO</span>
          <h1>Visão geral</h1>
        </div>
        <div className="online">● Sistema online</div>
      </header>
      {error && <p className="error">{error}</p>}

      {analytics ? (
        <div className="metrics">
          <article>
            <span>Pipeline comercial</span>
            <strong>{money(analytics.crm.pipeline_cents)}</strong>
            <small>{analytics.crm.opportunities} oportunidades no CRM</small>
          </article>
          <article>
            <span>Agentes ativos</span>
            <strong>{analytics.operations.active_agents}</strong>
            <small>
              {analytics.operations.open_threads} conversas abertas no WhatsApp
            </small>
          </article>
          <article>
            <span>Em atraso</span>
            <strong>{money(analytics.finance.overdue_cents)}</strong>
            <small>{money(analytics.finance.pending_cents)} ainda em aberto</small>
          </article>
        </div>
      ) : (
        !error && <div className="empty">Carregando indicadores…</div>
      )}

      {analytics && (hasFunnel || hasSpark) && (
        <div className="executive-grid" style={{ marginTop: 18 }}>
          <article className="panel">
            <div className="panel-title">
              <div>
                <span>CRM</span>
                <h2>Funil de oportunidades</h2>
              </div>
            </div>
            {hasFunnel ? (
              <BarChart
                items={charts!.crm_funnel}
                valueKey="count"
                labelKey="label"
                color="#3d7a5f"
              />
            ) : (
              <div className="empty">
                <strong>Funil ainda vazio</strong>
                <p>Cadastre oportunidades no CRM para ver o funil.</p>
                <Link className="secondary" href="/app/crm">
                  Abrir CRM
                </Link>
              </div>
            )}
          </article>

          <article className="panel">
            <div className="panel-title">
              <div>
                <span>7 DIAS</span>
                <h2>Movimento da operação</h2>
              </div>
            </div>
            {hasSpark ? (
              <>
                <SparkBars series={charts!.activity_7d} />
                <p className="pricing-note" style={{ marginTop: 12 }}>
                  Contagem de eventos reais (agentes, cobrança, marketing,
                  WhatsApp…) — não é tráfego de site.
                </p>
              </>
            ) : (
              <div className="empty">
                <strong>Sem movimento ainda</strong>
                <p>Use agentes, CRM ou Marketing para gerar atividade.</p>
              </div>
            )}
          </article>
        </div>
      )}

      <div className="executive-grid">
        <article className="panel">
          <div className="panel-title">
            <div>
              <span>RESUMO</span>
              <h2>Indicadores</h2>
            </div>
            <button type="button" onClick={() => void load()}>
              Atualizar
            </button>
          </div>
          {analytics ? (
            <>
              <div className="kpi-list">
                <div>
                  <span>Negócios ganhos</span>
                  <strong>{analytics.crm.won}</strong>
                </div>
                <div>
                  <span>Mensagens não lidas</span>
                  <strong>{analytics.operations.unread_messages}</strong>
                </div>
                <div>
                  <span>Já recebido</span>
                  <strong>{money(analytics.finance.paid_cents)}</strong>
                </div>
                <div>
                  <span>Campanhas</span>
                  <strong>{analytics.operations.campaigns}</strong>
                </div>
                <div>
                  <span>Interesses de marketing (7d)</span>
                  <strong>{analytics.marketing?.interests_7d ?? 0}</strong>
                </div>
                <div>
                  <span>Leads virando CRM (7d)</span>
                  <strong>{analytics.marketing?.opportunities_7d ?? 0}</strong>
                </div>
              </div>
              {hasFinance && (
                <div style={{ marginTop: 18 }}>
                  <strong style={{ display: "block", marginBottom: 8 }}>
                    Cobrança — composição
                  </strong>
                  <BarChart
                    items={charts!.finance_mix}
                    valueKey="cents"
                    labelKey="label"
                    formatValue={(n) => money(n)}
                    color="#6b7c74"
                  />
                </div>
              )}
            </>
          ) : (
            <div className="empty">
              <strong>Sem dados ainda</strong>
              <p>Conclua o setup para ver a operação em movimento.</p>
              <Link className="primary" href="/app/onboarding">
                Ir ao setup
              </Link>
            </div>
          )}
        </article>

        <article className="panel">
          <div className="panel-title">
            <div>
              <span>LINHA DO TEMPO</span>
              <h2>O que aconteceu</h2>
            </div>
          </div>
          {activity.length === 0 ? (
            <div className="empty">
              <strong>Nenhuma atividade</strong>
              <p>Ative um agente ou conecte o WhatsApp para começar.</p>
              <Link className="secondary" href="/app/agents">
                Ver agentes
              </Link>
            </div>
          ) : (
            activity.slice(0, 12).map((item) => (
              <div className="activity-row" key={item.id}>
                <div className="activity-dot" />
                <div>
                  <strong>{item.title ?? item.action}</strong>
                  <small>{item.summary ?? item.detail ?? item.resource}</small>
                </div>
                <time dateTime={item.created_at}>
                  {formatDateTime(item.created_at)}
                </time>
              </div>
            ))
          )}
        </article>
      </div>
    </>
  );
}
