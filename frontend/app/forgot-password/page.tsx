"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import { ApiError, apiJson } from "../lib/api";
import { LanguagePicker, LocaleProvider, useLocale } from "../lib/locale";

const ORG_KEY = "operai_last_org";

function ForgotForm() {
  const { t } = useLocale();
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [resetUrl, setResetUrl] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [orgSlug, setOrgSlug] = useState("");

  useEffect(() => {
    setOrgSlug(localStorage.getItem(ORG_KEY) || "");
  }, []);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setMessage("");
    setResetUrl(null);
    const data = Object.fromEntries(new FormData(event.currentTarget));
    const organization_slug = String(data.organization_slug || "")
      .trim()
      .toLowerCase();
    try {
      const result = await apiJson<{
        message?: string;
        reset_url?: string | null;
      }>("/api/v1/auth/forgot-password", {
        method: "POST",
        body: JSON.stringify({
          email: String(data.email).trim().toLowerCase(),
          organization_slug,
        }),
      });
      localStorage.setItem(ORG_KEY, organization_slug);
      setMessage(
        result.message ||
          "Se a conta existir, use o link de redefinição (válido por 1 hora).",
      );
      if (result.reset_url) setResetUrl(result.reset_url);
    } catch (e) {
      setError(
        e instanceof ApiError
          ? e.message
          : e instanceof Error
            ? e.message
            : "Não foi possível solicitar a recuperação.",
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
          <h1>Recuperar senha</h1>
          <p>Informe e-mail e identificador da empresa para gerar o link.</p>
        </div>
        <LanguagePicker />
      </section>
      <section className="auth-v2-right">
        <div className="auth-v2-card">
          <form onSubmit={onSubmit}>
            <label className="auth-v2-field">
              <span>{t.orgLabel}</span>
              <div className="auth-v2-input">
                <input
                  name="organization_slug"
                  required
                  pattern="[a-z0-9-]+"
                  placeholder={t.orgPlaceholder}
                  value={orgSlug}
                  onChange={(e) => setOrgSlug(e.target.value.toLowerCase())}
                  autoComplete="organization"
                />
              </div>
            </label>
            <label className="auth-v2-field">
              <span>{t.emailLabel}</span>
              <div className="auth-v2-input">
                <input
                  name="email"
                  type="email"
                  required
                  autoComplete="email"
                  placeholder={t.emailPlaceholder}
                />
              </div>
            </label>
            {error ? <p className="auth-v2-error">{error}</p> : null}
            {message ? <p className="success" style={{ marginTop: 8 }}>{message}</p> : null}
            {resetUrl ? (
              <div className="secret-box" style={{ marginTop: 12 }}>
                <strong>Link de redefinição (1 hora)</strong>
                <p style={{ wordBreak: "break-all", margin: "8px 0" }}>
                  <a href={resetUrl}>{resetUrl}</a>
                </p>
                <button
                  type="button"
                  className="secondary"
                  onClick={() => void navigator.clipboard.writeText(resetUrl)}
                >
                  Copiar link
                </button>
              </div>
            ) : null}
            <button type="submit" className="auth-v2-submit" disabled={busy}>
              {busy ? "Gerando…" : "Gerar link de redefinição"}
            </button>
          </form>
          <p className="auth-v2-switch">
            <Link href="/login">{t.signIn}</Link>
          </p>
        </div>
      </section>
    </main>
  );
}

export default function ForgotPasswordPage() {
  return (
    <LocaleProvider>
      <ForgotForm />
    </LocaleProvider>
  );
}
