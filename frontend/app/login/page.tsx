"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ApiError, login } from "../lib/api";

const ORG_KEY = "operai_last_org";
type Tab = "email" | "org";

function IconMail() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden>
      <rect x="3.5" y="5.5" width="17" height="13" rx="2" stroke="#c8c8d0" strokeWidth="1.5" />
      <path d="m5 7.5 7 5.2L19 7.5" stroke="#c8c8d0" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function IconLock() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden>
      <rect x="5" y="10" width="14" height="9.5" rx="2" stroke="#f5c400" strokeWidth="1.5" />
      <path d="M8 10V7.8a4 4 0 0 1 8 0V10" stroke="#f5c400" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  );
}

function IconBuilding() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden>
      <path d="M4 20V7l8-3.5L20 7v13" stroke="#c8c8d0" strokeWidth="1.5" strokeLinejoin="round" />
      <path d="M9 20v-4.5h6V20" stroke="#c8c8d0" strokeWidth="1.5" />
      <path d="M9 9.5h.01M12 9.5h.01M15 9.5h.01M9 12.5h.01M12 12.5h.01M15 12.5h.01" stroke="#c8c8d0" strokeWidth="2" strokeLinecap="round" />
    </svg>
  );
}

function IconEye({ off }: { off?: boolean }) {
  return off ? (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden>
      <path d="M3 3l18 18M10.6 10.7a2.4 2.4 0 0 0 2.8 2.8M9.4 5.5A9.8 9.8 0 0 1 12 5c5 0 8.8 3.5 10 7-.5 1.3-1.4 2.7-2.6 3.8M6.3 6.4C4.5 7.6 3.2 9.2 2.3 12c1.2 3.5 5 7 9.7 7 1.3 0 2.6-.2 3.7-.7" stroke="#8b8b93" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  ) : (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden>
      <path d="M2.5 12S6 5.5 12 5.5 21.5 12 21.5 12 18 18.5 12 18.5 2.5 12 2.5 12Z" stroke="#8b8b93" strokeWidth="1.5" />
      <circle cx="12" cy="12" r="2.8" stroke="#8b8b93" strokeWidth="1.5" />
    </svg>
  );
}

function IconGlobe() {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" aria-hidden>
      <circle cx="12" cy="12" r="8.5" stroke="#4d8cff" strokeWidth="1.5" />
      <path d="M3.5 12h17M12 3.5c2.4 2.6 3.6 5.4 3.6 8.5s-1.2 5.9-3.6 8.5c-2.4-2.6-3.6-5.4-3.6-8.5S9.6 6.1 12 3.5Z" stroke="#4d8cff" strokeWidth="1.5" />
    </svg>
  );
}

export default function LoginPage() {
  const router = useRouter();
  const [tab, setTab] = useState<Tab>("org");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [savedOrg, setSavedOrg] = useState("");
  const [orgSlug, setOrgSlug] = useState("");

  useEffect(() => {
    const last = localStorage.getItem(ORG_KEY) || "";
    setSavedOrg(last);
    setOrgSlug(last);
  }, []);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    const data = Object.fromEntries(new FormData(event.currentTarget));
    const organization_slug = (
      tab === "org" ? String(data.organization_slug || "") : savedOrg || orgSlug
    )
      .trim()
      .toLowerCase();

    if (!organization_slug) {
      setError("Informe o identificador da empresa.");
      setTab("org");
      setBusy(false);
      return;
    }

    try {
      await login({
        email: String(data.email),
        password: String(data.password),
        organization_slug,
      });
      localStorage.setItem(ORG_KEY, organization_slug);
      router.replace("/app");
    } catch (e) {
      setError(
        e instanceof ApiError
          ? e.message
          : e instanceof Error
            ? e.message
            : "Falha ao entrar. Tente novamente.",
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="auth-v2">
      <section className="auth-v2-left">
        <div className="auth-v2-brand">
          <img
            src="/operai-logo.png"
            alt="OperAI"
            className="auth-v2-logo"
            width={214}
            height={64}
          />
        </div>

        <div className="auth-v2-copy">
          <h1>Acesse sua plataforma</h1>
          <p>Entre com sua conta para continuar</p>
        </div>

        <div className="auth-v2-lang" aria-hidden>
          <IconGlobe />
          Português (Brasil)
          <span style={{ fontSize: 10, opacity: 0.75 }}>▼</span>
        </div>
      </section>

      <section className="auth-v2-right">
        <div className="auth-v2-card">
          <div className="auth-v2-tabs" role="tablist">
            <button
              type="button"
              role="tab"
              className={tab === "email" ? "active" : ""}
              aria-selected={tab === "email"}
              onClick={() => setTab("email")}
            >
              E-mail
            </button>
            <button
              type="button"
              role="tab"
              className={tab === "org" ? "active" : ""}
              aria-selected={tab === "org"}
              onClick={() => setTab("org")}
            >
              Entrar com organização
            </button>
          </div>

          <form onSubmit={onSubmit}>
            {tab === "org" && (
              <label className="auth-v2-field">
                <span>Identificador da empresa</span>
                <div className="auth-v2-input">
                  <IconBuilding />
                  <input
                    name="organization_slug"
                    required
                    pattern="[a-z0-9-]+"
                    placeholder="minha-empresa"
                    value={orgSlug}
                    onChange={(e) => setOrgSlug(e.target.value.toLowerCase())}
                    autoComplete="organization"
                  />
                </div>
              </label>
            )}

            <label className="auth-v2-field">
              <span>E-mail</span>
              <div className="auth-v2-input">
                <IconMail />
                <input
                  name="email"
                  type="email"
                  required
                  autoComplete="email"
                  placeholder="Seu endereço de e-mail"
                />
              </div>
            </label>

            <label className="auth-v2-field">
              <span>Senha</span>
              <div className="auth-v2-input">
                <IconLock />
                <input
                  name="password"
                  type={showPassword ? "text" : "password"}
                  required
                  minLength={8}
                  autoComplete="current-password"
                  placeholder="Sua senha"
                />
                <button
                  type="button"
                  className="icon-btn"
                  aria-label={showPassword ? "Ocultar senha" : "Mostrar senha"}
                  onClick={() => setShowPassword((v) => !v)}
                >
                  <IconEye off={showPassword} />
                </button>
              </div>
            </label>

            <div className="auth-v2-forgot">
              <button
                type="button"
                onClick={() =>
                  setError(
                    "Recuperação de senha em breve. Fale com o administrador.",
                  )
                }
              >
                Esqueceu sua senha?
              </button>
            </div>

            {error ? <p className="auth-v2-error">{error}</p> : null}

            <button type="submit" className="auth-v2-submit" disabled={busy}>
              {busy ? "Entrando..." : "Entrar"}
            </button>
          </form>

          <p className="auth-v2-terms">
            Ao fazer login, você concorda com nossos{" "}
            <a href="#termos">Termos e Condições</a>.
          </p>
          <p className="auth-v2-switch">
            Não tem conta? <Link href="/register">Criar empresa</Link>
          </p>
        </div>
      </section>
    </main>
  );
}
