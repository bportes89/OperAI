"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { apiJson } from "../../lib/api";
import { agentLabel } from "../../lib/format";
import type { Agent, ChatResult } from "../../lib/types";

export default function AgentsPage() {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [chatResult, setChatResult] = useState<ChatResult | null>(null);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [history, setHistory] = useState<{ role: string; content: string }[]>(
    [],
  );
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      setError("");
      setAgents(await apiJson<Agent[]>("/api/v1/agents"));
    } catch (e) {
      setError((e as Error).message);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function createAgent(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    const form = event.currentTarget;
    try {
      await apiJson("/api/v1/agents", {
        method: "POST",
        body: JSON.stringify(Object.fromEntries(new FormData(form))),
      });
      form.reset();
      await load();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
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
    try {
      setHistory((prev) => [...prev, { role: "user", content: question }]);
      const result = await apiJson<ChatResult>(
        `/api/v1/agents/${String(data.agent_id)}/query`,
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

  return (
    <>
      <header>
        <div>
          <span>AI WORKFORCE</span>
          <h1>Agentes</h1>
        </div>
      </header>
      {error && <p className="error">{error}</p>}

      <div className="content-grid">
        <article className="panel">
          <div className="panel-title">
            <div>
              <span>EQUIPE</span>
              <h2>Agentes configurados</h2>
            </div>
          </div>
          {agents.length === 0 ? (
            <div className="empty">
              <strong>Nenhum agente ainda</strong>
              <p>Crie Comercial, Atendimento, Cobrança ou Marketing.</p>
            </div>
          ) : (
            <div className="agent-grid">
              {agents.map((agent) => (
                <div className="agent-card" key={agent.id}>
                  <div className="agent-icon">◎</div>
                  <div>
                    <strong>{agent.name}</strong>
                    <small>
                      {agentLabel(agent.agent_type)} · {agent.model}
                    </small>
                  </div>
                  <span className={`agent-status ${agent.status}`}>
                    {agent.status}
                  </span>
                  <p>{agent.instructions}</p>
                  <div className="agent-actions">
                    <button
                      type="button"
                      onClick={() => void changeStatus(agent, "draft")}
                    >
                      Rascunho
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
              <h2>Consultar agente</h2>
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
                  <p style={{ whiteSpace: "pre-wrap", margin: "4px 0 0" }}>
                    {msg.content}
                  </p>
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
              <select name="agent_id" required>
                <option value="">Selecione</option>
                {agents
                  .filter((a) => a.status === "active")
                  .map((agent) => (
                    <option key={agent.id} value={agent.id}>
                      {agent.name} · {agentLabel(agent.agent_type)}
                    </option>
                  ))}
              </select>
            </label>
            <label>
              Pergunta
              <textarea name="question" required minLength={3} />
            </label>
            {agents.filter((a) => a.status === "active").length === 0 && (
              <p className="pricing-note">
                Ative um agente ou{" "}
                <Link href="/app/settings/llm">configure a chave LLM</Link>{" "}
                para respostas reais.
              </p>
            )}
            <button className="primary" disabled={busy}>
              Enviar
            </button>
          </form>
        </article>

        <article className="panel">
          <div className="panel-title">
            <div>
              <span>NOVO</span>
              <h2>Criar agente</h2>
            </div>
          </div>
          <form onSubmit={createAgent}>
            <label>
              Nome
              <input name="name" required minLength={2} />
            </label>
            <label>
              Especialidade
              <select name="agent_type" defaultValue="commercial">
                <option value="commercial">Comercial</option>
                <option value="whatsapp">Atendimento</option>
                <option value="finance">Cobrança</option>
                <option value="marketing">Marketing</option>
              </select>
            </label>
            <label>
              Modelo
              <select name="model" defaultValue="openai/gpt-oss-120b">
                <option value="openai/gpt-oss-120b">GPT-OSS 120B (Groq)</option>
                <option value="openai/gpt-oss-20b">GPT-OSS 20B (Groq)</option>
                <option value="qwen/qwen3.6-27b">Qwen 3.6 27B (Groq)</option>
                <option value="gpt-4o-mini">GPT-4o mini (OpenAI)</option>
                <option value="gpt-4o">GPT-4o (OpenAI)</option>
              </select>
            </label>
            <label>
              Instruções
              <textarea name="instructions" required minLength={10} />
            </label>
            <button className="primary" disabled={busy}>
              Criar agente
            </button>
          </form>
        </article>
      </div>
    </>
  );
}
