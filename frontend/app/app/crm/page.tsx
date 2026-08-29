"use client";

import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { apiJson } from "../../lib/api";
import { money } from "../../lib/format";
import type { Opportunity } from "../../lib/types";

const STAGES = [
  { id: "new", label: "Novos" },
  { id: "qualified", label: "Qualificados" },
  { id: "proposal", label: "Proposta" },
  { id: "won", label: "Ganhos" },
  { id: "lost", label: "Perdidos" },
] as const;

const CHANNEL_LABEL: Record<string, string> = {
  social: "Rede social",
  email: "E-mail",
  whatsapp: "WhatsApp",
  google: "Google",
  ads: "Anúncio",
  other: "Outro",
};

export default function CrmPage() {
  const [items, setItems] = useState<Opportunity[]>([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [draggingId, setDraggingId] = useState<string | null>(null);

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
          source_channel: data.source_channel || null,
          source_title: data.source_title || null,
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

  async function moveStage(id: string, stage: string) {
    const current = items.find((i) => i.id === id);
    if (!current || current.stage === stage) return;
    setItems((prev) =>
      prev.map((i) => (i.id === id ? { ...i, stage } : i)),
    );
    try {
      const updated = await apiJson<Opportunity>(
        `/api/v1/opportunities/${id}/stage`,
        { method: "PATCH", body: JSON.stringify({ stage }) },
      );
      setItems((prev) => prev.map((i) => (i.id === id ? { ...i, ...updated } : i)));
    } catch (e) {
      setError((e as Error).message);
      await load();
    }
  }

  const byStage = useMemo(() => {
    const map: Record<string, Opportunity[]> = {};
    for (const s of STAGES) map[s.id] = [];
    for (const item of items) {
      const key = map[item.stage] ? item.stage : "new";
      map[key].push(item);
    }
    return map;
  }, [items]);

  const total = items
    .filter((i) => i.stage !== "lost" && i.stage !== "won")
    .reduce((sum, item) => sum + item.value_cents, 0);

  function originLabel(item: Opportunity) {
    if (item.campaign_name) return `Campanha: ${item.campaign_name}`;
    if (item.source_title) return item.source_title;
    if (item.source_channel)
      return CHANNEL_LABEL[item.source_channel] ?? item.source_channel;
    return null;
  }

  return (
    <>
      <header>
        <div>
          <span>VENDAS</span>
          <h1>CRM</h1>
        </div>
        <Link className="secondary" href="/app/marketing">
          Marketing
        </Link>
      </header>
      {error && <p className="error">{error}</p>}

      <div className="metrics">
        <article>
          <span>No funil</span>
          <strong>
            {items.filter((i) => !["won", "lost"].includes(i.stage)).length}
          </strong>
          <small>oportunidades abertas</small>
        </article>
        <article>
          <span>Valor no pipeline</span>
          <strong>{money(total)}</strong>
          <small>sem ganhos/perdidos</small>
        </article>
        <article>
          <span>Ganhos</span>
          <strong>{items.filter((i) => i.stage === "won").length}</strong>
          <small>negócios fechados</small>
        </article>
      </div>

      <article className="panel" style={{ marginBottom: 18 }}>
        <div className="panel-title">
          <div>
            <span>KANBAN</span>
            <h2>Pipeline visual</h2>
          </div>
          <button type="button" onClick={() => void load()}>
            Atualizar
          </button>
        </div>
        <p style={{ marginTop: 0, opacity: 0.85, lineHeight: 1.5 }}>
          Arraste o card entre colunas ou use os botões de etapa. Interesses do
          Marketing entram em <strong>Novos</strong> com a origem da peça.
        </p>
        {items.length === 0 ? (
          <div className="empty">
            <strong>Pipeline vazio</strong>
            <p>
              Cadastre ao lado ou registre interesse no{" "}
              <Link href="/app/marketing">Marketing</Link>.
            </p>
          </div>
        ) : (
          <div className="kanban">
            {STAGES.map((col) => (
              <div
                key={col.id}
                className={`kanban-col${draggingId ? " drop-ready" : ""}`}
                onDragOver={(e) => {
                  e.preventDefault();
                  e.dataTransfer.dropEffect = "move";
                }}
                onDrop={(e) => {
                  e.preventDefault();
                  const id = e.dataTransfer.getData("text/opportunity-id");
                  setDraggingId(null);
                  if (id) void moveStage(id, col.id);
                }}
              >
                <div className="kanban-col-head">
                  <strong>{col.label}</strong>
                  <span>{byStage[col.id]?.length ?? 0}</span>
                </div>
                <div className="kanban-col-body">
                  {(byStage[col.id] ?? []).map((item) => {
                    const origin = originLabel(item);
                    return (
                      <div
                        key={item.id}
                        className={`kanban-card${draggingId === item.id ? " dragging" : ""}`}
                        draggable
                        onDragStart={(e) => {
                          e.dataTransfer.setData("text/opportunity-id", item.id);
                          e.dataTransfer.effectAllowed = "move";
                          setDraggingId(item.id);
                        }}
                        onDragEnd={() => setDraggingId(null)}
                      >
                        <strong>{item.company}</strong>
                        <small>{item.contact}</small>
                        <b>{money(item.value_cents)}</b>
                        {origin && (
                          <span className="kanban-origin" title={origin}>
                            {origin}
                          </span>
                        )}
                        <div className="kanban-move">
                          {STAGES.filter((s) => s.id !== item.stage).map((s) => (
                            <button
                              key={s.id}
                              type="button"
                              onClick={() => void moveStage(item.id, s.id)}
                            >
                              {s.label}
                            </button>
                          ))}
                        </div>
                      </div>
                    );
                  })}
                </div>
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
        <form onSubmit={createOpportunity} className="crm-create-form">
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
              {STAGES.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.label}
                </option>
              ))}
            </select>
          </label>
          <label>
            Valor (R$)
            <input name="value" type="number" min="0" step="0.01" required />
          </label>
          <label>
            Origem (opcional)
            <select name="source_channel" defaultValue="">
              <option value="">Manual / sem origem</option>
              <option value="social">Rede social</option>
              <option value="whatsapp">WhatsApp</option>
              <option value="email">E-mail</option>
              <option value="google">Google</option>
              <option value="ads">Anúncio</option>
              <option value="other">Outro</option>
            </select>
          </label>
          <label>
            Peça / campanha (opcional)
            <input name="source_title" placeholder="Ex.: Post Convite WhatsApp" />
          </label>
          <button className="primary" disabled={busy}>
            Adicionar ao pipeline
          </button>
        </form>
      </article>
    </>
  );
}
