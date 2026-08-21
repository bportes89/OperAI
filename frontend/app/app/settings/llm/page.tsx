"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { apiJson } from "../../../lib/api";
import type { LlmSettings } from "../../../lib/types";

export default function LlmSettingsPage() {
  const [settings, setSettings] = useState<LlmSettings | null>(null);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      setError("");
      const data = await apiJson<LlmSettings>("/api/v1/settings/llm");
      setSettings(data);
    } catch (e) {
      setError((e as Error).message);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setMessage("");
    const form = event.currentTarget;
    const data = Object.fromEntries(new FormData(form));
    try {
      const updated = await apiJson<LlmSettings>("/api/v1/settings/llm", {
        method: "PUT",
        body: JSON.stringify({
          provider: data.provider,
          model_name: data.model,
          api_key: data.api_key,
        }),
      });
      setSettings(updated);
      setMessage("Chave LLM salva. Os agentes passam a usar BYOK.");
      form.reset();
      try {
        await apiJson("/api/v1/settings/onboarding", {
          method: "PATCH",
          body: JSON.stringify({
            checklist: { llm: true },
            step: "llm",
          }),
        });
      } catch {
        /* optional while backend deploys */
      }
      await load();
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
          <span>BYOK</span>
          <h1>Chave LLM</h1>
        </div>
      </header>
      {error && <p className="error">{error}</p>}
      {message && <p className="success">{message}</p>}

      <div className="content-grid">
        <article className="panel">
          <div className="panel-title">
            <div>
              <span>STATUS</span>
              <h2>Provedor atual</h2>
            </div>
          </div>
          {settings?.configured ? (
            <div className="kpi-list">
              <div>
                <span>Provedor</span>
                <strong>{settings.provider}</strong>
              </div>
              <div>
                <span>Modelo</span>
                <strong>{settings.model_name}</strong>
              </div>
            </div>
          ) : (
            <div className="empty">
              <strong>Nenhuma chave configurada</strong>
              <p>
                Sem BYOK, os agentes usam resposta local limitada. Cole sua
                chave para respostas reais.
              </p>
            </div>
          )}
        </article>

        <article className="panel">
          <div className="panel-title">
            <div>
              <span>CONFIGURAR</span>
              <h2>Salvar credencial</h2>
            </div>
          </div>
          <form onSubmit={onSubmit}>
            <label>
              Provedor
              <select
                name="provider"
                defaultValue={settings?.provider ?? "openai"}
                required
              >
                <option value="openai">OpenAI</option>
                <option value="groq">Groq</option>
                <option value="openrouter">OpenRouter</option>
              </select>
            </label>
            <label>
              Modelo
              <input
                name="model"
                required
                defaultValue={settings?.model_name ?? "gpt-4o-mini"}
                placeholder="gpt-4o-mini"
              />
            </label>
            <label>
              API key
              <input
                name="api_key"
                type="password"
                required
                minLength={8}
                placeholder="sk-..."
                autoComplete="off"
              />
            </label>
            <button className="primary" disabled={busy}>
              {busy ? "Salvando..." : "Salvar chave"}
            </button>
          </form>
        </article>
      </div>
    </>
  );
}
