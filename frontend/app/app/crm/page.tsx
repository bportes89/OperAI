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
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [draggingId, setDraggingId] = useState<string | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);

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

  const editing = items.find((i) => i.id === editingId) ?? null;

  async function createOpportunity(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setMessage("");
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
      setMessage("Oportunidade adicionada ao pipeline.");
      await load();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function saveOpportunity(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!editingId) return;
    setBusy(true);
    setError("");
    setMessage("");
    const data = Object.fromEntries(new FormData(event.currentTarget));
    try {
      const updated = await apiJson<Opportunity>(
        `/api/v1/opportunities/${editingId}`,
        {
          method: "PATCH",
          body: JSON.stringify({
            company: data.company,
            contact: data.contact,
            stage: data.stage,
            value_cents: Math.round(Number(data.value) * 100),
            source_channel: data.source_channel || null,
            source_title: data.source_title || null,
          }),
        },
      );
      setItems((prev) =>
        prev.map((i) => (i.id === updated.id ? { ...i, ...updated } : i)),
      );
      setMessage(`“${updated.company}” atualizada.`);
      setEditingId(null);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function removeOpportunity() {
    if (!editingId || !editing) return;
    if (
      !window.confirm(
        `Remover “${editing.company}” do pipeline? Esta ação não desfaz.`,
      )
    ) {
      return;
    }
    setBusy(true);
    setError("");
    setMessage("");
    try {
      await apiJson(`/api/v1/opportunities/${editingId}`, { method: "DELETE" });
      setItems((prev) => prev.filter((i) => i.id !== editingId));
      setMessage(`“${editing.company}” removida.`);
      setEditingId(null);
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
      setItems((prev) =>
        prev.map((i) => (i.id === id ? { ...i, ...updated } : i)),
      );
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
      {message && <p className="success">{message}</p>}

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
          Arraste o card entre colunas, mude a etapa pelos botões ou abra{" "}
          <strong>Editar</strong> para alterar valor, contato e origem.
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
                        className={`kanban-card${draggingId === item.id ? " dragging" : ""}${editingId === item.id ? " selected" : ""}`}
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
                          <button
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation();
                              setEditingId(item.id);
                              setMessage("");
                              setError("");
                            }}
                          >
                            Editar
                          </button>
                          {STAGES.filter((s) => s.id !== item.stage).map((s) => (
                            <button
                              key={s.id}
                              type="button"
                              onClick={(e) => {
                                e.stopPropagation();
                                void moveStage(item.id, s.id);
                              }}
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

      {editing && (
        <article className="panel" id="edit-opportunity" style={{ marginBottom: 18 }}>
          <div className="panel-title">
            <div>
              <span>EDITAR</span>
              <h2>{editing.company}</h2>
            </div>
            <button type="button" onClick={() => setEditingId(null)}>
              Fechar
            </button>
          </div>
          <form
            key={editing.id}
            onSubmit={saveOpportunity}
            className="crm-create-form"
          >
            <label>
              Empresa
              <input
                name="company"
                required
                minLength={2}
                defaultValue={editing.company}
              />
            </label>
            <label>
              Contato
              <input
                name="contact"
                required
                minLength={2}
                defaultValue={editing.contact}
              />
            </label>
            <label>
              Etapa
              <select name="stage" defaultValue={editing.stage}>
                {STAGES.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.label}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Valor (R$)
              <input
                name="value"
                type="number"
                min="0"
                step="0.01"
                required
                defaultValue={(editing.value_cents / 100).toFixed(2)}
              />
            </label>
            <label>
              Origem
              <select
                name="source_channel"
                defaultValue={editing.source_channel || ""}
              >
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
              Peça / campanha
              <input
                name="source_title"
                defaultValue={editing.source_title || ""}
                placeholder="Ex.: Post Convite WhatsApp"
              />
            </label>
            <div className="proposal-actions" style={{ flexWrap: "wrap" }}>
              <button className="primary" disabled={busy} type="submit">
                {busy ? "Salvando…" : "Salvar alterações"}
              </button>
              <button
                type="button"
                disabled={busy}
                onClick={() => void removeOpportunity()}
              >
                Remover do pipeline
              </button>
            </div>
          </form>
        </article>
      )}

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
