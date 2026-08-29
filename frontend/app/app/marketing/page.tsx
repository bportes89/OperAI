"use client";

import Link from "next/link";
import { FormEvent, useCallback, useEffect, useState } from "react";
import { apiJson } from "../../lib/api";
import {
  CAMPAIGN_STATUS_LABELS,
  CAMPAIGN_TRANSITIONS,
  type Campaign,
  type MarketingConversion,
  type MarketingLead,
  type MarketingPlaybook,
  type MarketingPost,
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
  const [leads, setLeads] = useState<MarketingLead[]>([]);
  const [conversion, setConversion] = useState<MarketingConversion | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [view, setView] = useState<"wizard" | "campaigns" | "conversion">(
    "wizard",
  );
  const [interestFor, setInterestFor] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setError("");
      const [pb, cams, leadRows, conv] = await Promise.all([
        apiJson<MarketingPlaybook>("/api/v1/marketing/playbook"),
        apiJson<Campaign[]>("/api/v1/marketing/campaigns"),
        apiJson<MarketingLead[]>("/api/v1/marketing/leads"),
        apiJson<MarketingConversion>("/api/v1/marketing/conversion"),
      ]);
      setPlaybook(pb);
      setCampaigns(cams);
      setLeads(leadRows);
      setConversion(conv);
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

  async function registerInterest(
    event: FormEvent<HTMLFormElement>,
    source: { title: string; channel: string; campaignId?: string },
  ) {
    event.preventDefault();
    setBusy(true);
    setError("");
    const form = event.currentTarget;
    const data = Object.fromEntries(new FormData(form));
    try {
      await apiJson("/api/v1/marketing/leads", {
        method: "POST",
        body: JSON.stringify({
          contact_name: data.contact_name,
          phone: data.phone || null,
          email: data.email || null,
          note: data.note || null,
          company: data.company || null,
          source_title: source.title,
          source_channel: source.channel,
          campaign_id: source.campaignId || null,
          value_cents: Math.round(Number(data.value || 0) * 100),
        }),
      });
      form.reset();
      setInterestFor(null);
      await load();
      setView("conversion");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  function interestForm(
    key: string,
    source: { title: string; channel: string; campaignId?: string },
  ) {
    if (interestFor !== key) {
      return (
        <button type="button" onClick={() => setInterestFor(key)}>
          Registrar interesse → CRM
        </button>
      );
    }
    return (
      <form
        onSubmit={(e) => void registerInterest(e, source)}
        style={{ display: "grid", gap: 8, marginTop: 8 }}
      >
        <label>
          Nome do interessado
          <input name="contact_name" required minLength={2} />
        </label>
        <label>
          Telefone (WhatsApp)
          <input name="phone" placeholder="11999999999" />
        </label>
        <label>
          E-mail
          <input name="email" type="email" />
        </label>
        <label>
          Empresa
          <input name="company" />
        </label>
        <label>
          Valor estimado (R$)
          <input name="value" type="number" min={0} step="0.01" defaultValue={0} />
        </label>
        <label>
          Nota / contexto do interesse
          <textarea name="note" placeholder="Comentou no post, pediu orçamento…" />
        </label>
        <div className="proposal-actions">
          <button className="primary" disabled={busy} type="submit">
            Criar lead e passar ao comercial
          </button>
          <button type="button" onClick={() => setInterestFor(null)}>
            Cancelar
          </button>
        </div>
      </form>
    );
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
          <button
            type="button"
            className={view === "conversion" ? "primary" : undefined}
            onClick={() => setView("conversion")}
          >
            Conversão
          </button>
        </div>
      </header>
      {error && <p className="error">{error}</p>}

      {conversion && (
        <div className="metrics">
          <article>
            <span>Interesses (7d)</span>
            <strong>{conversion.interests}</strong>
            <small>conteúdo → pessoa</small>
          </article>
          <article>
            <span>Leads com contato</span>
            <strong>{conversion.leads_with_contact}</strong>
            <small>telefone ou e-mail</small>
          </article>
          <article>
            <span>Oportunidades CRM</span>
            <strong>{conversion.opportunities}</strong>
            <small>handoff comercial</small>
          </article>
        </div>
      )}

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
              Gestor + Redação + Mídias. Depois do plano, registre interesse e o
              lead vai para o CRM.
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
                  />
                </label>
                <label>
                  Tipo de conteúdo publicado
                  <textarea
                    name="content_types"
                    required
                    minLength={2}
                    defaultValue={d.content_types}
                  />
                </label>
                <label>
                  Frequência
                  <input
                    name="frequency"
                    required
                    minLength={2}
                    defaultValue={d.frequency}
                  />
                </label>
                <label>
                  Dados de engajamento
                  <textarea
                    name="engagement_notes"
                    defaultValue={d.engagement_notes}
                  />
                </label>
                <label>
                  Materiais de marca
                  <textarea name="brand_assets" defaultValue={d.brand_assets} />
                </label>
                <label>
                  Resultados comerciais do marketing
                  <textarea
                    name="commercial_results"
                    defaultValue={d.commercial_results}
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
                  Diferencial
                  <textarea
                    name="differentiators"
                    required
                    minLength={2}
                    defaultValue={disc.differentiators}
                  />
                </label>
                <label>
                  Cliente ideal
                  <textarea
                    name="ideal_customer"
                    required
                    minLength={2}
                    defaultValue={disc.ideal_customer}
                  />
                </label>
                <label>
                  Missão, visão e valores
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
                  Capacidade de leads
                  <input
                    name="lead_capacity"
                    required
                    minLength={1}
                    defaultValue={disc.lead_capacity}
                  />
                </label>
                <label>
                  Sazonalidade
                  <input name="seasonality" defaultValue={disc.seasonality} />
                </label>
                <label>
                  Orçamento mensal
                  <input
                    name="monthly_budget"
                    required
                    minLength={1}
                    defaultValue={disc.monthly_budget}
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
                    <p>Diagnóstico e descoberta prontos. Gere o plano Essencial.</p>
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
                    {playbook!.posts.map((post: MarketingPost, idx: number) => (
                      <div className="campaign-card" key={`${post.title}-${idx}`}>
                        <div>
                          <strong>{post.title}</strong>
                          <small>
                            {post.channel} · {post.audience}
                          </small>
                        </div>
                        <p>{post.content}</p>
                        {interestForm(`post-${idx}`, {
                          title: post.title,
                          channel:
                            post.channel === "whatsapp" ||
                            post.channel === "email"
                              ? post.channel
                              : "social",
                        })}
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
                <p>Conclua o Essencial ou planeje uma ação manual.</p>
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
                  {interestForm(`camp-${item.id}`, {
                    title: item.name,
                    channel:
                      item.channel === "whatsapp" || item.channel === "email"
                        ? item.channel
                        : "social",
                    campaignId: item.id,
                  })}
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
                <input name="audience" required minLength={2} />
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

      {view === "conversion" && (
        <div className="content-grid">
          <article className="panel">
            <div className="panel-title">
              <div>
                <span>FUNIL</span>
                <h2>Conteúdo → interesse → CRM</h2>
              </div>
            </div>
            <p style={{ opacity: 0.85 }}>
              Cada interesse vira contato + oportunidade em estágio{" "}
              <strong>new</strong> e tarefa de handoff para o agente comercial
              ou WhatsApp.
            </p>
            <div className="proposal-actions">
              <Link href="/app/crm">Abrir CRM</Link>
              <Link href="/app/inbox">Abrir Inbox</Link>
            </div>
            {conversion && (
              <div className="campaign-metrics" style={{ marginTop: 16 }}>
                <span>Social: {conversion.by_channel.social}</span>
                <span>E-mail: {conversion.by_channel.email}</span>
                <span>WhatsApp: {conversion.by_channel.whatsapp}</span>
              </div>
            )}
          </article>

          <article className="panel">
            <div className="panel-title">
              <div>
                <span>LEADS</span>
                <h2>Interesses registrados</h2>
              </div>
            </div>
            {leads.length === 0 ? (
              <div className="empty">
                <strong>Nenhum interesse ainda</strong>
                <p>
                  Nas peças ou campanhas, use “Registrar interesse → CRM” quando
                  alguém engajar.
                </p>
              </div>
            ) : (
              leads.map((lead) => (
                <div className="campaign-card" key={lead.id}>
                  <div>
                    <strong>{lead.contact_name}</strong>
                    <small>
                      {lead.source_channel} · {lead.source_title}
                    </small>
                  </div>
                  <span className={`finance-status ${lead.status}`}>
                    {lead.status}
                  </span>
                  <p>
                    {[lead.phone, lead.email].filter(Boolean).join(" · ") ||
                      "Sem telefone/e-mail"}
                    {lead.note ? ` — ${lead.note}` : ""}
                  </p>
                  <div className="campaign-metrics">
                    <span>Contato: {lead.contact_id ? "sim" : "não"}</span>
                    <span>
                      Oportunidade: {lead.opportunity_id ? "sim" : "não"}
                    </span>
                    <span>
                      {lead.created_at
                        ? new Date(lead.created_at).toLocaleString("pt-BR")
                        : ""}
                    </span>
                  </div>
                </div>
              ))
            )}
          </article>
        </div>
      )}
    </>
  );
}
