"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { apiJson } from "../../lib/api";
import { formatDateTime } from "../../lib/format";
import type { Channel, InboxMessage, InboxThread } from "../../lib/types";

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
  const [busy, setBusy] = useState(false);

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
    setError("");
    try {
      setMessages(
        await apiJson<InboxMessage[]>(
          `/api/v1/inbox/threads/${threadId}/messages`,
        ),
      );
      await load();
    } catch (e) {
      setError((e as Error).message);
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
      await openThread(selectedThread);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  const activeThread = threads.find((t) => t.id === selectedThread);
  const providerLabel = (p?: string) =>
    p === "meta" ? "Meta oficial" : p === "evolution" ? "Evolution" : "Webhook";

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
                  <span>CONVERSA</span>
                  <h2>{activeThread?.contact_name ?? "Mensagens"}</h2>
                </div>
              </div>
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
                  Resposta
                  <textarea name="text" required minLength={1} />
                </label>
                <button className="primary" disabled={busy}>
                  Enviar mensagem
                </button>
              </form>
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
                WABA ID (opcional)
                <input name="waba_id" placeholder="WhatsApp Business Account ID" />
              </label>
              <button className="primary" disabled={busy}>
                Conectar Meta Cloud API
              </button>
            </form>
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
