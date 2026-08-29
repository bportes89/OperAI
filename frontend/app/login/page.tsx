"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ApiError, login } from "../lib/api";
import { LanguagePicker, LocaleProvider, useLocale } from "../lib/locale";

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
      <rect x="5" y="10" width="14" height="9.5" rx="2" stroke="#ffc107" strokeWidth="1.5" />
      <path d="M8 10V7.8a4 4 0 0 1 8 0V10" stroke="#ffc107" strokeWidth="1.5" strokeLinecap="round" />
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

function LoginForm() {
  const router = useRouter();
  const { t } = useLocale();
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
      setError(t.orgRequired);
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
            : t.loginFail,
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
          <h1>{t.accessTitle}</h1>
          <p>{t.accessSubtitle}</p>
        </div>

        <LanguagePicker />
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
              {t.tabEmail}
            </button>
            <button
              type="button"
              role="tab"
              className={tab === "org" ? "active" : ""}
              aria-selected={tab === "org"}
              onClick={() => setTab("org")}
            >
              {t.tabOrg}
            </button>
          </div>

          <form onSubmit={onSubmit}>
            {tab === "org" && (
              <label className="auth-v2-field">
                <span>{t.orgLabel}</span>
                <div className="auth-v2-input">
                  <IconBuilding />
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
            )}

            <label className="auth-v2-field">
              <span>{t.emailLabel}</span>
              <div className="auth-v2-input">
                <IconMail />
                <input
                  name="email"
                  type="email"
                  required
                  autoComplete="email"
                  placeholder={t.emailPlaceholder}
                />
              </div>
            </label>

            <label className="auth-v2-field">
              <span>{t.passwordLabel}</span>
              <div className="auth-v2-input">
                <IconLock />
                <input
                  name="password"
                  type={showPassword ? "text" : "password"}
                  required
                  minLength={8}
                  autoComplete="current-password"
                  placeholder={t.passwordPlaceholder}
                />
                <button
                  type="button"
                  className="icon-btn"
                  aria-label={showPassword ? "Hide password" : "Show password"}
                  onClick={() => setShowPassword((v) => !v)}
                >
                  <IconEye off={showPassword} />
                </button>
              </div>
            </label>

            <div className="auth-v2-forgot">
              <Link href="/forgot-password">{t.forgotPassword}</Link>
            </div>

            {error ? <p className="auth-v2-error">{error}</p> : null}

            <button type="submit" className="auth-v2-submit" disabled={busy}>
              {busy ? t.entering : t.enter}
            </button>
          </form>

          <p className="auth-v2-terms">
            {t.termsPrefix} <a href="#termos">{t.termsLink}</a>.
          </p>
          <p className="auth-v2-switch">
            {t.noAccount} <Link href="/register">{t.createCompany}</Link>
          </p>
        </div>
      </section>
    </main>
  );
}

export default function LoginPage() {
  return (
    <LocaleProvider>
      <LoginForm />
    </LocaleProvider>
  );
}
