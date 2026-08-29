"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { apiJson } from "../../lib/api";
import type { Agent, OnboardingState } from "../../lib/types";

type Step = {
  key: keyof OnboardingState["checklist"];
  title: string;
  description: string;
  href: string;
  cta: string;
  tip: string;
};

const STEPS: Step[] = [
  {
    key: "account",
    title: "1. Conta e trial",
    description: "Sua empresa já está criada. O trial libera o uso inicial.",
    href: "/app/billing",
    cta: "Ver planos",
    tip: "Nada técnico aqui — só acompanhar a assinatura.",
  },
  {
    key: "llm",
    title: "2. Conectar a inteligência (IA)",
    description:
      "Cole a chave do provedor de IA (OpenAI, Groq ou OpenRouter). Sem isso, as respostas ficam limitadas.",
    href: "/app/settings/llm",
    cta: "Guia passo a passo",
    tip: "O assistente explica onde clicar para pegar a chave.",
  },
  {
    key: "faq",
    title: "3. Base da empresa",
    description:
      "Publique FAQ, políticas e preços (texto ou PDF/Word). É o que os agentes usam para falar como a sua empresa.",
    href: "/app/knowledge",
    cta: "Adicionar conteúdo",
    tip: "Comece com um FAQ curto; PDF escaneado também funciona via OCR.",
  },
  {
    key: "whatsapp",
    title: "4. Canal de atendimento",
    description:
      "Conecte o WhatsApp (Meta oficial ou Evolution) para as conversas entrarem na OperAI.",
    href: "/app/inbox",
    cta: "Abrir WhatsApp / Inbox",
    tip: "A verificação nas plataformas é sempre feita por você (dono).",
  },
  {
    key: "agent",
    title: "5. Ativar agente WhatsApp",
    description:
      "Sem o agente de Atendimento ativo, o canal recebe mensagem mas a IA não responde.",
    href: "/app/agents",
    cta: "Ver agentes",
    tip: "Um clique abaixo cria e ativa o agente pronto para PME.",
  },
];

export default function OnboardingPage() {
  const [state, setState] = useState<OnboardingState | null>(null);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      setError("");
      const data = await apiJson<OnboardingState>("/api/v1/settings/onboarding");
      setState(data);
    } catch (e) {
      setError((e as Error).message);
      setState({
        step: "welcome",
        completed_at: null,
        checklist: {
          account: true,
          llm: false,
          faq: false,
          whatsapp: false,
          agent: false,
        },
      });
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function activateWhatsappAgent() {
    setBusy(true);
    setError("");
    setMessage("");
    try {
      const agent = await apiJson<Agent>(
        "/api/v1/settings/onboarding/activate-whatsapp-agent",
        { method: "POST", body: "{}" },
      );
      setMessage(
        `Agente “${agent.name}” ativo — mensagens no WhatsApp já podem ser respondidas pela IA.`,
      );
      await load();
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
          <h1>Começar a operar</h1>
        </div>
        <div className="online">
          {doneCount}/{STEPS.length} concluídos
        </div>
      </header>
      {error && <p className="error">{error}</p>}
      {message && <p className="success">{message}</p>}
      {state?.completed_at && (
        <p className="success">
          Setup completo — IA, base, canal e agente de atendimento detectados.
        </p>
      )}

      <article className="panel" style={{ marginBottom: 16 }}>
        <p style={{ margin: 0, lineHeight: 1.55, opacity: 0.9 }}>
          Os passos abaixo são <strong>validados automaticamente</strong>: não
          adianta só marcar como feito. Quando conectar a IA, publicar a base,
          o WhatsApp e ativar o agente, o checklist atualiza sozinho.
        </p>
      </article>

      <article className="panel">
        <div className="panel-title">
          <div>
            <span>CHECKLIST</span>
            <h2>Do cadastro à primeira operação</h2>
          </div>
          <button type="button" onClick={() => void load()}>
            Atualizar status
          </button>
        </div>
        <div className="checklist">
          {STEPS.map((step) => {
            const done = Boolean(checklist[step.key]);
            return (
              <div
                key={String(step.key)}
                className={`check-item${done ? " done" : ""}`}
              >
                <div className="check-dot">{done ? "✓" : ""}</div>
                <div>
                  <strong>{step.title}</strong>
                  <small style={{ display: "block", color: "#a0a0a8" }}>
                    {step.description}
                  </small>
                  <small
                    style={{ display: "block", color: "#7a7a84", marginTop: 4 }}
                  >
                    {step.tip}
                  </small>
                  {done && (
                    <small
                      style={{
                        display: "block",
                        color: "#8ee0b5",
                        marginTop: 6,
                      }}
                    >
                      Detectado automaticamente
                    </small>
                  )}
                </div>
                <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                  {step.key === "agent" && !done ? (
                    <button
                      type="button"
                      className="primary"
                      disabled={busy}
                      onClick={() => void activateWhatsappAgent()}
                    >
                      {busy ? "Ativando…" : "Ativar agente agora"}
                    </button>
                  ) : null}
                  <Link
                    className={done ? "secondary" : step.key === "agent" ? "secondary" : "primary"}
                    href={step.href}
                  >
                    {done ? "Revisar" : step.cta}
                  </Link>
                </div>
              </div>
            );
          })}
        </div>
      </article>
    </>
  );
}
