"use client";

import Link from "next/link";
import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { ApiError, register } from "../lib/api";
import { LanguagePicker, LocaleProvider, useLocale } from "../lib/locale";

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
      <rect x="5" y="10" width="14" height="9.5" rx="2" stroke="#ffc107" strokeWidth="1.5" />
      <path d="M8 10V7.8a4 4 0 0 1 8 0V10" stroke="#ffc107" strokeWidth="1.5" strokeLinecap="round" />
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

function RegisterForm() {
  const router = useRouter();
  const { t } = useLocale();
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
      setError(e instanceof ApiError ? e.message : t.registerFail);
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
          <h1>{t.createTitle}</h1>
          <p>{t.createSubtitle}</p>
        </div>

        <LanguagePicker />
      </section>

      <section className="auth-v2-right">
        <div className="auth-v2-card">
          <form onSubmit={onSubmit}>
            <label className="auth-v2-field">
              <span>{t.yourName}</span>
              <div className="auth-v2-input">
                <IconUser />
                <input
                  name="name"
                  required
                  minLength={2}
                  placeholder={t.namePlaceholder}
                />
              </div>
            </label>

            <label className="auth-v2-field">
              <span>{t.companyName}</span>
              <div className="auth-v2-input">
                <IconBuilding />
                <input
                  name="organization_name"
                  required
                  minLength={2}
                  placeholder={t.companyPlaceholder}
                />
              </div>
            </label>

            <label className="auth-v2-field">
              <span>{t.orgLabel}</span>
              <div className="auth-v2-input">
                <IconBuilding />
                <input
                  name="organization_slug"
                  required
                  pattern="[a-z0-9-]+"
                  placeholder={t.orgPlaceholder}
                />
              </div>
            </label>

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
                  autoComplete="new-password"
                  placeholder={t.passwordPlaceholder}
                />
                <button
                  type="button"
                  className="icon-btn"
                  onClick={() => setShowPassword((v) => !v)}
                >
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden>
                    {showPassword ? (
                      <path d="M3 3l18 18" stroke="#8b8b93" strokeWidth="1.5" strokeLinecap="round" />
                    ) : (
                      <>
                        <path d="M2.5 12S6 5.5 12 5.5 21.5 12 21.5 12 18 18.5 12 18.5 2.5 12 2.5 12Z" stroke="#8b8b93" strokeWidth="1.5" />
                        <circle cx="12" cy="12" r="2.8" stroke="#8b8b93" strokeWidth="1.5" />
                      </>
                    )}
                  </svg>
                </button>
              </div>
            </label>

            {error ? <p className="auth-v2-error">{error}</p> : null}

            <button type="submit" className="auth-v2-submit" disabled={busy}>
              {busy ? t.creating : t.startTrial}
            </button>
          </form>

          <p className="auth-v2-terms">
            {t.termsPrefix} <a href="#termos">{t.termsLink}</a>.
          </p>
          <p className="auth-v2-switch">
            {t.hasAccount} <Link href="/login">{t.signIn}</Link>
          </p>
        </div>
      </section>
    </main>
  );
}

export default function RegisterPage() {
  return (
    <LocaleProvider>
      <RegisterForm />
    </LocaleProvider>
  );
}
