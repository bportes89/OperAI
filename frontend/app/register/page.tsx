"use client";

import Link from "next/link";
import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { ApiError, register } from "../lib/api";

export default function RegisterPage() {
  const router = useRouter();
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    const data = Object.fromEntries(new FormData(event.currentTarget));
    try {
      await register({
        name: String(data.name),
        email: String(data.email),
        password: String(data.password),
        organization_name: String(data.organization_name),
        organization_slug: String(data.organization_slug),
      });
      router.replace("/app/onboarding");
    } catch (e) {
      setError(
        e instanceof ApiError
          ? e.message
          : "Não foi possível criar a conta.",
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="auth-shell">
      <section className="brand">
        <div className="logo">O</div>
        <span>OPERAI · TRIAL</span>
        <h1>Monte sua equipe de IA em minutos.</h1>
        <p>
          Trial incluso. Configure BYOK, suba o FAQ e conecte o WhatsApp —
          depois ative o plano.
        </p>
      </section>
      <section className="auth-card">
        <h2>Criar empresa</h2>
        <form onSubmit={onSubmit}>
          <label>
            Seu nome
            <input name="name" required minLength={2} />
          </label>
          <label>
            Nome da empresa
            <input name="organization_name" required minLength={2} />
          </label>
          <label>
            E-mail
            <input name="email" type="email" required autoComplete="email" />
          </label>
          <label>
            Senha
            <input
              name="password"
              type="password"
              required
              minLength={8}
              autoComplete="new-password"
            />
          </label>
          <label>
            Identificador da empresa
            <input
              name="organization_slug"
              required
              pattern="[a-z0-9-]+"
              placeholder="minha-empresa"
            />
          </label>
          {error && <p className="error">{error}</p>}
          <button className="primary" disabled={busy}>
            {busy ? "Criando..." : "Começar trial"}
          </button>
        </form>
        <p className="auth-switch">
          Já tem conta? <Link href="/login">Entrar</Link>
        </p>
      </section>
    </main>
  );
}
