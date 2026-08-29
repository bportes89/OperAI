"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { apiJson } from "../../lib/api";
import {
  CAMPAIGN_STATUS_LABELS,
  CAMPAIGN_TRANSITIONS,
  type Campaign,
  type MarketingPlaybook,
} from "../../lib/types";

const WIZARD_STEPS = [
  { key: "diagnosis", label: "1. Diagnóstico" },
  { key: "discovery", label: "2. Descoberta" },
  { key: "plan", label: "3. Plano" },
  { key: "active", label: "4. Peças" },
] as const;

function stepIndex(step: string) {
  const i = WIZARD_STEPS.findIndex((s) => s.key === step);
  return i < 0 ? 0 : i;
}

export default function MarketingPage() {
  const [playbook, setPlaybook] = useState<MarketingPlaybook | null>(null);
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [view, setView] = useState<"wizard" | "campaigns">("wizard");

  const load = useCallback(async () => {
    try {
      setError("");
      const [pb, cams] = await Promise.all([
        apiJson<MarketingPlaybook>("/api/v1/marketing/playbook"),
        apiJson<Campaign[]>("/api/v1/marketing/campaigns"),
      ]);
      setPlaybook(pb);
      setCampaigns(cams);
      if (pb.step === "active" && (pb.posts?.length ?? 0) > 0) {
        setView("wizard");
      }
    } catch (e) {
      setError((e as Error).message);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function saveDiagnosis(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    const data = Object.fromEntries(new FormData(event.currentTarget));
    try {
      const pb = await apiJson<MarketingPlaybook>(
        "/api/v1/marketing/playbook/diagnosis",
        { method: "PUT", body: JSON.stringify(data) },
      );
      setPlaybook(pb);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function saveDiscovery(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    const data = Object.fromEntries(new FormData(event.currentTarget));
    try {
      const pb = await apiJson<MarketingPlaybook>(
        "/api/v1/marketing/playbook/discovery",
        { method: "PUT", body: JSON.stringify(data) },
      );
      setPlaybook(pb);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function generatePlan() {
    setBusy(true);
    setError("");
    try {
      const pb = await apiJson<MarketingPlaybook>(
        "/api/v1/marketing/playbook/generate",
        { method: "POST", body: "{}" },
      );
      setPlaybook(pb);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function materializePosts() {
    setBusy(true);
    setError("");
    try {
      await apiJson("/api/v1/marketing/playbook/materialize", {
        method: "POST",
        body: "{}",
      });
      await load();
      setView("campaigns");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function createCampaign(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    const form = event.currentTarget;
    const data = Object.fromEntries(new FormData(form));
    try {
      await apiJson("/api/v1/marketing/campaigns", {
        method: "POST",
        body: JSON.stringify({
          name: data.name,
          channel: data.channel,
          audience: data.audience,
          content: data.content,
        }),
      });
      form.reset();
      await load();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function campaignStatus(item: Campaign, status: string) {
    try {
      await apiJson(`/api/v1/marketing/campaigns/${item.id}/status`, {
        method: "PATCH",
        body: JSON.stringify({ status }),
      });
      await load();
    } catch (e) {
      setError((e as Error).message);
    }
  }

  const step = playbook?.step ?? "diagnosis";
  const current = stepIndex(step);
  const d = playbook?.diagnosis ?? {};
  const disc = playbook?.discovery ?? {};

  return (
    <>
      <header>
        <div>
          <span>CRESCIMENTO</span>
          <h1>Marketing</h1>
        </div>
        <div className="proposal-actions">
          <button
            type="button"
            className={view === "wizard" ? "primary" : undefined}
            onClick={() => setView("wizard")}
          >
            Pacote Essencial
          </button>
          <button
            type="button"
            className={view === "campaigns" ? "primary" : undefined}
            onClick={() => setView("campaigns")}
          >
            Campanhas
          </button>
        </div>
      </header>
      {error && <p className="error">{error}</p>}

      {view === "wizard" && (
        <>
          <article className="panel" style={{ marginBottom: 16 }}>
            <div className="panel-title">
              <div>
                <span>AGENTE GESTOR</span>
                <h2>Essencial — diagnóstico antes de produzir</h2>
              </div>
            </div>
            <p style={{ marginTop: 0, opacity: 0.8 }}>
              Gestor + Redação + Mídias sociais. Começa entendendo o negócio;
              só depois gera plano e peças com CTA.
            </p>
            <div className="proposal-actions" style={{ flexWrap: "wrap" }}>
              {WIZARD_STEPS.map((s, i) => (
                <span
                  key={s.key}
                  className={`finance-status ${i <= current ? "paid" : "pending"}`}
                >
                  {s.label}
                </span>
              ))}
            </div>
          </article>

          {step === "diagnosis" && (
            <article className="panel">
              <div className="panel-title">
                <div>
                  <span>AS IS</span>
                  <h2>Diagnóstico inicial</h2>
                </div>
              </div>
              <form onSubmit={saveDiagnosis}>
                <label>
                  Canais ativos hoje
                  <textarea
                    name="channels_active"
                    required
                    minLength={2}
                    defaultValue={d.channels_active}
                    placeholder="Instagram, WhatsApp Status, site…"
                  />
                </label>
                <label>
                  Tipo de conteúdo publicado
                  <textarea
                    name="content_types"
                    required
                    minLength={2}
                    defaultValue={d.content_types}
                    placeholder="Posts institucionais, bastidores, ofertas…"
                  />
                </label>
                <label>
                  Frequência
                  <input
                    name="frequency"
                    required
                    minLength={2}
                    defaultValue={d.frequency}
                    placeholder="Ex.: 3x por semana"
                  />
                </label>
                <label>
                  Dados de engajamento (mesmo que superficiais)
                  <textarea
                    name="engagement_notes"
                    defaultValue={d.engagement_notes}
                    placeholder="Curtidas, alcance, comentários, horários…"
                  />
                </label>
                <label>
                  Materiais de marca já existentes
                  <textarea
                    name="brand_assets"
                    defaultValue={d.brand_assets}
                    placeholder="Logo, textos institucionais, identidade…"
                  />
                </label>
                <label>
                  Resultados comerciais já vindos do marketing
                  <textarea
                    name="commercial_results"
                    defaultValue={d.commercial_results}
                    placeholder="Leads, vendas, ou 'ainda não medimos'"
                  />
                </label>
                <button className="primary" disabled={busy}>
                  Salvar e ir à descoberta
                </button>
              </form>
            </article>
          )}

          {step === "discovery" && (
            <article className="panel">
              <div className="panel-title">
                <div>
                  <span>TO BE</span>
                  <h2>Descoberta estratégica</h2>
                </div>
              </div>
              <form onSubmit={saveDiscovery}>
                <label>
                  Concorrentes diretos
                  <textarea
                    name="competitors"
                    required
                    minLength={2}
                    defaultValue={disc.competitors}
                  />
                </label>
                <label>
                  O que diferencia esta empresa
                  <textarea
                    name="differentiators"
                    required
                    minLength={2}
                    defaultValue={disc.differentiators}
                  />
                </label>
                <label>
                  Cliente ideal e onde ele está
                  <textarea
                    name="ideal_customer"
                    required
                    minLength={2}
                    defaultValue={disc.ideal_customer}
                  />
                </label>
                <label>
                  Missão, visão e valores (pelo que quer ser conhecida)
                  <textarea
                    name="mission_values"
                    required
                    minLength={2}
                    defaultValue={disc.mission_values}
                  />
                </label>
                <label>
                  O que a marca NÃO deve parecer
                  <textarea
                    name="brand_avoid"
                    defaultValue={disc.brand_avoid}
                  />
                </label>
                <label>
                  Capacidade real de atendimento de leads
                  <input
                    name="lead_capacity"
                    required
                    minLength={1}
                    defaultValue={disc.lead_capacity}
                    placeholder="Ex.: 10 conversas/semana"
                  />
                </label>
                <label>
                  Sazonalidade
                  <input
                    name="seasonality"
                    defaultValue={disc.seasonality}
                    placeholder="Ex.: pico no 4º trimestre"
                  />
                </label>
                <label>
                  Orçamento mensal de marketing
                  <input
                    name="monthly_budget"
                    required
                    minLength={1}
                    defaultValue={disc.monthly_budget}
                    placeholder="Ex.: R$ 0 (só orgânico) / R$ 500"
                  />
                </label>
                <button className="primary" disabled={busy}>
                  Salvar e gerar plano
                </button>
              </form>
            </article>
          )}

          {(step === "plan" || step === "active") && (
            <div className="content-grid">
              <article className="panel">
                <div className="panel-title">
                  <div>
                    <span>PLANO</span>
                    <h2>Ação priorizada (30 dias)</h2>
                  </div>
                </div>
                {!playbook?.action_plan ? (
                  <>
                    <p>
                      Diagnóstico e descoberta prontos. O Agente Gestor vai
                      cruzar orçamento, capacidade e canais para propor o plano.
                    </p>
                    <button
                      className="primary"
                      type="button"
                      disabled={busy}
                      onClick={() => void generatePlan()}
                    >
                      {busy ? "Gerando…" : "Gerar plano Essencial"}
                    </button>
                  </>
                ) : (
                  <>
                    {playbook.diagnosis_summary && (
                      <>
                        <strong>Resumo as-is</strong>
                        <p style={{ whiteSpace: "pre-wrap" }}>
                          {playbook.diagnosis_summary}
                        </p>
                      </>
                    )}
                    <strong>Plano</strong>
                    <p style={{ whiteSpace: "pre-wrap" }}>
                      {playbook.action_plan}
                    </p>
                    <button
                      type="button"
                      disabled={busy}
                      onClick={() => void generatePlan()}
                    >
                      Regenerar plano
                    </button>
                  </>
                )}
              </article>

              <article className="panel">
                <div className="panel-title">
                  <div>
                    <span>REDAÇÃO + MÍDIAS</span>
                    <h2>Peças com CTA</h2>
                  </div>
                </div>
                {(playbook?.posts?.length ?? 0) === 0 ? (
                  <div className="empty">
                    <strong>Aguardando plano</strong>
                    <p>As 4 peças aparecem após gerar o plano.</p>
                  </div>
                ) : (
                  <>
                    {playbook!.posts.map((post, idx) => (
                      <div className="campaign-card" key={`${post.title}-${idx}`}>
                        <div>
                          <strong>{post.title}</strong>
                          <small>
                            {post.channel} · {post.audience}
                          </small>
                        </div>
                        <p>{post.content}</p>
                      </div>
                    ))}
                    <button
                      className="primary"
                      type="button"
                      disabled={busy}
                      onClick={() => void materializePosts()}
                    >
                      Criar campanhas em rascunho
                    </button>
                  </>
                )}
              </article>
            </div>
          )}
        </>
      )}

      {view === "campaigns" && (
        <div className="content-grid">
          <article className="panel">
            <div className="panel-title">
              <div>
                <span>CAMPANHAS</span>
                <h2>Ações multicanal</h2>
              </div>
            </div>
            {campaigns.length === 0 ? (
              <div className="empty">
                <strong>Nenhuma campanha</strong>
                <p>
                  Conclua o pacote Essencial ou planeje uma ação manual abaixo.
                </p>
              </div>
            ) : (
              campaigns.map((item) => (
                <div className="campaign-card" key={item.id}>
                  <div>
                    <strong>{item.name}</strong>
                    <small>
                      {item.channel} · {item.audience}
                    </small>
                  </div>
                  <span className={`finance-status ${item.status}`}>
                    {item.status}
                  </span>
                  <p>{item.content}</p>
                  <div className="campaign-metrics">
                    <span>{item.sent_count} enviados</span>
                    <span>{item.delivered_count} entregues</span>
                    <span>{item.response_count} respostas</span>
                  </div>
                  <div className="proposal-actions">
                    {(CAMPAIGN_TRANSITIONS[item.status] ?? []).map((next) => (
                      <button
                        key={next}
                        type="button"
                        onClick={() => void campaignStatus(item, next)}
                      >
                        {CAMPAIGN_STATUS_LABELS[next] ?? next}
                      </button>
                    ))}
                  </div>
                </div>
              ))
            )}
          </article>

          <article className="panel">
            <div className="panel-title">
              <div>
                <span>NOVA</span>
                <h2>Planejar ação manual</h2>
              </div>
            </div>
            <form onSubmit={createCampaign}>
              <label>
                Nome
                <input name="name" required minLength={2} />
              </label>
              <label>
                Canal
                <select name="channel" defaultValue="whatsapp">
                  <option value="whatsapp">WhatsApp</option>
                  <option value="email">E-mail</option>
                  <option value="social">Redes sociais</option>
                </select>
              </label>
              <label>
                Público
                <input
                  name="audience"
                  required
                  minLength={2}
                  placeholder="Ex.: leads qualificados"
                />
              </label>
              <label>
                Conteúdo
                <textarea name="content" required minLength={5} />
              </label>
              <button className="primary" disabled={busy}>
                Criar campanha
              </button>
            </form>
          </article>
        </div>
      )}
    </>
  );
}
