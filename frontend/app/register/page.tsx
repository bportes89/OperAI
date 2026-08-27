"use client";

import Link from "next/link";
import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { ApiError, register } from "../lib/api";

const ORG_KEY = "operai_last_org";

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

function IconUser() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden>
      <circle cx="12" cy="8" r="3.2" stroke="#c8c8d0" strokeWidth="1.5" />
      <path d="M5 19c1.7-3 4-4.5 7-4.5s5.3 1.5 7 4.5" stroke="#c8c8d0" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  );
}

function IconBuilding() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden>
      <path d="M4 20V7l8-3.5L20 7v13" stroke="#c8c8d0" strokeWidth="1.5" strokeLinejoin="round" />
      <path d="M9 20v-4.5h6V20" stroke="#c8c8d0" strokeWidth="1.5" />
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

export default function RegisterPage() {
  const router = useRouter();
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [showPassword, setShowPassword] = useState(false);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    const data = Object.fromEntries(new FormData(event.currentTarget));
    const organization_slug = String(data.organization_slug).trim().toLowerCase();
    try {
      await register({
        name: String(data.name),
        email: String(data.email),
        password: String(data.password),
        organization_name: String(data.organization_name),
        organization_slug,
      });
      localStorage.setItem(ORG_KEY, organization_slug);
      router.replace("/app/onboarding");
    } catch (e) {
      setError(
        e instanceof ApiError ? e.message : "Não foi possível criar a conta.",
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
          <h1>Crie sua plataforma</h1>
          <p>Trial incluso para montar sua equipe de IA</p>
        </div>

        <div className="auth-v2-lang" aria-hidden>
          <IconGlobe />
          Português (Brasil)
          <span style={{ fontSize: 10, opacity: 0.75 }}>▼</span>
        </div>
      </section>

      <section className="auth-v2-right">
        <div className="auth-v2-card">
          <form onSubmit={onSubmit}>
            <label className="auth-v2-field">
              <span>Seu nome</span>
              <div className="auth-v2-input">
                <IconUser />
                <input name="name" required minLength={2} placeholder="Nome completo" />
              </div>
            </label>

            <label className="auth-v2-field">
              <span>Nome da empresa</span>
              <div className="auth-v2-input">
                <IconBuilding />
                <input
                  name="organization_name"
                  required
                  minLength={2}
                  placeholder="Nome da empresa"
                />
              </div>
            </label>

            <label className="auth-v2-field">
              <span>Identificador da empresa</span>
              <div className="auth-v2-input">
                <IconBuilding />
                <input
                  name="organization_slug"
                  required
                  pattern="[a-z0-9-]+"
                  placeholder="minha-empresa"
                />
              </div>
            </label>

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
                  autoComplete="new-password"
                  placeholder="Sua senha"
                />
                <button
                  type="button"
                  className="icon-btn"
                  onClick={() => setShowPassword((v) => !v)}
                >
                  {showPassword ? "Ocultar" : "Mostrar"}
                </button>
              </div>
            </label>

            {error ? <p className="auth-v2-error">{error}</p> : null}

            <button type="submit" className="auth-v2-submit" disabled={busy}>
              {busy ? "Criando..." : "Começar trial"}
            </button>
          </form>

          <p className="auth-v2-terms">
            Ao criar a conta, você concorda com nossos{" "}
            <a href="#termos">Termos e Condições</a>.
          </p>
          <p className="auth-v2-switch">
            Já tem conta? <Link href="/login">Entrar</Link>
          </p>
        </div>
      </section>
    </main>
  );
}
