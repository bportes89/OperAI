"use client";

import Link from "next/link";
import { FormEvent, Suspense, useEffect, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { ApiError, apiJson } from "../lib/api";
import { LanguagePicker, LocaleProvider, useLocale } from "../lib/locale";

const ORG_KEY = "operai_last_org";

type InvitePreview = {
  email: string;
  name: string;
  organization_name: string;
  organization_slug: string;
  role: string;
  pending: boolean;
};

function AcceptForm() {
  const router = useRouter();
  const params = useSearchParams();
  const { t } = useLocale();
  const token = useMemo(() => params.get("token") || "", [params]);
  const [preview, setPreview] = useState<InvitePreview | null>(null);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!token) {
      setLoading(false);
      setError("Link de convite inválido.");
      return;
    }
    void (async () => {
      try {
        const data = await apiJson<InvitePreview>(
          `/api/v1/auth/invite?token=${encodeURIComponent(token)}`,
        );
        setPreview(data);
        if (data.organization_slug) {
          localStorage.setItem(ORG_KEY, data.organization_slug);
        }
      } catch (e) {
        setError(
          e instanceof ApiError
            ? e.message
            : "Convite inválido ou expirado.",
        );
      } finally {
        setLoading(false);
      }
    })();
  }, [token]);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!token) return;
    setBusy(true);
    setError("");
    setMessage("");
    const data = Object.fromEntries(new FormData(event.currentTarget));
    if (String(data.password) !== String(data.confirm)) {
      setError("As senhas não coincidem.");
      setBusy(false);
      return;
    }
    try {
      const result = await apiJson<{
        message?: string;
        organization_slug?: string;
      }>("/api/v1/auth/accept-invite", {
        method: "POST",
        body: JSON.stringify({
          token,
          password: data.password,
          name: data.name || undefined,
        }),
      });
      if (result.organization_slug) {
        localStorage.setItem(ORG_KEY, result.organization_slug);
      }
      setMessage(result.message || "Conta ativada.");
      setTimeout(() => router.replace("/login"), 1200);
    } catch (e) {
      setError(
        e instanceof ApiError
          ? e.message
          : e instanceof Error
            ? e.message
            : "Não foi possível aceitar o convite.",
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
          <h1>Aceitar convite</h1>
          <p>Crie sua senha para entrar na equipe.</p>
        </div>
        <LanguagePicker />
      </section>
      <section className="auth-v2-right">
        <div className="auth-v2-card">
          {loading ? (
            <p>Carregando convite…</p>
          ) : error && !preview ? (
            <>
              <p className="auth-v2-error">{error}</p>
              <p className="auth-v2-switch">
                <Link href="/login">{t.signIn}</Link>
              </p>
            </>
          ) : preview && !preview.pending ? (
            <>
              <p className="success">
                Este convite já foi aceito. Entre com seu e-mail.
              </p>
              <p className="auth-v2-switch">
                <Link href="/login">{t.signIn}</Link>
              </p>
            </>
          ) : (
            <form onSubmit={onSubmit}>
              {preview && (
                <p style={{ marginTop: 0, opacity: 0.9, lineHeight: 1.5 }}>
                  <strong>{preview.organization_name}</strong>
                  <br />
                  {preview.email} · {preview.role}
                </p>
              )}
              <label className="auth-v2-field">
                <span>Seu nome</span>
                <div className="auth-v2-input">
                  <input
                    name="name"
                    required
                    minLength={2}
                    defaultValue={preview?.name || ""}
                  />
                </div>
              </label>
              <label className="auth-v2-field">
                <span>Senha</span>
                <div className="auth-v2-input">
                  <input
                    name="password"
                    type="password"
                    required
                    minLength={8}
                    autoComplete="new-password"
                  />
                </div>
              </label>
              <label className="auth-v2-field">
                <span>Confirmar senha</span>
                <div className="auth-v2-input">
                  <input
                    name="confirm"
                    type="password"
                    required
                    minLength={8}
                    autoComplete="new-password"
                  />
                </div>
              </label>
              {error ? <p className="auth-v2-error">{error}</p> : null}
              {message ? <p className="success">{message}</p> : null}
              <button type="submit" className="auth-v2-submit" disabled={busy}>
                {busy ? "Ativando…" : "Ativar minha conta"}
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

export default function AcceptInvitePage() {
  return (
    <LocaleProvider>
      <Suspense fallback={<main className="auth-v2"><p>Carregando…</p></main>}>
        <AcceptForm />
      </Suspense>
    </LocaleProvider>
  );
}
