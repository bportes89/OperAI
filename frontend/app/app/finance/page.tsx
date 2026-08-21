"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { apiJson } from "../../lib/api";
import { money } from "../../lib/format";
import type { FinanceSummary, Receivable } from "../../lib/types";

export default function FinancePage() {
  const [receivables, setReceivables] = useState<Receivable[]>([]);
  const [summary, setSummary] = useState<FinanceSummary>({
    pending_cents: 0,
    overdue_cents: 0,
    paid_cents: 0,
    total_count: 0,
  });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      setError("");
      const [list, sum] = await Promise.all([
        apiJson<Receivable[]>("/api/v1/finance/receivables"),
        apiJson<FinanceSummary>("/api/v1/finance/summary"),
      ]);
      setReceivables(list);
      setSummary(sum);
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
    try {
      await apiJson("/api/v1/finance/receivables", {
        method: "POST",
        body: JSON.stringify({
          customer_name: data.customer_name,
          description: data.description,
          amount_cents: Math.round(Number(data.amount) * 100),
          due_date: data.due_date,
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

  return (
    <>
      <header>
        <div>
          <span>FINANCEIRO</span>
          <h1>Cobrança</h1>
        </div>
      </header>
      {error && <p className="error">{error}</p>}

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
          <small>baixas confirmadas</small>
        </article>
      </div>

      <div className="content-grid">
        <article className="panel">
          <div className="panel-title">
            <div>
              <span>CONTAS A RECEBER</span>
              <h2>Cobranças</h2>
            </div>
          </div>
          {receivables.length === 0 ? (
            <div className="empty">
              <strong>Nenhuma cobrança</strong>
              <p>Lance um recebível para acompanhar pagamentos.</p>
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
                  </small>
                </div>
                <b>{money(item.amount_cents)}</b>
                <span className={`finance-status ${item.status}`}>
                  {item.status}
                </span>
                {item.status !== "paid" && (
                  <button type="button" onClick={() => void payReceivable(item)}>
                    Baixar via Pix
                  </button>
                )}
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
    </>
  );
}
