"use client";

import Link from "next/link";
import { FormEvent, Suspense, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { ApiError, apiJson } from "../lib/api";
import { LanguagePicker, LocaleProvider, useLocale } from "../lib/locale";

const ORG_KEY = "operai_last_org";

function ResetForm() {
  const router = useRouter();
  const params = useSearchParams();
  const { t } = useLocale();
  const token = useMemo(() => params.get("token") || "", [params]);
  const orgFromLink = useMemo(() => params.get("org") || "", [params]);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [showPassword, setShowPassword] = useState(false);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!token) {
      setError("Link inválido. Solicite uma nova recuperação.");
      return;
    }
    setBusy(true);
    setError("");
    setMessage("");
    const data = Object.fromEntries(new FormData(event.currentTarget));
    const password = String(data.password || "");
    const confirm = String(data.confirm || "");
    if (password !== confirm) {
      setError("As senhas não coincidem.");
      setBusy(false);
      return;
    }
    try {
      const result = await apiJson<{
        message?: string;
        organization_slug?: string | null;
      }>("/api/v1/auth/reset-password", {
        method: "POST",
        body: JSON.stringify({ token, password }),
      });
      const slug = result.organization_slug || orgFromLink;
      if (slug) localStorage.setItem(ORG_KEY, slug);
      setMessage(result.message || "Senha atualizada.");
      setTimeout(() => router.replace("/login"), 1200);
    } catch (e) {
      setError(
        e instanceof ApiError
          ? e.message
          : e instanceof Error
            ? e.message
            : "Não foi possível redefinir a senha.",
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
          <h1>Nova senha</h1>
          <p>Defina uma senha forte (mínimo 8 caracteres).</p>
        </div>
        <LanguagePicker />
      </section>
      <section className="auth-v2-right">
        <div className="auth-v2-card">
          {!token ? (
            <>
              <p className="auth-v2-error">
                Link inválido ou incompleto. Solicite uma nova recuperação.
              </p>
              <p className="auth-v2-switch">
                <Link href="/forgot-password">Recuperar senha</Link>
              </p>
            </>
          ) : (
            <form onSubmit={onSubmit}>
              <label className="auth-v2-field">
                <span>Nova senha</span>
                <div className="auth-v2-input">
                  <input
                    name="password"
                    type={showPassword ? "text" : "password"}
                    required
                    minLength={8}
                    autoComplete="new-password"
                    placeholder={t.passwordPlaceholder}
                  />
                  <button
                    type="button"
                    className="auth-v2-eye"
                    onClick={() => setShowPassword((v) => !v)}
                  >
                    {showPassword ? "Ocultar" : "Mostrar"}
                  </button>
                </div>
              </label>
              <label className="auth-v2-field">
                <span>Confirmar senha</span>
                <div className="auth-v2-input">
                  <input
                    name="confirm"
                    type={showPassword ? "text" : "password"}
                    required
                    minLength={8}
                    autoComplete="new-password"
                    placeholder={t.passwordPlaceholder}
                  />
                </div>
              </label>
              {error ? <p className="auth-v2-error">{error}</p> : null}
              {message ? <p className="success">{message}</p> : null}
              <button type="submit" className="auth-v2-submit" disabled={busy}>
                {busy ? "Salvando…" : "Salvar nova senha"}
              </button>
            </form>
          )}
          <p className="auth-v2-switch">
            <Link href="/login">{t.signIn}</Link>
          </p>
        </div>
      </section>
    </main>
  );
}

export default function ResetPasswordPage() {
  return (
    <LocaleProvider>
      <Suspense fallback={<main className="auth-v2"><p>Carregando…</p></main>}>
        <ResetForm />
      </Suspense>
    </LocaleProvider>
  );
}
