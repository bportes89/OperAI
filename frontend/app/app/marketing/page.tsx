"use client";

import Link from "next/link";
import { FormEvent, useCallback, useEffect, useState } from "react";
import { apiJson } from "../../lib/api";
import {
  CAMPAIGN_STATUS_LABELS,
  CAMPAIGN_TRANSITIONS,
  type BrandKit,
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

const LEAD_STATUS_LABELS: Record<string, string> = {
  handed_off: "Encaminhado",
  escalated: "Escalado",
};

type VocabMode = "calm" | "direct";

type DiagnosisKey =
  | "channels_active"
  | "content_types"
  | "frequency"
  | "engagement_notes"
  | "brand_assets"
  | "commercial_results";

const DIAGNOSIS_QUESTIONS: Array<{
  key: DiagnosisKey;
  label: string;
  kind: "textarea" | "input";
  required?: boolean;
  placeholder?: string;
  help?: string;
  quickFill?: string;
}> = [
  {
    key: "channels_active",
    label: "Quais canais você usa hoje?",
    kind: "textarea",
    required: true,
    placeholder:
      "Ex.: Instagram (@...), WhatsApp Business, Google Business Profile, site…",
    help: "Liste onde você já aparece e onde as pessoas te chamam para pedir orçamento.",
  },
  {
    key: "content_types",
    label: "Que tipo de conteúdo você publica?",
    kind: "textarea",
    required: true,
    placeholder: "Ex.: fotos de produtos, bastidores, promoções, depoimentos…",
    help: "Pode ser simples. O objetivo é entender o que já existe hoje.",
  },
  {
    key: "frequency",
    label: "Com que frequência você publica?",
    kind: "input",
    required: true,
    placeholder: "Ex.: 2–3 vezes por semana (sem calendário fixo)",
    help: "Se varia, responda com uma média.",
  },
  {
    key: "engagement_notes",
    label: "Você tem números de engajamento?",
    kind: "textarea",
    placeholder:
      "Ex.: seguidores, alcance médio, curtidas, cliques no link, mensagens por semana…",
    help: "Se não souber, pode dizer “não sei” — a plataforma funciona mesmo assim.",
    quickFill: "Não sei informar agora.",
  },
  {
    key: "brand_assets",
    label: "Tem algum material de marca para anexar aqui?",
    kind: "textarea",
    placeholder:
      "Ex.: link do logo, paleta, mensagens prontas, cardápio, fotos, promoções…",
    help: "O kit de marca da Base já entra no plano. Use aqui só o que for específico desta campanha.",
  },
  {
    key: "commercial_results",
    label: "Quais resultados comerciais o marketing gera hoje?",
    kind: "textarea",
    placeholder:
      "Ex.: pedidos por indicação, mensagens no WhatsApp, poucas vendas via Instagram…",
    help: "Se não tiver números, descreva a sensação geral (o que funciona e o que não).",
  },
];

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
  const [brandKit, setBrandKit] = useState<BrandKit | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [view, setView] = useState<
    "wizard" | "campaigns" | "conversion" | "governance" | "growth"
  >("wizard");
  const [interestFor, setInterestFor] = useState<string | null>(null);
  const [vocabMode, setVocabMode] = useState<VocabMode>("calm");
  const [diagnosisIndex, setDiagnosisIndex] = useState(0);
  const [diagnosisDirty, setDiagnosisDirty] = useState(false);
  const [diagnosisDraft, setDiagnosisDraft] = useState<
    Record<DiagnosisKey, string>
  >({
    channels_active: "",
    content_types: "",
    frequency: "",
    engagement_notes: "",
    brand_assets: "",
    commercial_results: "",
  });
  const [discoveryDirty, setDiscoveryDirty] = useState(false);
  const [discoveryDraft, setDiscoveryDraft] = useState<Record<string, string>>({
    competitors: "",
    differentiators: "",
    ideal_customer: "",
    mission_values: "",
    brand_avoid: "",
    lead_capacity: "",
    seasonality: "",
    monthly_budget: "",
  });

  const load = useCallback(async () => {
    try {
      setError("");
      const [pb, cams, leadRows, conv, gov, spendRows, growthData, engRows, kit] =
        await Promise.all([
          apiJson<MarketingPlaybook>("/api/v1/marketing/playbook"),
          apiJson<Campaign[]>("/api/v1/marketing/campaigns"),
          apiJson<MarketingLead[]>("/api/v1/marketing/leads"),
          apiJson<MarketingConversion>("/api/v1/marketing/conversion"),
          apiJson<MarketingGovernance>("/api/v1/marketing/governance"),
          apiJson<MarketingSpendRequest[]>("/api/v1/marketing/spend-requests"),
          apiJson<MarketingGrowth>("/api/v1/marketing/growth"),
          apiJson<MarketingEngagement[]>("/api/v1/marketing/engagements"),
          apiJson<BrandKit>("/api/v1/settings/brand-kit"),
        ]);
      setPlaybook(pb);
      setCampaigns(cams);
      setLeads(leadRows);
      setConversion(conv);
      setGovernance(gov);
      setSpends(spendRows);
      setGrowth(growthData);
      setEngagements(engRows);
      setBrandKit(kit);
    } catch (e) {
      setError((e as Error).message);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    const onFocus = () => void load();
    const onVisible = () => {
      if (!document.hidden) void load();
    };
    window.addEventListener("focus", onFocus);
    document.addEventListener("visibilitychange", onVisible);
    return () => {
      window.removeEventListener("focus", onFocus);
      document.removeEventListener("visibilitychange", onVisible);
    };
  }, [load]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const raw = window.localStorage.getItem("operai_vocab_mode");
    if (raw === "direct" || raw === "calm") setVocabMode(raw);
  }, []);

  useEffect(() => {
    if (!playbook) return;
    if (!diagnosisDirty) {
      const d = playbook.diagnosis ?? {};
      const brandAssets =
        String(d.brand_assets || "").trim() ||
        [
          brandKit?.logo_url,
          brandKit?.notes,
          brandKit?.primary_color &&
            `cores ${brandKit.primary_color}${brandKit.secondary_color ? ` / ${brandKit.secondary_color}` : ""}`,
        ]
          .filter(Boolean)
          .join("\n") ||
        "";
      setDiagnosisDraft({
        channels_active: String(d.channels_active || ""),
        content_types: String(d.content_types || ""),
        frequency: String(d.frequency || ""),
        engagement_notes: String(d.engagement_notes || ""),
        brand_assets: brandAssets,
        commercial_results: String(d.commercial_results || ""),
      });
    }
    if (!discoveryDirty) {
      const disc = playbook.discovery ?? {};
      setDiscoveryDraft({
        competitors: String(disc.competitors || ""),
        differentiators: String(disc.differentiators || ""),
        ideal_customer: String(disc.ideal_customer || ""),
        mission_values: String(disc.mission_values || ""),
        brand_avoid: String(disc.brand_avoid || brandKit?.avoid || ""),
        lead_capacity: String(disc.lead_capacity || ""),
        seasonality: String(disc.seasonality || ""),
        monthly_budget: String(disc.monthly_budget || ""),
      });
    }
  }, [playbook, brandKit, diagnosisDirty, discoveryDirty]);

  async function saveDiagnosis() {
    setBusy(true);
    setError("");
    try {
      const pb = await apiJson<MarketingPlaybook>(
        "/api/v1/marketing/playbook/diagnosis",
        { method: "PUT", body: JSON.stringify(diagnosisDraft) },
      );
      setPlaybook(pb);
      setDiagnosisDirty(false);
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
    try {
      const pb = await apiJson<MarketingPlaybook>(
        "/api/v1/marketing/playbook/discovery",
        { method: "PUT", body: JSON.stringify(discoveryDraft) },
      );
      setPlaybook(pb);
      setDiscoveryDirty(false);
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
      window.dispatchEvent(new CustomEvent("operai:crm-updated"));
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
          Registrar pessoa interessada → Clientes
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
            <span>Interessados com contato</span>
            <strong>{conversion.leads_with_contact}</strong>
            <small>telefone ou e-mail</small>
          </article>
          <article>
            <span>Oportunidades em Clientes</span>
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
              interessado vai para Clientes.
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
            <p style={{ marginBottom: 0, marginTop: 14, lineHeight: 1.5, opacity: 0.9 }}>
              {brandKit?.configured ? (
                <>
                  Kit de marca ativo
                  {brandKit.brand_name ? `: ${brandKit.brand_name}` : ""}
                  {brandKit.voice_tone
                    ? ` · tom: ${brandKit.voice_tone.slice(0, 80)}${brandKit.voice_tone.length > 80 ? "…" : ""}`
                    : ""}
                  .{" "}
                  <Link href="/app/knowledge#brand">Editar na Base</Link>
                </>
              ) : (
                <>
                  Sem kit de marca ainda — posts e agentes ficam mais genéricos.{" "}
                  <Link href="/app/knowledge#brand">Cadastrar identidade</Link>
                </>
              )}
            </p>
          </article>

          {step === "diagnosis" && (
            <article className="panel">
              <div className="panel-title">
                <div>
                  <span>AS IS</span>
                  <h2>Diagnóstico inicial</h2>
                </div>
              </div>
              <div className="proposal-actions" style={{ flexWrap: "wrap" }}>
                <span className="finance-status paid">Explicações</span>
                <button
                  type="button"
                  className={vocabMode === "calm" ? "primary" : undefined}
                  onClick={() => {
                    setVocabMode("calm");
                    window.localStorage.setItem("operai_vocab_mode", "calm");
                  }}
                >
                  Me explica com calma
                </button>
                <button
                  type="button"
                  className={vocabMode === "direct" ? "primary" : undefined}
                  onClick={() => {
                    setVocabMode("direct");
                    window.localStorage.setItem("operai_vocab_mode", "direct");
                  }}
                >
                  Direto ao ponto
                </button>
              </div>

              {diagnosisIndex >= DIAGNOSIS_QUESTIONS.length ? (
                <>
                  <p style={{ marginTop: 12, opacity: 0.85 }}>
                    Revise antes de salvar. Você pode voltar e ajustar qualquer resposta.
                  </p>
                  <div style={{ display: "grid", gap: 12 }}>
                    {DIAGNOSIS_QUESTIONS.map((q, idx) => (
                      <div
                        key={q.key}
                        style={{
                          display: "grid",
                          gap: 6,
                          padding: 12,
                          border: "1px solid rgba(255,255,255,0.08)",
                          borderRadius: 12,
                        }}
                      >
                        <div className="proposal-actions" style={{ justifyContent: "space-between" }}>
                          <strong>{q.label}</strong>
                          <button
                            type="button"
                            onClick={() => setDiagnosisIndex(idx)}
                          >
                            Editar
                          </button>
                        </div>
                        <p style={{ margin: 0, whiteSpace: "pre-wrap", opacity: 0.9 }}>
                          {diagnosisDraft[q.key] || "—"}
                        </p>
                      </div>
                    ))}
                  </div>
                  <div className="proposal-actions" style={{ marginTop: 12 }}>
                    <button
                      type="button"
                      disabled={busy}
                      onClick={() => setDiagnosisIndex(DIAGNOSIS_QUESTIONS.length - 1)}
                    >
                      Voltar
                    </button>
                    <button
                      className="primary"
                      type="button"
                      disabled={
                        busy ||
                        diagnosisDraft.channels_active.trim().length < 2 ||
                        diagnosisDraft.content_types.trim().length < 2 ||
                        diagnosisDraft.frequency.trim().length < 2
                      }
                      onClick={() => void saveDiagnosis()}
                    >
                      {busy ? "Salvando…" : "Salvar e ir à descoberta"}
                    </button>
                  </div>
                </>
              ) : (
                (() => {
                  const q = DIAGNOSIS_QUESTIONS[diagnosisIndex];
                  const value = diagnosisDraft[q.key] ?? "";
                  const min = q.required ? 2 : 0;
                  const canContinue = value.trim().length >= min;
                  return (
                    <>
                      <p style={{ marginTop: 12, marginBottom: 6, opacity: 0.85 }}>
                        Pergunta {diagnosisIndex + 1} de {DIAGNOSIS_QUESTIONS.length}
                      </p>
                      <label>
                        {q.label}
                        {q.kind === "input" ? (
                          <input
                            value={value}
                            placeholder={q.placeholder}
                            onChange={(e) => {
                              setDiagnosisDirty(true);
                              setDiagnosisDraft((prev) => ({
                                ...prev,
                                [q.key]: e.target.value,
                              }));
                            }}
                          />
                        ) : (
                          <textarea
                            value={value}
                            placeholder={q.placeholder}
                            onChange={(e) => {
                              setDiagnosisDirty(true);
                              setDiagnosisDraft((prev) => ({
                                ...prev,
                                [q.key]: e.target.value,
                              }));
                            }}
                          />
                        )}
                      </label>
                      {vocabMode === "calm" && q.help && (
                        <p style={{ marginTop: 0, opacity: 0.8 }}>{q.help}</p>
                      )}
                      <div className="proposal-actions" style={{ flexWrap: "wrap" }}>
                        {q.quickFill && (
                          <button
                            type="button"
                            onClick={() => {
                              setDiagnosisDirty(true);
                              setDiagnosisDraft((prev) => ({
                                ...prev,
                                [q.key]: q.quickFill ?? "",
                              }));
                            }}
                          >
                            Não sei
                          </button>
                        )}
                        <button
                          type="button"
                          disabled={busy || diagnosisIndex === 0}
                          onClick={() => setDiagnosisIndex((prev) => Math.max(0, prev - 1))}
                        >
                          Voltar
                        </button>
                        <button
                          type="button"
                          className="primary"
                          disabled={busy || !canContinue}
                          onClick={() =>
                            setDiagnosisIndex((prev) =>
                              Math.min(DIAGNOSIS_QUESTIONS.length, prev + 1),
                            )
                          }
                        >
                          Próximo
                        </button>
                      </div>
                    </>
                  );
                })()
              )}
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
                    value={discoveryDraft.competitors}
                    onChange={(e) => {
                      setDiscoveryDirty(true);
                      setDiscoveryDraft((prev) => ({
                        ...prev,
                        competitors: e.target.value,
                      }));
                    }}
                  />
                </label>
                <label>
                  Diferencial
                  <textarea
                    name="differentiators"
                    required
                    minLength={2}
                    value={discoveryDraft.differentiators}
                    onChange={(e) => {
                      setDiscoveryDirty(true);
                      setDiscoveryDraft((prev) => ({
                        ...prev,
                        differentiators: e.target.value,
                      }));
                    }}
                  />
                </label>
                <label>
                  Cliente ideal
                  <textarea
                    name="ideal_customer"
                    required
                    minLength={2}
                    value={discoveryDraft.ideal_customer}
                    onChange={(e) => {
                      setDiscoveryDirty(true);
                      setDiscoveryDraft((prev) => ({
                        ...prev,
                        ideal_customer: e.target.value,
                      }));
                    }}
                  />
                </label>
                <label>
                  Missão, visão e valores
                  <textarea
                    name="mission_values"
                    required
                    minLength={2}
                    value={discoveryDraft.mission_values}
                    onChange={(e) => {
                      setDiscoveryDirty(true);
                      setDiscoveryDraft((prev) => ({
                        ...prev,
                        mission_values: e.target.value,
                      }));
                    }}
                  />
                </label>
                <label>
                  O que a marca deve evitar (complementa o kit)
                  <textarea
                    name="brand_avoid"
                    value={discoveryDraft.brand_avoid}
                    placeholder="Já vem do kit se estiver preenchido"
                    onChange={(e) => {
                      setDiscoveryDirty(true);
                      setDiscoveryDraft((prev) => ({
                        ...prev,
                        brand_avoid: e.target.value,
                      }));
                    }}
                  />
                </label>
                <label>
                  Capacidade de leads
                  <input
                    name="lead_capacity"
                    required
                    minLength={1}
                    value={discoveryDraft.lead_capacity}
                    onChange={(e) => {
                      setDiscoveryDirty(true);
                      setDiscoveryDraft((prev) => ({
                        ...prev,
                        lead_capacity: e.target.value,
                      }));
                    }}
                  />
                </label>
                <label>
                  Sazonalidade
                  <input
                    name="seasonality"
                    value={discoveryDraft.seasonality}
                    onChange={(e) => {
                      setDiscoveryDirty(true);
                      setDiscoveryDraft((prev) => ({
                        ...prev,
                        seasonality: e.target.value,
                      }));
                    }}
                  />
                </label>
                <label>
                  Orçamento mensal
                  <input
                    name="monthly_budget"
                    required
                    minLength={1}
                    value={discoveryDraft.monthly_budget}
                    onChange={(e) => {
                      setDiscoveryDirty(true);
                      setDiscoveryDraft((prev) => ({
                        ...prev,
                        monthly_budget: e.target.value,
                      }));
                    }}
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
                    <h2>Peças com chamada para ação</h2>
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
                    {CAMPAIGN_STATUS_LABELS[item.status] ?? item.status}
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
                <h2>Conteúdo → interesse → Clientes</h2>
              </div>
            </div>
            <p style={{ opacity: 0.85 }}>
              Cada interesse vira contato + oportunidade em estágio{" "}
              <strong>Novos</strong> e tarefa de handoff para o agente comercial
              ou WhatsApp.
            </p>
            <div className="proposal-actions">
              <Link href="/app/crm">Abrir Clientes</Link>
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
                <span>INTERESSADOS</span>
                <h2>Pessoas interessadas</h2>
              </div>
            </div>
            {leads.length === 0 ? (
              <div className="empty">
                <strong>Nenhum interesse ainda</strong>
                <p>
                  Nas peças ou campanhas, use “Registrar pessoa interessada →
                  Clientes” quando alguém engajar.
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
                    {LEAD_STATUS_LABELS[lead.status] ?? lead.status}
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
                <span>Interesses → Clientes</span>
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
