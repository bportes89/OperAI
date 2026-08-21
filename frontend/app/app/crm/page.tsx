"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { apiJson } from "../../lib/api";
import { money } from "../../lib/format";
import type { Opportunity } from "../../lib/types";

export default function CrmPage() {
  const [items, setItems] = useState<Opportunity[]>([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      setError("");
      setItems(await apiJson<Opportunity[]>("/api/v1/opportunities"));
    } catch (e) {
      setError((e as Error).message);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function createOpportunity(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    const form = event.currentTarget;
    const data = Object.fromEntries(new FormData(form));
    try {
      await apiJson("/api/v1/opportunities", {
        method: "POST",
        body: JSON.stringify({
          company: data.company,
          contact: data.contact,
          stage: data.stage,
          value_cents: Math.round(Number(data.value) * 100),
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

  const total = items.reduce((sum, item) => sum + item.value_cents, 0);

  return (
    <>
      <header>
        <div>
          <span>VENDAS</span>
          <h1>CRM</h1>
        </div>
      </header>
      {error && <p className="error">{error}</p>}

      <div className="metrics">
        <article>
          <span>Oportunidades</span>
          <strong>{items.length}</strong>
          <small>pipeline ativo</small>
        </article>
        <article>
          <span>Valor no pipeline</span>
          <strong>{money(total)}</strong>
          <small>potencial comercial</small>
        </article>
        <article>
          <span>Ganhos</span>
          <strong>{items.filter((i) => i.stage === "won").length}</strong>
          <small>negócios fechados</small>
        </article>
      </div>

      <div className="content-grid">
        <article className="panel">
          <div className="panel-title">
            <div>
              <span>PIPELINE</span>
              <h2>Oportunidades</h2>
            </div>
            <button type="button" onClick={() => void load()}>
              Atualizar
            </button>
          </div>
          {items.length === 0 ? (
            <div className="empty">
              <strong>Pipeline vazio</strong>
              <p>Cadastre a primeira oportunidade comercial.</p>
            </div>
          ) : (
            <div className="table">
              {items.map((item) => (
                <div className="row" key={item.id}>
                  <div>
                    <strong>{item.company}</strong>
                    <small>{item.contact}</small>
                  </div>
                  <span className="stage">{item.stage}</span>
                  <b>{money(item.value_cents)}</b>
                </div>
              ))}
            </div>
          )}
        </article>

        <article className="panel">
          <div className="panel-title">
            <div>
              <span>NOVO</span>
              <h2>Criar oportunidade</h2>
            </div>
          </div>
          <form onSubmit={createOpportunity}>
            <label>
              Empresa
              <input name="company" required minLength={2} />
            </label>
            <label>
              Contato
              <input name="contact" required minLength={2} />
            </label>
            <label>
              Etapa
              <select name="stage" defaultValue="new">
                <option value="new">Novo</option>
                <option value="qualified">Qualificado</option>
                <option value="proposal">Proposta</option>
                <option value="won">Ganho</option>
              </select>
            </label>
            <label>
              Valor (R$)
              <input name="value" type="number" min="0" step="0.01" required />
            </label>
            <button className="primary" disabled={busy}>
              Adicionar ao pipeline
            </button>
          </form>
        </article>
      </div>
    </>
  );
}
