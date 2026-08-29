"use client";

import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { apiJson } from "../../lib/api";
import { agentLabel } from "../../lib/format";
import { MarkdownLite } from "../../lib/markdown";
import type { Agent, AgentPreset, ChatResult } from "../../lib/types";

export default function AgentsPage() {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [presets, setPresets] = useState<AgentPreset[]>([]);
  const [chatResult, setChatResult] = useState<ChatResult | null>(null);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [history, setHistory] = useState<{ role: string; content: string }[]>(
    [],
  );
  const [selectedAgentId, setSelectedAgentId] = useState("");
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [activating, setActivating] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setError("");
      const [agentList, presetList] = await Promise.all([
        apiJson<Agent[]>("/api/v1/agents"),
        apiJson<AgentPreset[]>("/api/v1/agents/presets").catch(() => []),
      ]);
      setAgents(agentList);
      setPresets(presetList);
      const gestor = agentList.find((a) => a.agent_type === "marketing");
      setSelectedAgentId((prev) => {
        if (prev && agentList.some((a) => a.id === prev)) return prev;
        return gestor?.id ?? agentList.find((a) => a.status === "active")?.id ?? "";
      });
    } catch (e) {
      setError((e as Error).message);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const gestor = useMemo(
    () => agents.find((a) => a.agent_type === "marketing") ?? null,
    [agents],
  );

  const activeAgents = useMemo(
    () => agents.filter((a) => a.status === "active"),
    [agents],
  );

  async function activatePreset(presetId: string) {
    setActivating(presetId);
    setError("");
    setMessage("");
    try {
      const created = await apiJson<Agent>("/api/v1/agents/from-preset", {
        method: "POST",
        body: JSON.stringify({ preset_id: presetId }),
      });
      setMessage(
        presetId === "gestor"
          ? "Agente Gestor pronto — use o playbook ou converse abaixo."
          : `${created.name} ativado.`,
      );
      await load();
      setSelectedAgentId(created.id);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setActivating(null);
    }
  }

  async function changeStatus(agent: Agent, status: string) {
    try {
      await apiJson(`/api/v1/agents/${agent.id}/status`, {
        method: "PATCH",
        body: JSON.stringify({ status }),
      });
      await load();
    } catch (e) {
      setError((e as Error).message);
    }
  }

  async function queryAgent(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    const form = event.currentTarget;
    const data = Object.fromEntries(new FormData(form));
    const question = String(data.question);
    const agentId = String(data.agent_id || selectedAgentId);
    try {
      setHistory((prev) => [...prev, { role: "user", content: question }]);
      const result = await apiJson<ChatResult>(
        `/api/v1/agents/${agentId}/query`,
        {
          method: "POST",
          body: JSON.stringify({
            question,
            conversation_id: conversationId,
          }),
        },
      );
      setConversationId(result.conversation_id);
      setChatResult(result);
      setHistory((prev) => [
        ...prev,
        { role: "assistant", content: result.answer },
      ]);
      form.querySelector<HTMLTextAreaElement>("textarea")?.focus();
      (form.elements.namedItem("question") as HTMLTextAreaElement).value = "";
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  function hasType(agentType: string) {
    return agents.some((a) => a.agent_type === agentType && a.status === "active");
  }

  return (
    <>
      <header>
        <div>
          <span>EQUIPE DE IA</span>
          <h1>Agentes</h1>
        </div>
        <Link className="secondary" href="/app/settings/llm">
          Inteligência (IA)
        </Link>
      </header>
      {error && <p className="error">{error}</p>}
      {message && <p className="success">{message}</p>}

      <article className="panel" style={{ marginBottom: 16 }}>
        <div className="panel-title">
          <div>
            <span>GESTOR</span>
            <h2>Agente Gestor — o cérebro do Marketing</h2>
          </div>
          <span className={`agent-status ${gestor?.status ?? "draft"}`}>
            {gestor ? gestor.status : "preparando…"}
          </span>
        </div>
        <p style={{ marginTop: 0, lineHeight: 1.55, opacity: 0.9 }}>
          Ele não começa produzindo posts. Primeiro diagnostica o que já existe,
          depois descobre o que a empresa quer, e só então monta plano e peças
          com CTA. O fluxo guiado fica no Marketing; aqui você conversa e
          ativa o restante da equipe.
        </p>
        <div className="proposal-actions" style={{ flexWrap: "wrap", gap: 8 }}>
          <Link className="primary" href="/app/marketing">
            Abrir playbook (diagnóstico → plano)
          </Link>
          {gestor?.status !== "active" && (
            <button
              type="button"
              className="secondary"
              disabled={activating === "gestor"}
              onClick={() => void activatePreset("gestor")}
            >
              {activating === "gestor" ? "Ativando…" : "Garantir Gestor ativo"}
            </button>
          )}
          {gestor && (
            <button
              type="button"
              className="secondary"
              onClick={() => {
                setSelectedAgentId(gestor.id);
                setConversationId(null);
                setHistory([]);
                setChatResult(null);
              }}
            >
              Conversar com o Gestor
            </button>
          )}
        </div>
      </article>

      <div className="content-grid">
        <article className="panel">
          <div className="panel-title">
            <div>
              <span>EQUIPE</span>
              <h2>Agentes da empresa</h2>
            </div>
          </div>
          {agents.length === 0 ? (
            <div className="empty">
              <strong>Nenhum agente ainda</strong>
              <p>Ative um papel pronto ao lado — sem escrever prompt.</p>
            </div>
          ) : (
            <div className="agent-grid">
              {agents.map((agent) => (
                <div className="agent-card" key={agent.id}>
                  <div className="agent-icon">
                    {agent.agent_type === "marketing" ? "◆" : "◎"}
                  </div>
                  <div>
                    <strong>{agent.name}</strong>
                    <small>
                      {agentLabel(agent.agent_type)}
                      {agent.agent_type === "marketing" ? " · orquestra Marketing" : ""}
                    </small>
                  </div>
                  <span className={`agent-status ${agent.status}`}>
                    {agent.status}
                  </span>
                  <p>
                    {agent.agent_type === "marketing"
                      ? "Diagnostica → descobre → planeja → peças com CTA."
                      : agent.instructions.length > 140
                        ? `${agent.instructions.slice(0, 140)}…`
                        : agent.instructions}
                  </p>
                  <div className="agent-actions">
                    <button
                      type="button"
                      onClick={() => {
                        setSelectedAgentId(agent.id);
                        setConversationId(null);
                        setHistory([]);
                        setChatResult(null);
                      }}
                    >
                      Conversar
                    </button>
                    <button
                      type="button"
                      onClick={() => void changeStatus(agent, "active")}
                    >
                      Ativar
                    </button>
                    <button
                      type="button"
                      onClick={() => void changeStatus(agent, "paused")}
                    >
                      Pausar
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}

          <div className="panel-title" style={{ marginTop: "1.5rem" }}>
            <div>
              <span>CHAT</span>
              <h2>Conversar com um agente</h2>
            </div>
            {conversationId && (
              <button
                type="button"
                onClick={() => {
                  setConversationId(null);
                  setHistory([]);
                  setChatResult(null);
                }}
              >
                Nova conversa
              </button>
            )}
          </div>

          {history.length > 0 && (
            <div className="chat-result" style={{ marginBottom: 16 }}>
              {history.map((msg, i) => (
                <div key={`${msg.role}-${i}`} style={{ marginBottom: 12 }}>
                  <strong>{msg.role === "user" ? "Você" : "Agente"}</strong>
                  {msg.role === "assistant" ? (
                    <div style={{ margin: "4px 0 0" }}>
                      <MarkdownLite text={msg.content} />
                    </div>
                  ) : (
                    <p style={{ whiteSpace: "pre-wrap", margin: "4px 0 0" }}>
                      {msg.content}
                    </p>
                  )}
                </div>
              ))}
              {chatResult && (
                <small>
                  {chatResult.sources.length} fontes
                  {chatResult.mode ? ` · ${chatResult.mode}` : ""}
                </small>
              )}
            </div>
          )}

          <form onSubmit={queryAgent}>
            <label>
              Agente
              <select
                name="agent_id"
                required
                value={selectedAgentId}
                onChange={(e) => setSelectedAgentId(e.target.value)}
              >
                <option value="">Selecione</option>
                {activeAgents.map((agent) => (
                  <option key={agent.id} value={agent.id}>
                    {agent.name} · {agentLabel(agent.agent_type)}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Pergunta
              <textarea
                name="question"
                required
                minLength={3}
                placeholder={
                  selectedAgentId && gestor?.id === selectedAgentId
                    ? "Ex.: Nossa empresa posta só no Instagram. Por onde começamos?"
                    : "Pergunte ao agente…"
                }
              />
            </label>
            {activeAgents.length === 0 && (
              <p className="pricing-note">
                Ative um papel pronto ao lado ou{" "}
                <Link href="/app/settings/llm">conecte a inteligência (IA)</Link>
                .
              </p>
            )}
            <button className="primary" disabled={busy || !selectedAgentId}>
              Enviar
            </button>
          </form>
        </article>

        <article className="panel">
          <div className="panel-title">
            <div>
              <span>PRONTOS</span>
              <h2>Ativar papel (sem escrever prompt)</h2>
            </div>
          </div>
          <p style={{ marginTop: 0, opacity: 0.85, lineHeight: 1.5 }}>
            Escolha o que a empresa precisa. As instruções vêm prontas — você
            não precisa ser técnico nem “engenheiro de prompt”.
          </p>
          <div style={{ display: "grid", gap: 12 }}>
            {(presets.length
              ? presets
              : [
                  {
                    id: "gestor",
                    name: "Agente Gestor",
                    agent_type: "marketing",
                    blurb: "Orquestra Marketing: diagnóstico → plano → peças.",
                    featured: true,
                    workspace_href: "/app/marketing",
                    workspace_label: "Abrir playbook",
                  },
                ]
            ).map((preset) => {
              const active = hasType(preset.agent_type);
              return (
                <div
                  key={preset.id}
                  style={{
                    border: preset.featured
                      ? "1px solid #5a8f72"
                      : "1px solid #3a3a40",
                    borderRadius: 8,
                    padding: 12,
                  }}
                >
                  <strong>
                    {preset.name}
                    {preset.featured ? " · principal" : ""}
                  </strong>
                  <p style={{ margin: "6px 0 10px", opacity: 0.85 }}>
                    {preset.blurb}
                  </p>
                  <div className="proposal-actions" style={{ flexWrap: "wrap", gap: 8 }}>
                    <button
                      type="button"
                      className={active ? "secondary" : "primary"}
                      disabled={activating === preset.id}
                      onClick={() => void activatePreset(preset.id)}
                    >
                      {activating === preset.id
                        ? "Ativando…"
                        : active
                          ? "Já ativo — reabrir"
                          : "Ativar"}
                    </button>
                    <Link className="secondary" href={preset.workspace_href}>
                      {preset.workspace_label}
                    </Link>
                  </div>
                </div>
              );
            })}
          </div>
        </article>
      </div>
    </>
  );
}
