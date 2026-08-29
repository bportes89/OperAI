"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { apiJson } from "../../lib/api";
import { formatDateTime, money } from "../../lib/format";
import type { FinanceFollowUp, FinanceSummary, Receivable } from "../../lib/types";

const STATUS_LABEL: Record<string, string> = {
  pending: "Em aberto",
  overdue: "Em atraso",
  paid: "Pago",
};

const TONE_LABEL: Record<string, string> = {
  reminder: "Lembrete prévio",
  due_today: "Vence hoje",
  overdue_soft: "Atraso recente",
  negotiate: "Negociação",
};

export default function FinancePage() {
  const [receivables, setReceivables] = useState<Receivable[]>([]);
  const [followUps, setFollowUps] = useState<FinanceFollowUp[]>([]);
  const [summary, setSummary] = useState<FinanceSummary>({
    pending_cents: 0,
    overdue_cents: 0,
    paid_cents: 0,
    total_count: 0,
    whatsapp_ready: false,
  });
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [draftingId, setDraftingId] = useState<string | null>(null);
  const [sendingId, setSendingId] = useState<string | null>(null);
  const [lastDraft, setLastDraft] = useState("");

  const load = useCallback(async () => {
    try {
      setError("");
      const [list, sum, drafts] = await Promise.all([
        apiJson<Receivable[]>("/api/v1/finance/receivables"),
        apiJson<FinanceSummary>("/api/v1/finance/summary"),
        apiJson<FinanceFollowUp[]>("/api/v1/finance/follow-ups").catch(() => []),
      ]);
      setReceivables(list);
      setSummary(sum);
      setFollowUps(drafts);
    } catch (e) {
      setError((e as Error).message);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function createReceivable(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    const form = event.currentTarget;
    const data = Object.fromEntries(new FormData(form));
    const phone = String(data.phone || "").trim();
    try {
      await apiJson("/api/v1/finance/receivables", {
        method: "POST",
        body: JSON.stringify({
          customer_name: data.customer_name,
          description: data.description,
          amount_cents: Math.round(Number(data.amount) * 100),
          due_date: data.due_date,
          phone: phone || null,
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

  async function payReceivable(item: Receivable) {
    try {
      await apiJson(`/api/v1/finance/receivables/${item.id}/payments`, {
        method: "POST",
        body: JSON.stringify({
          amount_cents: item.amount_cents,
          method: "pix",
        }),
      });
      await load();
    } catch (e) {
      setError((e as Error).message);
    }
  }

  async function draftFollowUp(item: Receivable) {
    setDraftingId(item.id);
    setError("");
    setMessage("");
    try {
      const result = await apiJson<{ message: string; tone?: string }>(
        `/api/v1/finance/receivables/${item.id}/follow-up`,
        { method: "POST" },
      );
      setLastDraft(result.message);
      setMessage(
        `Lembrete pronto (${TONE_LABEL[result.tone ?? ""] ?? "follow-up"}). Envie no WhatsApp ou copie.`,
      );
      await load();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setDraftingId(null);
    }
  }

  async function sendWhatsApp(item: Receivable) {
    setSendingId(item.id);
    setError("");
    setMessage("");
    let phone = item.phone || "";
    if (!phone) {
      const typed = window.prompt(
        "WhatsApp do cliente (DDI+DDD+número, ex.: 5511999999999):",
        "",
      );
      if (!typed) {
        setSendingId(null);
        return;
      }
      phone = typed.trim();
    }
    try {
      const result = await apiJson<{
        message: string;
        provider?: string;
        phone?: string;
      }>(`/api/v1/finance/receivables/${item.id}/follow-up/send`, {
        method: "POST",
        body: JSON.stringify({ phone }),
      });
      setLastDraft(result.message);
      setMessage(
        `Enviado via ${result.provider === "meta" ? "WhatsApp oficial" : "Evolution"} para ${result.phone}.`,
      );
      await load();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setSendingId(null);
    }
  }

  async function runBatchFollowUps() {
    setBusy(true);
    setError("");
    setMessage("");
    try {
      const result = await apiJson<{ drafted: number; skipped: number }>(
        "/api/v1/finance/follow-ups/run",
        { method: "POST" },
      );
      setMessage(
        `${result.drafted} lembrete(s) gerado(s)${result.skipped ? ` · ${result.skipped} ignorado(s)` : ""}.`,
      );
      await load();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function copyText(text: string) {
    try {
      await navigator.clipboard.writeText(text);
      setMessage("Mensagem copiada.");
    } catch {
      setError("Não foi possível copiar. Selecione o texto manualmente.");
    }
  }

  return (
    <>
      <header>
        <div>
          <span>FINANCEIRO</span>
          <h1>Cobrança</h1>
        </div>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          <Link className="secondary" href="/app/inbox">
            WhatsApp
          </Link>
          <button
            type="button"
            className="primary"
            disabled={busy}
            onClick={() => void runBatchFollowUps()}
          >
            {busy ? "Gerando…" : "Rodar follow-ups"}
          </button>
        </div>
      </header>
      {error && <p className="error">{error}</p>}
      {message && <p className="success">{message}</p>}
      {!summary.whatsapp_ready && (
        <p className="pricing-note">
          Para envio automático, conecte WhatsApp oficial (Meta) ou Evolution em{" "}
          <Link href="/app/inbox">WhatsApp</Link>. Sem canal, ainda dá para
          gerar e copiar o lembrete.
        </p>
      )}

      <div className="metrics">
        <article>
          <span>Em aberto</span>
          <strong>{money(summary.pending_cents)}</strong>
          <small>{summary.total_count} títulos</small>
        </article>
        <article>
          <span>Em atraso</span>
          <strong>{money(summary.overdue_cents)}</strong>
          <small>inadimplência atual</small>
        </article>
        <article>
          <span>Recebido</span>
          <strong>{money(summary.paid_cents)}</strong>
          <small>
            {summary.whatsapp_ready ? "WhatsApp pronto" : "sem canal WA"}
          </small>
        </article>
      </div>

      {lastDraft && (
        <article className="panel" style={{ marginBottom: 18 }}>
          <div className="panel-title">
            <div>
              <span>ÚLTIMA MENSAGEM</span>
              <h2>Lembrete de cobrança</h2>
            </div>
            <button type="button" onClick={() => void copyText(lastDraft)}>
              Copiar
            </button>
          </div>
          <p style={{ whiteSpace: "pre-wrap", lineHeight: 1.55, margin: 0 }}>
            {lastDraft}
          </p>
        </article>
      )}

      <div className="content-grid">
        <article className="panel">
          <div className="panel-title">
            <div>
              <span>CONTAS A RECEBER</span>
              <h2>Cobranças</h2>
            </div>
          </div>
          <p style={{ marginTop: 0, opacity: 0.85, lineHeight: 1.5 }}>
            Gere o texto no tom certo e envie no WhatsApp com um clique. A
            conversa também aparece na Inbox.
          </p>
          {receivables.length === 0 ? (
            <div className="empty">
              <strong>Nenhuma cobrança</strong>
              <p>Lance um recebível com WhatsApp do cliente para cobrar.</p>
            </div>
          ) : (
            receivables.map((item) => (
              <div className="finance-row" key={item.id}>
                <div>
                  <strong>{item.customer_name}</strong>
                  <small>
                    {item.description} · vence{" "}
                    {new Date(
                      item.due_date + "T12:00:00",
                    ).toLocaleDateString("pt-BR")}
                    {item.phone ? ` · ${item.phone}` : ""}
                  </small>
                </div>
                <b>{money(item.amount_cents)}</b>
                <span className={`finance-status ${item.status}`}>
                  {STATUS_LABEL[item.status] ?? item.status}
                </span>
                {item.status !== "paid" && (
                  <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                    <button
                      type="button"
                      className="primary"
                      disabled={sendingId === item.id || !summary.whatsapp_ready}
                      onClick={() => void sendWhatsApp(item)}
                      title={
                        summary.whatsapp_ready
                          ? "Enviar lembrete no WhatsApp"
                          : "Conecte um canal WhatsApp primeiro"
                      }
                    >
                      {sendingId === item.id ? "Enviando…" : "Enviar WhatsApp"}
                    </button>
                    <button
                      type="button"
                      disabled={draftingId === item.id}
                      onClick={() => void draftFollowUp(item)}
                    >
                      {draftingId === item.id ? "Gerando…" : "Só gerar"}
                    </button>
                    <button type="button" onClick={() => void payReceivable(item)}>
                      Baixar via Pix
                    </button>
                  </div>
                )}
              </div>
            ))
          )}
        </article>

        <div style={{ display: "grid", gap: 18 }}>
          <article className="panel">
            <div className="panel-title">
              <div>
                <span>AGENTE</span>
                <h2>Follow-ups recentes</h2>
              </div>
            </div>
            {followUps.length === 0 ? (
              <div className="empty">
                <strong>Nenhum lembrete ainda</strong>
                <p>
                  Use &quot;Enviar WhatsApp&quot; ou &quot;Rodar follow-ups&quot;.
                </p>
              </div>
            ) : (
              followUps.slice(0, 8).map((fu) => (
                <div
                  className="activity-row"
                  key={fu.id}
                  style={{ alignItems: "start" }}
                >
                  <div className="activity-dot" />
                  <div>
                    <strong>
                      {fu.customer_name || fu.title}
                      {fu.tone ? ` · ${TONE_LABEL[fu.tone] ?? fu.tone}` : ""}
                    </strong>
                    <small style={{ whiteSpace: "pre-wrap" }}>
                      {fu.message.length > 220
                        ? `${fu.message.slice(0, 220)}…`
                        : fu.message}
                    </small>
                    <button
                      type="button"
                      style={{ marginTop: 6 }}
                      onClick={() => void copyText(fu.message)}
                    >
                      Copiar mensagem
                    </button>
                  </div>
                  <time>
                    {fu.created_at ? formatDateTime(fu.created_at) : ""}
                  </time>
                </div>
              ))
            )}
          </article>

          <article className="panel">
            <div className="panel-title">
              <div>
                <span>NOVA</span>
                <h2>Lançar recebível</h2>
              </div>
            </div>
            <form onSubmit={createReceivable}>
              <label>
                Cliente
                <input name="customer_name" required minLength={2} />
              </label>
              <label>
                WhatsApp (opcional)
                <input
                  name="phone"
                  placeholder="5511999999999"
                  pattern="[0-9+\s()-]{8,30}"
                />
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
                  min="0.01"
                  step="0.01"
                  required
                />
              </label>
              <label>
                Vencimento
                <input name="due_date" type="date" required />
              </label>
              <button className="primary" disabled={busy}>
                Criar cobrança
              </button>
            </form>
          </article>
        </div>
      </div>
    </>
  );
}
