"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { apiJson } from "../lib/api";
import { formatDate, money } from "../lib/format";
import type { Activity, Analytics } from "../lib/types";

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
            <span>Pipeline</span>
            <strong>{money(analytics.crm.pipeline_cents)}</strong>
            <small>{analytics.crm.opportunities} oportunidades</small>
          </article>
          <article>
            <span>Agentes ativos</span>
            <strong>{analytics.operations.active_agents}</strong>
            <small>{analytics.operations.open_threads} threads abertas</small>
          </article>
          <article>
            <span>Em atraso</span>
            <strong>{money(analytics.finance.overdue_cents)}</strong>
            <small>{money(analytics.finance.pending_cents)} em aberto</small>
          </article>
        </div>
      ) : (
        !error && <div className="empty">Carregando indicadores...</div>
      )}

      <div className="executive-grid">
        <article className="panel">
          <div className="panel-title">
            <div>
              <span>BI</span>
              <h2>Indicadores</h2>
            </div>
            <button type="button" onClick={() => void load()}>
              Atualizar
            </button>
          </div>
          {analytics ? (
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
                <span>Recebido</span>
                <strong>{money(analytics.finance.paid_cents)}</strong>
              </div>
              <div>
                <span>Campanhas</span>
                <strong>{analytics.operations.campaigns}</strong>
              </div>
            </div>
          ) : (
            <div className="empty">
              <strong>Sem dados ainda</strong>
              <p>Conclua o onboarding para ver a operação em movimento.</p>
              <Link className="primary" href="/app/onboarding">
                Ir ao onboarding
              </Link>
            </div>
          )}
        </article>

        <article className="panel">
          <div className="panel-title">
            <div>
              <span>ATIVIDADE</span>
              <h2>Recentes</h2>
            </div>
          </div>
          {activity.length === 0 ? (
            <div className="empty">
              <strong>Nenhuma atividade</strong>
              <p>Crie um agente ou conecte o WhatsApp para começar.</p>
              <Link className="secondary" href="/app/agents">
                Ver agentes
              </Link>
            </div>
          ) : (
            activity.slice(0, 10).map((item) => (
              <div className="activity-row" key={item.id}>
                <div className="activity-dot" />
                <div>
                  <strong>{item.action}</strong>
                  <small>{item.detail || item.resource}</small>
                </div>
                <time>{formatDate(item.created_at)}</time>
              </div>
            ))
          )}
        </article>
      </div>
    </>
  );
}
