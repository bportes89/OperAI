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
      form.reset();
      await load();
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
            expira em ~1 minuto; use "Gerar QR" para renovar.
          </small>
        </div>
      )}
      {qrInfo && !qrImage && <p className="success">{qrInfo}</p>}

      <div className="content-grid">
        <article className="panel">
          <div className="panel-title">
            <div>
              <span>CONVERSAS</span>
              <h2>Threads</h2>
            </div>
          </div>
          {threads.length === 0 ? (
            <div className="empty">
              <strong>Nenhuma conversa</strong>
              <p>Conecte o WhatsApp para receber mensagens aqui.</p>
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
                  <span>THREAD</span>
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
                <span>EVOLUTION</span>
                <h2>Conectar WhatsApp</h2>
              </div>
            </div>
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
              <button className="primary" disabled={busy}>
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
                        {ch.provider ?? "webhook"} · {ch.external_key}
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
                <span>WEBHOOK</span>
                <h2>Canal manual</h2>
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
              <button className="primary" disabled={busy}>
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
