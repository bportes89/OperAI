"use client";

import Link from "next/link";
import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { apiJson } from "../../../lib/api";
import type { LlmSettings } from "../../../lib/types";

const PROVIDERS = [
  {
    id: "groq",
    name: "Groq",
    blurb: "Bom para começar — rápido e costuma ter créditos gratuitos.",
    keyUrl: "https://console.groq.com/keys",
    models: [
      { id: "llama-3.3-70b-versatile", label: "Llama 3.3 70B (recomendado)" },
      { id: "llama-3.1-8b-instant", label: "Llama 3.1 8B (mais barato)" },
      { id: "openai/gpt-oss-120b", label: "GPT OSS 120B" },
      { id: "openai/gpt-oss-20b", label: "GPT OSS 20B" },
      { id: "groq/compound", label: "Groq Compound (Sistema de IA)" },
      { id: "groq/compound-mini", label: "Groq Compound Mini (Sistema de IA)" },
    ],
  },
  {
    id: "openai",
    name: "OpenAI",
    blurb: "O mais conhecido (ChatGPT). Exige conta com pagamento cadastrado.",
    keyUrl: "https://platform.openai.com/api-keys",
    models: [
      { id: "gpt-4o-mini", label: "GPT-4o mini (recomendado)" },
      { id: "gpt-4o", label: "GPT-4o (mais capaz)" },
    ],
  },
  {
    id: "openrouter",
    name: "OpenRouter",
    blurb: "Uma chave para vários modelos. Útil se você quiser trocar depois.",
    keyUrl: "https://openrouter.ai/keys",
    models: [
      { id: "openai/gpt-4o-mini", label: "GPT-4o mini via OpenRouter" },
      { id: "google/gemini-2.0-flash-001", label: "Gemini Flash" },
    ],
  },
] as const;

export default function LlmSettingsPage() {
  const [settings, setSettings] = useState<LlmSettings | null>(null);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [step, setStep] = useState(1);
  const [provider, setProvider] = useState("groq");
  const [model, setModel] = useState("llama-3.3-70b-versatile");

  const selected = useMemo(
    () => PROVIDERS.find((p) => p.id === provider) ?? PROVIDERS[0],
    [provider],
  );

  const load = useCallback(async () => {
    try {
      setError("");
      const data = await apiJson<LlmSettings>("/api/v1/settings/llm");
      setSettings(data);
      if (data.configured && data.provider) {
        setProvider(data.provider);
        if (data.model_name) setModel(data.model_name);
      }
    } catch (e) {
      setError((e as Error).message);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    const first = selected.models[0]?.id;
    if (first && !selected.models.some((m) => m.id === model)) {
      setModel(first);
    }
  }, [selected, model]);

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
      setMessage(
        "Pronto! A inteligência da sua empresa está conectada. Os agentes já podem responder de verdade.",
      );
      setStep(4);
      form.reset();
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
          <span>INTELIGÊNCIA</span>
          <h1>Conectar a IA da empresa</h1>
        </div>
        <Link className="secondary" href="/app/onboarding">
          Voltar ao setup
        </Link>
      </header>
      {error && <p className="error">{error}</p>}
      {message && <p className="success">{message}</p>}

      <article className="panel" style={{ marginBottom: 16 }}>
        <div className="panel-title">
          <div>
            <span>POR QUE ISSO?</span>
            <h2>Em linguagem simples</h2>
          </div>
        </div>
        <p style={{ marginTop: 0, lineHeight: 1.55 }}>
          A OperAI é a plataforma (agentes, WhatsApp, CRM). O custo das
          respostas de IA fica na <strong>sua</strong> conta do provedor —
          assim você controla o gasto. É só criar uma chave no site do
          provedor e colar aqui. Não precisa ser técnico: siga os 3 passos.
        </p>
        <div className="proposal-actions" style={{ flexWrap: "wrap" }}>
          {[1, 2, 3].map((n) => (
            <span
              key={n}
              className={`finance-status ${step >= n ? "paid" : "pending"}`}
            >
              {n}.{" "}
              {n === 1 ? "Escolher provedor" : n === 2 ? "Pegar a chave" : "Colar e testar"}
            </span>
          ))}
        </div>
      </article>

      <div className="content-grid">
        <article className="panel">
          <div className="panel-title">
            <div>
              <span>STATUS</span>
              <h2>Situação atual</h2>
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
              <div>
                <span>Chave</span>
                <strong>{settings.api_key_masked ?? "••••"}</strong>
              </div>
            </div>
          ) : (
            <div className="empty">
              <strong>Ainda sem conexão</strong>
              <p>
                Enquanto isso, os agentes usam só o que está na base da empresa
                (respostas limitadas). Complete o passo a passo ao lado.
              </p>
            </div>
          )}
        </article>

        <article className="panel">
          <div className="panel-title">
            <div>
              <span>ASSISTENTE</span>
              <h2>Passo a passo</h2>
            </div>
          </div>
          <form onSubmit={onSubmit}>
            <label>
              1. Qual provedor você quer usar?
              <select
                name="provider"
                value={provider}
                onChange={(e) => {
                  setProvider(e.target.value);
                  setStep(1);
                }}
                required
              >
                {PROVIDERS.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name}
                    {p.id === "groq" ? " — recomendado para começar" : ""}
                  </option>
                ))}
              </select>
            </label>
            <p style={{ opacity: 0.85, marginTop: -4 }}>{selected.blurb}</p>

            <label>
              2. Qual modelo?
              <select
                name="model"
                value={model}
                onChange={(e) => setModel(e.target.value)}
                required
              >
                {selected.models.map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.label}
                  </option>
                ))}
              </select>
            </label>
            <p style={{ opacity: 0.85, marginTop: -4 }}>
              Deixe o recomendado se não tiver preferência.
            </p>

            <div
              style={{
                border: "1px solid #3a3a40",
                padding: 12,
                borderRadius: 8,
                marginBottom: 8,
              }}
            >
              <strong>3. Pegue sua chave</strong>
              <p style={{ margin: "8px 0", opacity: 0.85 }}>
                Abra o site do provedor, entre na conta e crie uma API key.
                Depois volte e cole abaixo.
              </p>
              <a
                className="secondary"
                href={selected.keyUrl}
                target="_blank"
                rel="noreferrer"
                onClick={() => setStep(2)}
              >
                Abrir página de chaves ({selected.name})
              </a>
            </div>

            <label>
              Cole a chave aqui
              <input
                name="api_key"
                type="password"
                required
                minLength={8}
                placeholder="Cole a chave gerada no site do provedor"
                autoComplete="off"
                onFocus={() => setStep(3)}
              />
            </label>

            <button className="primary" disabled={busy}>
              {busy
                ? "Testando conexão…"
                : "Testar e salvar (validamos antes de gravar)"}
            </button>
          </form>
        </article>
      </div>
    </>
  );
}
