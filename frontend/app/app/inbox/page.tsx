"use client";

import Link from "next/link";
import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { apiJson } from "../../lib/api";
import { formatDateTime } from "../../lib/format";
import type {
  Channel,
  InboxMessage,
  InboxThread,
  Opportunity,
  WhatsAppTemplate,
} from "../../lib/types";

export default function InboxPage() {
  const [channels, setChannels] = useState<Channel[]>([]);
  const [threads, setThreads] = useState<InboxThread[]>([]);
  const [selectedThread, setSelectedThread] = useState<string | null>(null);
  const [messages, setMessages] = useState<InboxMessage[]>([]);
  const [channelSecret, setChannelSecret] = useState("");
  const [evolutionInfo, setEvolutionInfo] = useState("");
  const [metaInfo, setMetaInfo] = useState<{
    webhook_url: string;
    verify_token: string;
    message?: string;
  } | null>(null);
  const [qrImage, setQrImage] = useState<string | null>(null);
  const [qrInfo, setQrInfo] = useState("");
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [crmOpen, setCrmOpen] = useState(false);
  const [templates, setTemplates] = useState<WhatsAppTemplate[]>([]);
  const [templatesHint, setTemplatesHint] = useState("");
  const [templatesSource, setTemplatesSource] = useState("");
  const [selectedTemplate, setSelectedTemplate] = useState("");
  const [templateLang, setTemplateLang] = useState("pt_BR");
  const [templateParams, setTemplateParams] = useState<string[]>([]);

  const load = useCallback(async () => {
    try {
      setError("");
      const [ch, th] = await Promise.all([
        apiJson<Channel[]>("/api/v1/channels"),
        apiJson<InboxThread[]>("/api/v1/inbox/threads"),
      ]);
      setChannels(ch);
      setThreads(th);
    } catch (e) {
      setError((e as Error).message);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function markWhatsappDone() {
    try {
      await apiJson("/api/v1/settings/onboarding", {
        method: "PATCH",
        body: JSON.stringify({
          checklist: { whatsapp: true },
          step: "whatsapp",
        }),
      });
    } catch {
      /* optional */
    }
  }

  async function createChannel(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    const form = event.currentTarget;
    try {
      const result = await apiJson<{ webhook_secret: string }>(
        "/api/v1/channels",
        {
          method: "POST",
          body: JSON.stringify(Object.fromEntries(new FormData(form))),
        },
      );
      setChannelSecret(result.webhook_secret);
      form.reset();
      await load();
      await markWhatsappDone();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function connectMeta(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setMetaInfo(null);
    const form = event.currentTarget;
    const data = Object.fromEntries(new FormData(form));
    try {
      const result = await apiJson<{
        webhook_url: string;
        verify_token: string;
        message?: string;
      }>("/api/v1/channels/meta/connect", {
        method: "POST",
        body: JSON.stringify({
          name: data.name,
          phone_number_id: String(data.phone_number_id).trim(),
          access_token: String(data.access_token).trim(),
          waba_id: String(data.waba_id || "").trim() || null,
        }),
      });
      setMetaInfo(result);
      form.reset();
      await load();
      await markWhatsappDone();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function connectEvolution(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setEvolutionInfo("");
    const form = event.currentTarget;
    const data = Object.fromEntries(new FormData(form));
    try {
      const result = await apiJson<{
        status?: string;
        qrcode?: string | null;
        pairing_code?: string | null;
        instance_name?: string;
        message?: string;
        id?: string;
      }>("/api/v1/channels/evolution/connect", {
        method: "POST",
        body: JSON.stringify({
          name: data.name,
          instance_name: data.instance_name,
        }),
      });
      if (result.qrcode) {
        setQrImage(result.qrcode);
        setQrInfo(
          `Instância ${result.instance_name ?? ""} · escaneie o QR com o WhatsApp da empresa.`,
        );
        setEvolutionInfo("");
      } else {
        setQrImage(null);
        setQrInfo("");
        setEvolutionInfo(
          result.message ||
            `Canal Evolution conectado (${result.status ?? "ok"}). Use "Gerar QR" para vincular.`,
        );
      }
      form.reset();
      await load();
      await markWhatsappDone();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function fetchQr(channel: Channel) {
    setError("");
    setQrInfo("");
    try {
      const result = await apiJson<{
        qrcode?: string | null;
        pairing_code?: string | null;
        status?: string;
      }>(`/api/v1/channels/${channel.id}/evolution/qr`);
      if (result.qrcode) {
        setQrImage(result.qrcode);
        setQrInfo(
          `Instância ${channel.instance_name ?? channel.name} · escaneie o QR com o WhatsApp da empresa.`,
        );
      } else {
        setQrImage(null);
        setQrInfo(
          result.status === "open"
            ? "Instância já conectada."
            : `Status: ${result.status ?? "desconhecido"}. Tente novamente em alguns segundos.`,
        );
      }
    } catch (e) {
      setError((e as Error).message);
    }
  }

  async function openThread(threadId: string) {
    setSelectedThread(threadId);
    setCrmOpen(false);
    setError("");
    setMessage("");
    try {
      const [msgs, th] = await Promise.all([
        apiJson<InboxMessage[]>(
          `/api/v1/inbox/threads/${threadId}/messages`,
        ),
        apiJson<InboxThread[]>("/api/v1/inbox/threads"),
      ]);
      setMessages(msgs);
      setThreads(th);
      const ch = await apiJson<Channel[]>("/api/v1/channels");
      setChannels(ch);
      const thread = th.find((t) => t.id === threadId);
      if (thread?.provider === "meta" && thread.channel_id) {
        await loadTemplates(thread.channel_id);
      } else {
        setTemplates([]);
        setSelectedTemplate("");
      }
    } catch (e) {
      setError((e as Error).message);
    }
  }

  async function loadTemplates(channelId: string) {
    try {
      const result = await apiJson<{
        templates: WhatsAppTemplate[];
        hint?: string;
        source?: string;
      }>(`/api/v1/channels/${channelId}/meta/templates`);
      setTemplates(result.templates || []);
      setTemplatesHint(result.hint || "");
      setTemplatesSource(result.source || "");
      const first = result.templates?.[0];
      if (first) {
        setSelectedTemplate(first.name);
        setTemplateLang(first.language || "pt_BR");
        setTemplateParams(
          Array.from({ length: first.body_param_count || 0 }, () => ""),
        );
      }
    } catch (e) {
      setTemplates([]);
      setTemplatesHint((e as Error).message);
    }
  }

  async function sendMessage(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedThread) return;
    setBusy(true);
    setError("");
    const form = event.currentTarget;
    const text = String(new FormData(form).get("text") ?? "");
    try {
      await apiJson(`/api/v1/inbox/threads/${selectedThread}/messages`, {
        method: "POST",
        body: JSON.stringify({ text }),
      });
      form.reset();
      await load();
      await openThread(selectedThread);
      setMessage("Mensagem enviada — IA pausada nesta conversa.");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function setThreadStatus(status: "open" | "human" | "closed") {
    if (!selectedThread) return;
    setBusy(true);
    setError("");
    setMessage("");
    try {
      const updated = await apiJson<InboxThread>(
        `/api/v1/inbox/threads/${selectedThread}/status`,
        { method: "PATCH", body: JSON.stringify({ status }) },
      );
      setThreads((prev) =>
        prev.map((t) => (t.id === updated.id ? { ...t, ...updated } : t)),
      );
      const labels = {
        open: "IA retomada nesta conversa.",
        human: "Atendente humano — IA pausada.",
        closed: "Conversa encerrada.",
      };
      setMessage(labels[status]);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function createCrmFromThread(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedThread) return;
    setBusy(true);
    setError("");
    setMessage("");
    const data = Object.fromEntries(new FormData(event.currentTarget));
    const value = Number(data.value || 0);
    try {
      const result = await apiJson<{
        opportunity: Opportunity;
        thread_status?: string;
        message?: string;
      }>(`/api/v1/inbox/threads/${selectedThread}/opportunity`, {
        method: "POST",
        body: JSON.stringify({
          company: String(data.company || "").trim() || null,
          value_cents: Math.round((Number.isFinite(value) ? value : 0) * 100),
          stage: "new",
          pause_ai: true,
        }),
      });
      if (result.thread_status) {
        setThreads((prev) =>
          prev.map((t) =>
            t.id === selectedThread
              ? { ...t, status: result.thread_status as string }
              : t,
          ),
        );
      }
      setCrmOpen(false);
      setMessage(
        result.message ||
          `Oportunidade “${result.opportunity.company}” criada no CRM.`,
      );
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function sendTemplate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedThread || !selectedTemplate) return;
    setBusy(true);
    setError("");
    setMessage("");
    try {
      await apiJson(`/api/v1/inbox/threads/${selectedThread}/template`, {
        method: "POST",
        body: JSON.stringify({
          template_name: selectedTemplate,
          language: templateLang,
          body_params: templateParams.filter((p) => p.trim()),
        }),
      });
      setMessage(`Template “${selectedTemplate}” enviado.`);
      await openThread(selectedThread);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  const activeThread = threads.find((t) => t.id === selectedThread);
  const threadStatusLabel =
    activeThread?.status === "human"
      ? "Atendente humano"
      : activeThread?.status === "closed"
        ? "Encerrada"
        : "IA ativa";
  const activeTemplate = useMemo(
    () => templates.find((t) => t.name === selectedTemplate),
    [templates, selectedTemplate],
  );
  const providerLabel = (p?: string) =>
    p === "meta" ? "Meta oficial" : p === "evolution" ? "Evolution" : "Webhook";
  const metaChannel = channels.find((c) => c.provider === "meta");

  return (
    <>
      <header>
        <div>
          <span>INBOX</span>
          <h1>WhatsApp</h1>
        </div>
        <button type="button" className="secondary" onClick={() => void load()}>
          Atualizar
        </button>
      </header>
      {error && <p className="error">{error}</p>}
      {message && <p className="success">{message}</p>}
      {evolutionInfo && <p className="success">{evolutionInfo}</p>}
      {qrImage && (
        <div className="secret-box">
          <strong>QR Code WhatsApp</strong>
          <img
            src={
              qrImage.startsWith("data:")
                ? qrImage
                : `data:image/png;base64,${qrImage}`
            }
            alt="QR Code WhatsApp"
            style={{
              width: 260,
              height: 260,
              background: "#fff",
              borderRadius: 8,
              padding: 8,
            }}
          />
          <small>
            WhatsApp do celular → Aparelhos conectados → Conectar aparelho. O QR
            expira em ~1 minuto; use &quot;Gerar QR&quot; para renovar.
          </small>
        </div>
      )}
      {qrInfo && !qrImage && <p className="success">{qrInfo}</p>}
      {metaInfo && (
        <div className="secret-box">
          <strong>Webhook Meta — copie agora</strong>
          <p style={{ margin: "8px 0", opacity: 0.9 }}>{metaInfo.message}</p>
          <small>Callback URL</small>
          <code>{metaInfo.webhook_url}</code>
          <small style={{ display: "block", marginTop: 8 }}>Verify token</small>
          <code>{metaInfo.verify_token}</code>
          <small>
            No Meta for Developers → seu app → WhatsApp → Configuration →
            Webhook: cole URL + token e assine o campo <em>messages</em>.
          </small>
        </div>
      )}

      <div className="content-grid">
        <article className="panel">
          <div className="panel-title">
            <div>
              <span>CONVERSAS</span>
              <h2>Caixa de entrada</h2>
            </div>
          </div>
          {threads.length === 0 ? (
            <div className="empty">
              <strong>Nenhuma conversa</strong>
              <p>Conecte o WhatsApp oficial (Meta) ou Evolution para receber mensagens.</p>
            </div>
          ) : (
            threads.map((thread) => (
              <div
                className="inbox-thread"
                key={thread.id}
                role="button"
                tabIndex={0}
                onClick={() => void openThread(thread.id)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") void openThread(thread.id);
                }}
                style={{
                  cursor: "pointer",
                  outline:
                    selectedThread === thread.id
                      ? "1px solid var(--teal)"
                      : undefined,
                }}
              >
                <div className="agent-icon">W</div>
                <div>
                  <strong>{thread.contact_name}</strong>
                  <small>
                    {thread.phone} · {thread.channel}
                    {thread.status === "human"
                      ? " · humano"
                      : thread.status === "closed"
                        ? " · encerrada"
                        : " · IA"}
                  </small>
                </div>
                {thread.unread_count > 0 && <span>{thread.unread_count}</span>}
              </div>
            ))
          )}

          {selectedThread && (
            <>
              <div className="panel-title" style={{ marginTop: "1.5rem" }}>
                <div>
                  <span>CONVERSA · {threadStatusLabel}</span>
                  <h2>{activeThread?.contact_name ?? "Mensagens"}</h2>
                </div>
              </div>
              <div
                className="proposal-actions"
                style={{ flexWrap: "wrap", marginBottom: 12 }}
              >
                {activeThread?.status !== "human" && (
                  <button
                    type="button"
                    disabled={busy}
                    onClick={() => void setThreadStatus("human")}
                  >
                    Atendente humano
                  </button>
                )}
                {activeThread?.status !== "open" && (
                  <button
                    type="button"
                    className="primary"
                    disabled={busy}
                    onClick={() => void setThreadStatus("open")}
                  >
                    Retomar IA
                  </button>
                )}
                {activeThread?.status !== "closed" && (
                  <button
                    type="button"
                    disabled={busy}
                    onClick={() => void setThreadStatus("closed")}
                  >
                    Encerrar
                  </button>
                )}
                <button
                  type="button"
                  className="primary"
                  disabled={busy}
                  onClick={() => setCrmOpen((v) => !v)}
                >
                  {crmOpen ? "Cancelar CRM" : "Criar no CRM"}
                </button>
                <Link className="secondary" href="/app/crm">
                  Abrir CRM
                </Link>
              </div>
              {crmOpen && activeThread && (
                <form
                  onSubmit={createCrmFromThread}
                  style={{
                    display: "grid",
                    gap: 10,
                    marginBottom: 14,
                    padding: 12,
                    border: "1px solid rgba(0,0,0,.08)",
                    borderRadius: 10,
                  }}
                >
                  <p style={{ margin: 0, opacity: 0.85, lineHeight: 1.45 }}>
                    Cria oportunidade em Novos com origem WhatsApp e pausa a IA
                    nesta conversa.
                  </p>
                  <label>
                    Empresa / lead
                    <input
                      name="company"
                      defaultValue={activeThread.contact_name}
                      minLength={2}
                      required
                    />
                  </label>
                  <label>
                    Valor estimado (R$)
                    <input
                      name="value"
                      type="number"
                      min="0"
                      step="0.01"
                      defaultValue="0"
                    />
                  </label>
                  <button className="primary" disabled={busy} type="submit">
                    {busy ? "Criando…" : "Salvar no pipeline"}
                  </button>
                </form>
              )}
              <p style={{ marginTop: 0, marginBottom: 12, opacity: 0.85, lineHeight: 1.45 }}>
                {activeThread?.status === "human"
                  ? "IA pausada — só você responde nesta conversa."
                  : activeThread?.status === "closed"
                    ? "Conversa encerrada. Nova mensagem do cliente reabre com IA."
                    : "IA responde automaticamente. Ao enviar mensagem manual, a IA pausa."}
              </p>
              {messages.length === 0 ? (
                <div className="empty">Sem mensagens nesta conversa.</div>
              ) : (
                messages.map((msg) => (
                  <div className="activity-row" key={msg.id}>
                    <div className="activity-dot" />
                    <div>
                      <strong>
                        {msg.direction === "inbound" ? "Recebida" : "Enviada"}
                      </strong>
                      {msg.status === "failed" && (
                        <span
                          style={{
                            color: "#c0392b",
                            marginLeft: 8,
                            fontWeight: 600,
                          }}
                        >
                          falhou ao enviar
                        </span>
                      )}
                      {msg.status === "queued" && (
                        <span style={{ color: "#8a9692", marginLeft: 8 }}>
                          na fila
                        </span>
                      )}
                      <small>{msg.content}</small>
                    </div>
                    <time>{formatDateTime(msg.created_at)}</time>
                  </div>
                ))
              )}
              <form onSubmit={sendMessage}>
                <label>
                  Resposta (janela 24h)
                  <textarea name="text" required minLength={1} />
                </label>
                <button className="primary" disabled={busy}>
                  Enviar mensagem
                </button>
              </form>
              {activeThread?.provider === "meta" && (
                <form
                  onSubmit={sendTemplate}
                  style={{ marginTop: 16, display: "grid", gap: 8 }}
                >
                  <div className="panel-title" style={{ margin: 0 }}>
                    <div>
                      <span>TEMPLATE META</span>
                      <h2 style={{ fontSize: 16 }}>Fora da janela 24h</h2>
                    </div>
                    {activeThread.channel_id && (
                      <button
                        type="button"
                        onClick={() =>
                          void loadTemplates(activeThread.channel_id!)
                        }
                      >
                        Atualizar lista
                      </button>
                    )}
                  </div>
                  <p style={{ margin: 0, opacity: 0.85, lineHeight: 1.45 }}>
                    Templates aprovados na Meta permitem iniciar conversa
                    (cobrança, follow-up).{" "}
                    {templatesSource === "suggested"
                      ? "Lista sugerida — crie no Business Manager com o mesmo nome."
                      : "Lista da sua WABA."}
                  </p>
                  {templatesHint && (
                    <small style={{ opacity: 0.8 }}>{templatesHint}</small>
                  )}
                  <label>
                    Template
                    <select
                      value={selectedTemplate}
                      onChange={(e) => {
                        const name = e.target.value;
                        setSelectedTemplate(name);
                        const tpl = templates.find((t) => t.name === name);
                        setTemplateLang(tpl?.language || "pt_BR");
                        setTemplateParams(
                          Array.from(
                            { length: tpl?.body_param_count || 0 },
                            () => "",
                          ),
                        );
                      }}
                      required
                    >
                      <option value="">Selecione</option>
                      {templates.map((t) => (
                        <option key={`${t.name}-${t.language}`} value={t.name}>
                          {t.name} ({t.language})
                          {t.status === "SUGGESTED" ? " · sugerido" : ""}
                        </option>
                      ))}
                    </select>
                  </label>
                  {activeTemplate?.blurb && (
                    <small style={{ opacity: 0.85 }}>{activeTemplate.blurb}</small>
                  )}
                  <label>
                    Idioma
                    <input
                      value={templateLang}
                      onChange={(e) => setTemplateLang(e.target.value)}
                      required
                    />
                  </label>
                  {templateParams.map((val, i) => (
                    <label key={`p-${i}`}>
                      Variável {i + 1}
                      {activeTemplate?.param_hints?.[i]
                        ? ` (${activeTemplate.param_hints[i]})`
                        : ""}
                      <input
                        value={val}
                        onChange={(e) => {
                          const next = [...templateParams];
                          next[i] = e.target.value;
                          setTemplateParams(next);
                        }}
                        required
                      />
                    </label>
                  ))}
                  <button className="primary" disabled={busy || !selectedTemplate}>
                    Enviar template
                  </button>
                </form>
              )}
            </>
          )}
        </article>

        <div style={{ display: "grid", gap: 18 }}>
          <article className="panel">
            <div className="panel-title">
              <div>
                <span>RECOMENDADO</span>
                <h2>WhatsApp oficial (Meta)</h2>
              </div>
            </div>
            <p style={{ marginTop: 0, opacity: 0.85, lineHeight: 1.5 }}>
              Sem risco de ban por cliente não oficial. Você (dono) cria o app
              na Meta, verifica o negócio e cola aqui o Phone Number ID e o
              token. A OperAI recebe e responde via Cloud API.
            </p>
            <ol style={{ margin: "0 0 12px", paddingLeft: 18, opacity: 0.9, lineHeight: 1.55 }}>
              <li>
                Abra{" "}
                <a
                  href="https://developers.facebook.com/apps/"
                  target="_blank"
                  rel="noreferrer"
                >
                  Meta for Developers
                </a>{" "}
                → app com produto WhatsApp
              </li>
              <li>Copie Phone number ID e Access token temporário (ou permanente)</li>
              <li>Salve aqui e configure o webhook com a URL/token que mostramos</li>
            </ol>
            <form onSubmit={connectMeta}>
              <label>
                Nome do canal
                <input
                  name="name"
                  required
                  minLength={2}
                  placeholder="WhatsApp Comercial"
                  defaultValue="WhatsApp Oficial"
                />
              </label>
              <label>
                Phone Number ID
                <input
                  name="phone_number_id"
                  required
                  pattern="[0-9]+"
                  placeholder="Ex.: 123456789012345"
                />
              </label>
              <label>
                Access token
                <input
                  name="access_token"
                  type="password"
                  required
                  minLength={20}
                  autoComplete="off"
                  placeholder="Token da Meta"
                />
              </label>
              <label>
                WABA ID (recomendado para templates)
                <input name="waba_id" placeholder="WhatsApp Business Account ID" />
              </label>
              <button className="primary" disabled={busy}>
                Conectar Meta Cloud API
              </button>
            </form>
            {metaChannel && (
              <p className="pricing-note" style={{ marginTop: 12 }}>
                Canal Meta ativo. Abra uma conversa para enviar templates fora
                da janela de 24h.
              </p>
            )}
          </article>

          <article className="panel">
            <div className="panel-title">
              <div>
                <span>ALTERNATIVA</span>
                <h2>Evolution (QR)</h2>
              </div>
            </div>
            <p style={{ marginTop: 0, opacity: 0.85, lineHeight: 1.5 }}>
              Conexão por QR (Baileys). Mais rápida para testar, mas não é a API
              oficial — use com conta dedicada e consciência do risco.
            </p>
            <form onSubmit={connectEvolution}>
              <label>
                Nome do canal
                <input
                  name="name"
                  required
                  minLength={2}
                  placeholder="WhatsApp Comercial"
                />
              </label>
              <label>
                Instância
                <input
                  name="instance_name"
                  required
                  minLength={2}
                  pattern="[a-zA-Z0-9_-]+"
                  placeholder="empresa_01"
                />
              </label>
              <button className="secondary" disabled={busy}>
                Conectar Evolution
              </button>
            </form>
            {channels.length > 0 && (
              <div style={{ marginTop: 16 }}>
                {channels.map((ch) => (
                  <div className="knowledge-doc" key={ch.id}>
                    <div>
                      <strong>{ch.name}</strong>
                      <small>
                        {providerLabel(ch.provider)} · {ch.external_key}
                      </small>
                    </div>
                    <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                      <span>{ch.active ? "ativo" : "off"}</span>
                      {(ch.provider ?? "webhook") === "evolution" && (
                        <button
                          type="button"
                          onClick={() => void fetchQr(ch)}
                          disabled={busy}
                        >
                          Gerar QR
                        </button>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </article>

          <article className="panel">
            <div className="panel-title">
              <div>
                <span>AVANÇADO</span>
                <h2>Webhook manual</h2>
              </div>
            </div>
            <form onSubmit={createChannel}>
              <label>
                Nome do canal
                <input name="name" required minLength={2} />
              </label>
              <label>
                Chave externa
                <input
                  name="external_key"
                  required
                  pattern="[a-zA-Z0-9_-]+"
                  placeholder="empresa_whatsapp_01"
                />
              </label>
              <button className="secondary" disabled={busy}>
                Criar canal
              </button>
            </form>
            {channelSecret && (
              <div className="secret-box">
                <strong>Segredo do webhook</strong>
                <code>{channelSecret}</code>
                <small>Copie agora. Ele não será exibido novamente.</small>
              </div>
            )}
          </article>
        </div>
      </div>
    </>
  );
}
