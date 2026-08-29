"use client";

import Link from "next/link";
import { FormEvent, useCallback, useEffect, useState } from "react";
import { apiJson } from "../../lib/api";
import {
  CAMPAIGN_STATUS_LABELS,
  CAMPAIGN_TRANSITIONS,
  type Campaign,
  type MarketingConversion,
  type MarketingEngagement,
  type MarketingGovernance,
  type MarketingGrowth,
  type MarketingLead,
  type MarketingPlaybook,
  type MarketingPost,
  type MarketingSpendRequest,
} from "../../lib/types";
import { money } from "../../lib/format";

const SEO_LABELS: Record<string, string> = {
  google_business_profile: "Perfil Google Business completo e verificado",
  nap_consistent: "Nome, endereço e telefone consistentes (NAP)",
  site_basic_seo: "SEO básico no site (títulos, meta, mobile)",
  faq_on_site: "FAQ / políticas publicadas no site ou base OperAI",
  local_keywords: "Palavras-chave locais definidas",
};

const WIZARD_STEPS = [
  { key: "diagnosis", label: "1. Diagnóstico" },
  { key: "discovery", label: "2. Descoberta" },
  { key: "plan", label: "3. Plano" },
  { key: "active", label: "4. Peças" },
] as const;

const CHANNEL_LABEL: Record<string, string> = {
  whatsapp: "WhatsApp",
  email: "E-mail",
  social: "Redes sociais",
  google_ads: "Google Ads (busca)",
  meta_ads: "Meta Ads",
};

function interestChannel(channel: string) {
  if (channel === "whatsapp" || channel === "email") return channel;
  return "social";
}

function stepIndex(step: string) {
  const i = WIZARD_STEPS.findIndex((s) => s.key === step);
  return i < 0 ? 0 : i;
}

