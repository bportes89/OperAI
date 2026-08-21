"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { apiJson } from "../../lib/api";
import type { OnboardingState } from "../../lib/types";

type Step = {
  key: keyof OnboardingState["checklist"];
  title: string;
  description: string;
  href: string;
  cta: string;
};

const STEPS: Step[] = [
  {
    key: "account",
    title: "1. Conta e trial",
    description: "Sua empresa já está criada com trial ativo.",
    href: "/app/billing",
    cta: "Ver assinatura",
  },
  {
    key: "llm",
    title: "2. Colar chave LLM (BYOK)",
    description: "Conecte OpenAI, Groq ou OpenRouter para respostas reais.",
    href: "/app/settings/llm",
    cta: "Configurar LLM",
  },
  {
    key: "faq",
    title: "3. Subir FAQ",
    description: "Alimente a base com políticas, preços e respostas comuns.",
    href: "/app/knowledge",
    cta: "Enviar FAQ",
  },
  {
    key: "whatsapp",
    title: "4. Conectar WhatsApp",
    description: "Vincule um canal Evolution ou webhook para atender clientes.",
    href: "/app/inbox",
    cta: "Conectar WhatsApp",
  },
];

export default function OnboardingPage() {
  const [state, setState] = useState<OnboardingState | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      setError("");
      const data = await apiJson<OnboardingState>("/api/v1/settings/onboarding");
      const checklist = {
        account: true,
        llm: false,
        faq: false,
        whatsapp: false,
        ...(data.checklist ?? {}),
      };
      setState({ ...data, checklist });
    } catch (e) {
      setError((e as Error).message);
      setState({
        step: "welcome",
        completed_at: null,
        checklist: { account: true, llm: false, faq: false, whatsapp: false },
      });
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function markDone(key: string) {
    setBusy(true);
    setError("");
    try {
      const nextChecklist = {
        ...(state?.checklist ?? {}),
        [key]: true,
        account: true,
      };
      const allDone =
        nextChecklist.account &&
        nextChecklist.llm &&
        nextChecklist.faq &&
        nextChecklist.whatsapp;
      const updated = await apiJson<OnboardingState>(
        "/api/v1/settings/onboarding",
        {
          method: "PATCH",
          body: JSON.stringify({
            step: allDone ? "done" : key,
            checklist: nextChecklist,
            completed_at: allDone ? new Date().toISOString() : null,
          }),
        },
      );
      setState(updated);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  const checklist = state?.checklist ?? {};
  const doneCount = STEPS.filter((s) => checklist[s.key]).length;

  return (
    <>
      <header>
        <div>
          <span>SETUP</span>
          <h1>Onboarding</h1>
        </div>
        <div className="online">
          {doneCount}/{STEPS.length} passos
        </div>
      </header>
      {error && <p className="error">{error}</p>}
      {state?.completed_at && (
        <p className="success">Onboarding concluído. Boa operação!</p>
      )}

      <article className="panel">
        <div className="panel-title">
          <div>
            <span>CHECKLIST</span>
            <h2>Coloque a operação no ar</h2>
          </div>
          <button type="button" onClick={() => void load()}>
            Atualizar
          </button>
        </div>
        <div className="checklist">
          {STEPS.map((step) => {
            const done = Boolean(checklist[step.key]);
            return (
              <div
                key={step.key}
                className={`check-item${done ? " done" : ""}`}
              >
                <div className="check-dot">{done ? "✓" : ""}</div>
                <div>
                  <strong>{step.title}</strong>
                  <small style={{ display: "block", color: "#8a9692" }}>
                    {step.description}
                  </small>
                </div>
                <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                  <Link className="secondary" href={step.href}>
                    {step.cta}
                  </Link>
                  {!done && step.key !== "account" && (
                    <button
                      type="button"
                      className="primary"
                      disabled={busy}
                      onClick={() => void markDone(String(step.key))}
                    >
                      Marcar feito
                    </button>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </article>
    </>
  );
}
