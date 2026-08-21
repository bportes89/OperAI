"use client";

import Link from "next/link";
import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { ApiError, login } from "../lib/api";

export default function LoginPage() {
  const router = useRouter();
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    const data = Object.fromEntries(new FormData(event.currentTarget));
    try {
      await login({
        email: String(data.email),
        password: String(data.password),
        organization_slug: String(data.organization_slug),
      });
      router.replace("/app");
    } catch (e) {
      setError(
        e instanceof ApiError ? e.message : "Falha ao entrar. Tente novamente.",
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="auth-shell">
      <section className="brand">
        <div className="logo">O</div>
        <span>OPERAI</span>
        <h1>Entre na sua operação de IA.</h1>
        <p>
          Acesse agentes, WhatsApp, cobrança e a base de conhecimento da sua
          empresa.
        </p>
      </section>
      <section className="auth-card">
        <h2>Entrar</h2>
        <form onSubmit={onSubmit}>
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
              autoComplete="current-password"
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
            {busy ? "Entrando..." : "Entrar no OperAI"}
          </button>
        </form>
        <p className="auth-switch">
          Não tem conta? <Link href="/register">Criar empresa</Link>
        </p>
      </section>
    </main>
  );
}