export default function MarketingPage() {
  const [playbook, setPlaybook] = useState<MarketingPlaybook | null>(null);
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [leads, setLeads] = useState<MarketingLead[]>([]);
  const [conversion, setConversion] = useState<MarketingConversion | null>(null);
  const [governance, setGovernance] = useState<MarketingGovernance | null>(null);
  const [spends, setSpends] = useState<MarketingSpendRequest[]>([]);
  const [growth, setGrowth] = useState<MarketingGrowth | null>(null);
  const [engagements, setEngagements] = useState<MarketingEngagement[]>([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [view, setView] = useState<
    "wizard" | "campaigns" | "conversion" | "governance" | "growth"
  >("wizard");
  const [interestFor, setInterestFor] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setError("");
      const [pb, cams, leadRows, conv, gov, spendRows, growthData, engRows] =
        await Promise.all([
          apiJson<MarketingPlaybook>("/api/v1/marketing/playbook"),
          apiJson<Campaign[]>("/api/v1/marketing/campaigns"),
          apiJson<MarketingLead[]>("/api/v1/marketing/leads"),
          apiJson<MarketingConversion>("/api/v1/marketing/conversion"),
          apiJson<MarketingGovernance>("/api/v1/marketing/governance"),
          apiJson<MarketingSpendRequest[]>("/api/v1/marketing/spend-requests"),
          apiJson<MarketingGrowth>("/api/v1/marketing/growth"),
          apiJson<MarketingEngagement[]>("/api/v1/marketing/engagements"),
        ]);
      setPlaybook(pb);
      setCampaigns(cams);
      setLeads(leadRows);
      setConversion(conv);
      setGovernance(gov);
      setSpends(spendRows);
      setGrowth(growthData);
      setEngagements(engRows);
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

  async function regeneratePost(index: number) {
    setBusy(true);
    setError("");
    try {
      const result = await apiJson<{
        playbook: MarketingPlaybook;
        post: MarketingPost;
      }>(`/api/v1/marketing/playbook/posts/${index}/regenerate`, {
        method: "POST",
        body: "{}",
      });
      setPlaybook(result.playbook);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function requestCampaignSpend(item: Campaign) {
    const raw = window.prompt(
      "Valor da verba de anúncio (R$):",
      "100",
    );
    if (!raw) return;
    const amount = Math.round(Number(raw.replace(",", ".")) * 100);
    if (!Number.isFinite(amount) || amount <= 0) {
      setError("Informe um valor válido em reais.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      const result = await apiJson<{
        status: string;
        needs_owner_approval: boolean;
      }>(`/api/v1/marketing/campaigns/${item.id}/request-spend`, {
        method: "POST",
        body: JSON.stringify({ amount_cents: amount }),
      });
      await load();
      setView("governance");
      if (result.needs_owner_approval) {
        setError("");
        window.alert(
          "Pedido acima do teto — aguardando aprovação do dono na Governança.",
        );
      } else {
        window.alert("Verba registrada dentro do teto (aprovada automaticamente).");
      }
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
          consent_lgpd: data.consent_lgpd === "on",
          is_crisis: data.is_crisis === "on",
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
        <label className="check-row">
          <input name="consent_lgpd" type="checkbox" required />
          Consentimento LGPD: o interessado autorizou o tratamento dos dados
          para contato comercial
        </label>
        <label className="check-row">
          <input name="is_crisis" type="checkbox" />
          Situação sensível / crise — escalar para humano (sem resposta automática)
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

  async function saveGovernance(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    const form = event.currentTarget;
    const data = Object.fromEntries(new FormData(form));
    try {
      const gov = await apiJson<MarketingGovernance>(
        "/api/v1/marketing/governance",
        {
          method: "PUT",
          body: JSON.stringify({
            monthly_ad_ceiling_cents: Math.round(
              Number(data.ceiling_reais || 0) * 100,
            ),
            crisis_escalation: data.crisis_escalation === "on",
            lgpd_note: data.lgpd_note || null,
            account_checklist: {
              google_business: data.google_business === "on",
              meta_business: data.meta_business === "on",
              whatsapp_business: data.whatsapp_business === "on",
            },
            seo_checklist: {
              google_business_profile: data.google_business_profile === "on",
              nap_consistent: data.nap_consistent === "on",
              site_basic_seo: data.site_basic_seo === "on",
              faq_on_site: data.faq_on_site === "on",
              local_keywords: data.local_keywords === "on",
            },
          }),
        },
      );
      setGovernance(gov);
      await load();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function logEngagement(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    const form = event.currentTarget;
    const data = Object.fromEntries(new FormData(form));
    try {
      await apiJson("/api/v1/marketing/engagements", {
        method: "POST",
        body: JSON.stringify({
          label: data.label,
          channel: data.channel,
          views: Number(data.views || 0),
          clicks: Number(data.clicks || 0),
          likes: Number(data.likes || 0),
          comments: Number(data.comments || 0),
          best_day: data.best_day || null,
          audience_note: data.audience_note || null,
          campaign_id: data.campaign_id || null,
        }),
      });
      form.reset();
      await load();
      setView("growth");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function upgradePackage(packageName: string) {
    setBusy(true);
    setError("");
    try {
      await apiJson("/api/v1/marketing/playbook/upgrade", {
        method: "POST",
        body: JSON.stringify({ package: packageName }),
      });
      await load();
      setView("growth");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function requestSpend(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    const form = event.currentTarget;
    const data = Object.fromEntries(new FormData(form));
    try {
      await apiJson("/api/v1/marketing/spend-requests", {
        method: "POST",
        body: JSON.stringify({
          channel: data.channel,
          description: data.description,
          amount_cents: Math.round(Number(data.amount || 0) * 100),
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

  async function reviewSpend(id: string, status: "approved" | "rejected") {
    setBusy(true);
    setError("");
    try {
      await apiJson(`/api/v1/marketing/spend-requests/${id}`, {
        method: "PATCH",
        body: JSON.stringify({ status }),
      });
      await load();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function escalateLead(id: string) {
    setBusy(true);
    setError("");
    try {
      await apiJson(`/api/v1/marketing/leads/${id}/escalate`, {
        method: "POST",
        body: "{}",
      });
      await load();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
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
          <button
            type="button"
            className={view === "conversion" ? "primary" : undefined}
            onClick={() => setView("conversion")}
          >
            Conversão
          </button>
          <button
            type="button"
            className={view === "governance" ? "primary" : undefined}
            onClick={() => setView("governance")}
          >
            Governança
          </button>
          <button
            type="button"
            className={view === "growth" ? "primary" : undefined}
            onClick={() => setView("growth")}
          >
            Crescimento
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
                            {CHANNEL_LABEL[post.channel] ?? post.channel} ·{" "}
                            {post.audience}
                          </small>
                        </div>
                        <p>{post.content}</p>
                        <div className="proposal-actions" style={{ marginBottom: 8 }}>
                          <button
                            type="button"
                            disabled={busy}
                            onClick={() => void regeneratePost(idx)}
                          >
                            {busy ? "Reescrevendo…" : "Regenerar peça (IA)"}
                          </button>
                        </div>
                        {interestForm(`post-${idx}`, {
                          title: post.title,
                          channel: interestChannel(post.channel),
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
                      {CHANNEL_LABEL[item.channel] ?? item.channel} ·{" "}
                      {item.audience}
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
                    {(item.channel === "google_ads" ||
                      item.channel === "meta_ads") &&
                      item.status !== "cancelled" && (
                        <button
                          type="button"
                          className="primary"
                          disabled={busy}
                          onClick={() => void requestCampaignSpend(item)}
                        >
                          Pedir verba de anúncio
                        </button>
                      )}
                  </div>
                  {interestForm(`camp-${item.id}`, {
                    title: item.name,
                    channel: interestChannel(item.channel),
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
                  <option value="google_ads">Google Ads (busca paga)</option>
                  <option value="meta_ads">Meta Ads</option>
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
                      LGPD: {lead.consent_lgpd ? "ok" : "—"}
                    </span>
                    <span>
                      {lead.created_at
                        ? new Date(lead.created_at).toLocaleString("pt-BR")
                        : ""}
                    </span>
                  </div>
                  {!lead.is_crisis && (
                    <button
                      type="button"
                      disabled={busy}
                      onClick={() => void escalateLead(lead.id)}
                    >
                      Escalar crise → humano
                    </button>
                  )}
                </div>
              ))
            )}
          </article>
        </div>
      )}

      {view === "governance" && governance && (
        <div className="content-grid">
          <article className="panel">
            <div className="panel-title">
              <div>
                <span>CONTROLE</span>
                <h2>Teto de mídia, LGPD e contas</h2>
              </div>
            </div>
            <div className="metrics" style={{ marginBottom: 16 }}>
              <article>
                <span>Teto mensal Ads</span>
                <strong>{money(governance.monthly_ad_ceiling_cents)}</strong>
                <small>Google/Meta — separado da mensalidade</small>
              </article>
              <article>
                <span>Já consumido</span>
                <strong>{money(governance.spent_cents)}</strong>
                <small>restam {money(governance.remaining_cents)}</small>
              </article>
            </div>
            <form onSubmit={saveGovernance}>
              <label>
                Teto mensal de mídia paga (R$)
                <input
                  name="ceiling_reais"
                  type="number"
                  min={0}
                  step="0.01"
                  defaultValue={(
                    governance.monthly_ad_ceiling_cents / 100
                  ).toFixed(2)}
                />
              </label>
              <label className="check-row">
                <input
                  name="crisis_escalation"
                  type="checkbox"
                  defaultChecked={governance.crisis_escalation}
                />
                Escalonar crises automaticamente para humano
              </label>
              <label>
                Nota LGPD (visível na operação)
                <textarea
                  name="lgpd_note"
                  defaultValue={governance.lgpd_note ?? ""}
                />
              </label>
              <strong>Checklist — só o dono consegue verificar estas contas</strong>
              <p style={{ opacity: 0.8, marginTop: 4 }}>
                O agente guia; a verificação de identidade nas plataformas é
                sempre humana.
              </p>
              <div className="checklist-block">
                <label className="check-row">
                  <input
                    name="google_business"
                    type="checkbox"
                    defaultChecked={!!governance.account_checklist.google_business}
                  />
                  Perfil da Empresa no Google (Business Profile) verificado
                </label>
                <label className="check-row">
                  <input
                    name="meta_business"
                    type="checkbox"
                    defaultChecked={!!governance.account_checklist.meta_business}
                  />
                  Meta Business Manager criado/verificado
                </label>
                <label className="check-row">
                  <input
                    name="whatsapp_business"
                    type="checkbox"
                    defaultChecked={
                      !!governance.account_checklist.whatsapp_business
                    }
                  />
                  WhatsApp Business / API credenciado
                </label>
              </div>
              <strong style={{ marginTop: 12 }}>Checklist SEO / Google</strong>
              <div className="checklist-block">
                {Object.entries(SEO_LABELS).map(([key, label]) => (
                  <label key={key} className="check-row">
                    <input
                      name={key}
                      type="checkbox"
                      defaultChecked={Boolean(
                        (
                          governance.seo_checklist as
                            | Record<string, boolean>
                            | undefined
                        )?.[key],
                      )}
                    />
                    {label}
                  </label>
                ))}
              </div>
              <button className="primary" disabled={busy} type="submit">
                Salvar governança
              </button>
            </form>
          </article>

          <article className="panel">
            <div className="panel-title">
              <div>
                <span>GASTOS</span>
                <h2>Pedidos de mídia paga</h2>
              </div>
            </div>
            <form onSubmit={requestSpend}>
              <label>
                Canal
                <select name="channel" defaultValue="meta_ads">
                  <option value="meta_ads">Meta Ads</option>
                  <option value="google_ads">Google Ads</option>
                  <option value="other">Outro</option>
                </select>
              </label>
              <label>
                Descrição
                <input name="description" required minLength={2} />
              </label>
              <label>
                Valor (R$)
                <input
                  name="amount"
                  type="number"
                  min={0.01}
                  step="0.01"
                  required
                />
              </label>
              <button className="primary" disabled={busy} type="submit">
                Registrar gasto / pedido
              </button>
            </form>
            <p style={{ opacity: 0.8 }}>
              Dentro do teto: aprovado e contabilizado. Acima do teto: aguarda
              aprovação do owner/admin.
            </p>
            {spends.length === 0 ? (
              <div className="empty">
                <strong>Nenhum pedido</strong>
                <p>Verba de Ads é sempre separada da mensalidade OperAI.</p>
              </div>
            ) : (
              spends.map((s) => (
                <div className="campaign-card" key={s.id}>
                  <div>
                    <strong>{money(s.amount_cents)}</strong>
                    <small>
                      {s.channel} · {s.description}
                    </small>
                  </div>
                  <span className={`finance-status ${s.status}`}>{s.status}</span>
                  {s.status === "pending" && (
                    <div className="proposal-actions">
                      <button
                        type="button"
                        disabled={busy}
                        onClick={() => void reviewSpend(s.id, "approved")}
                      >
                        Aprovar
                      </button>
                      <button
                        type="button"
                        disabled={busy}
                        onClick={() => void reviewSpend(s.id, "rejected")}
                      >
                        Rejeitar
                      </button>
                    </div>
                  )}
                </div>
              ))
            )}
          </article>
        </div>
      )}

      {view === "growth" && growth && (
        <div className="content-grid">
          <article className="panel">
            <div className="panel-title">
              <div>
                <span>DADOS</span>
                <h2>Engajamento (7 dias)</h2>
              </div>
            </div>
            <div className="metrics">
              <article>
                <span>Views</span>
                <strong>{growth.engagement_7d.views}</strong>
                <small>{growth.engagement_7d.entries} leituras</small>
              </article>
              <article>
                <span>Cliques / CTR</span>
                <strong>
                  {growth.engagement_7d.clicks} · {growth.engagement_7d.ctr_pct}%
                </strong>
                <small>
                  {growth.engagement_7d.best_day
                    ? `melhor dia: ${growth.engagement_7d.best_day}`
                    : "sem melhor dia ainda"}
                </small>
              </article>
              <article>
                <span>Interesses → CRM</span>
                <strong>{growth.conversion_7d.interests}</strong>
                <small>
                  {growth.conversion_7d.opportunities} oportunidades
                </small>
              </article>
            </div>
            <p style={{ whiteSpace: "pre-wrap" }}>
              <strong>Recomendação do Gestor: </strong>
              {growth.engagement_7d.recommendation}
            </p>
            <form onSubmit={logEngagement}>
              <label>
                Peça / post analisado
                <input name="label" required minLength={2} />
              </label>
              <label>
                Canal
                <select name="channel" defaultValue="social">
                  <option value="social">Social</option>
                  <option value="email">E-mail</option>
                  <option value="whatsapp">WhatsApp</option>
                </select>
              </label>
              <label>
                Campanha (opcional)
                <select name="campaign_id" defaultValue="">
                  <option value="">—</option>
                  {campaigns.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.name}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Views
                <input name="views" type="number" min={0} defaultValue={0} />
              </label>
              <label>
                Cliques
                <input name="clicks" type="number" min={0} defaultValue={0} />
              </label>
              <label>
                Curtidas
                <input name="likes" type="number" min={0} defaultValue={0} />
              </label>
              <label>
                Comentários
                <input name="comments" type="number" min={0} defaultValue={0} />
              </label>
              <label>
                Melhor dia/horário
                <input name="best_day" placeholder="Terça 19h" />
              </label>
              <label>
                Perfil de quem engajou
                <textarea name="audience_note" />
              </label>
              <button className="primary" disabled={busy} type="submit">
                Registrar leitura de engajamento
              </button>
            </form>
            {engagements.slice(0, 5).map((e) => (
              <div className="campaign-card" key={e.id}>
                <div>
                  <strong>{e.label}</strong>
                  <small>
                    {e.channel} · {e.views} views · {e.clicks} cliques
                  </small>
                </div>
                <p>{e.recommendation}</p>
              </div>
            ))}
          </article>

          <article className="panel">
            <div className="panel-title">
              <div>
                <span>PACOTE</span>
                <h2>
                  {growth.package} →{" "}
                  {growth.upgrade.recommended_package}
                </h2>
              </div>
            </div>
            <p>
              Pacote atual: <strong>{growth.upgrade.current_package}</strong>
            </p>
            <ul>
              {(growth.upgrade.packages[growth.package] || []).map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
            {growth.upgrade.reasons.map((r) => (
              <p key={r} style={{ opacity: 0.85 }}>
                {r}
              </p>
            ))}
            {growth.upgrade.ready ? (
              <button
                className="primary"
                type="button"
                disabled={busy}
                onClick={() =>
                  void upgradePackage(growth.upgrade.recommended_package)
                }
              >
                Aceitar upgrade para {growth.upgrade.recommended_package}
              </button>
            ) : (
              <p>
                O Gestor ainda não recomenda upgrade — avance nos critérios
                acima.
              </p>
            )}
            <strong style={{ display: "block", marginTop: 16 }}>
              SEO / Google (atalho)
            </strong>
            <p style={{ opacity: 0.8 }}>
              Marque o progresso em Governança. Resumo:
            </p>
            {Object.entries(SEO_LABELS).map(([key, label]) => (
              <div key={key} className="campaign-metrics">
                <span>
                  {growth.seo_checklist[key] ? "✓" : "○"} {label}
                </span>
              </div>
            ))}
            <button type="button" onClick={() => setView("governance")}>
              Abrir checklist completo
            </button>
          </article>
        </div>
      )}
    </>
  );
}
