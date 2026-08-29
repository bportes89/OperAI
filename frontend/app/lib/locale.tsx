"use client";

import {
  createContext,
  ReactNode,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

export type Locale = "pt-BR" | "en";

const LOCALE_KEY = "operai_locale";

const LABELS: Record<Locale, string> = {
  "pt-BR": "Português (Brasil)",
  en: "English",
};

type AuthCopy = {
  accessTitle: string;
  accessSubtitle: string;
  createTitle: string;
  createSubtitle: string;
  tabEmail: string;
  tabOrg: string;
  orgLabel: string;
  orgPlaceholder: string;
  emailLabel: string;
  emailPlaceholder: string;
  passwordLabel: string;
  passwordPlaceholder: string;
  forgotPassword: string;
  enter: string;
  entering: string;
  termsPrefix: string;
  termsLink: string;
  noAccount: string;
  createCompany: string;
  hasAccount: string;
  signIn: string;
  yourName: string;
  companyName: string;
  startTrial: string;
  creating: string;
  namePlaceholder: string;
  companyPlaceholder: string;
  forgotSoon: string;
  orgRequired: string;
  loginFail: string;
  registerFail: string;
};

const COPY: Record<Locale, AuthCopy> = {
  "pt-BR": {
    accessTitle: "Acesse sua plataforma",
    accessSubtitle: "Entre com sua conta para continuar",
    createTitle: "Crie sua plataforma",
    createSubtitle: "Trial incluso para montar sua equipe de IA",
    tabEmail: "E-mail",
    tabOrg: "Entrar com organização",
    orgLabel: "Identificador da empresa",
    orgPlaceholder: "minha-empresa",
    emailLabel: "E-mail",
    emailPlaceholder: "Seu endereço de e-mail",
    passwordLabel: "Senha",
    passwordPlaceholder: "Sua senha",
    forgotPassword: "Esqueceu sua senha?",
    enter: "Entrar",
    entering: "Entrando...",
    termsPrefix: "Ao fazer login, você concorda com nossos",
    termsLink: "Termos e Condições",
    noAccount: "Não tem conta?",
    createCompany: "Criar empresa",
    hasAccount: "Já tem conta?",
    signIn: "Entrar",
    yourName: "Seu nome",
    companyName: "Nome da empresa",
    startTrial: "Começar trial",
    creating: "Criando...",
    namePlaceholder: "Nome completo",
    companyPlaceholder: "Nome da empresa",
    forgotSoon: "Use a recuperação de senha ou peça ao administrador na Equipe.",
    orgRequired: "Informe o identificador da empresa.",
    loginFail: "Falha ao entrar. Tente novamente.",
    registerFail: "Não foi possível criar a conta.",
  },
  en: {
    accessTitle: "Access your platform",
    accessSubtitle: "Sign in with your account to continue",
    createTitle: "Create your platform",
    createSubtitle: "Trial included to set up your AI team",
    tabEmail: "Email",
    tabOrg: "Sign in with organization",
    orgLabel: "Organization ID",
    orgPlaceholder: "my-company",
    emailLabel: "Email",
    emailPlaceholder: "Your email address",
    passwordLabel: "Password",
    passwordPlaceholder: "Your password",
    forgotPassword: "Forgot your password?",
    enter: "Sign in",
    entering: "Signing in...",
    termsPrefix: "By signing in, you agree to our",
    termsLink: "Terms and Conditions",
    noAccount: "Don't have an account?",
    createCompany: "Create company",
    hasAccount: "Already have an account?",
    signIn: "Sign in",
    yourName: "Your name",
    companyName: "Company name",
    startTrial: "Start trial",
    creating: "Creating...",
    namePlaceholder: "Full name",
    companyPlaceholder: "Company name",
    forgotSoon: "Use password recovery or ask your admin in Team.",
    orgRequired: "Enter your organization ID.",
    loginFail: "Could not sign in. Try again.",
    registerFail: "Could not create the account.",
  },
};

type LocaleContextValue = {
  locale: Locale;
  setLocale: (locale: Locale) => void;
  t: AuthCopy;
  label: string;
};

const LocaleContext = createContext<LocaleContextValue | null>(null);

export function LocaleProvider({ children }: { children: ReactNode }) {
  const [locale, setLocaleState] = useState<Locale>("pt-BR");

  useEffect(() => {
    const saved = localStorage.getItem(LOCALE_KEY);
    if (saved === "en" || saved === "pt-BR") setLocaleState(saved);
  }, []);

  const setLocale = useCallback((next: Locale) => {
    setLocaleState(next);
    localStorage.setItem(LOCALE_KEY, next);
    document.documentElement.lang = next === "en" ? "en" : "pt-BR";
  }, []);

  const value = useMemo(
    () => ({
      locale,
      setLocale,
      t: COPY[locale],
      label: LABELS[locale],
    }),
    [locale, setLocale],
  );

  return (
    <LocaleContext.Provider value={value}>{children}</LocaleContext.Provider>
  );
}

export function useLocale() {
  const ctx = useContext(LocaleContext);
  if (!ctx) throw new Error("useLocale must be used within LocaleProvider");
  return ctx;
}

function IconGlobe() {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" aria-hidden>
      <circle cx="12" cy="12" r="8.5" stroke="#4d8cff" strokeWidth="1.5" />
      <path
        d="M3.5 12h17M12 3.5c2.4 2.6 3.6 5.4 3.6 8.5s-1.2 5.9-3.6 8.5c-2.4-2.6-3.6-5.4-3.6-8.5S9.6 6.1 12 3.5Z"
        stroke="#4d8cff"
        strokeWidth="1.5"
      />
    </svg>
  );
}

export function LanguagePicker() {
  const { locale, setLocale, label } = useLocale();
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function onDocClick(event: MouseEvent) {
      if (!rootRef.current?.contains(event.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onDocClick);
    return () => document.removeEventListener("mousedown", onDocClick);
  }, []);

  return (
    <div className={`auth-v2-lang-wrap${open ? " open" : ""}`} ref={rootRef}>
      <button
        type="button"
        className="auth-v2-lang"
        aria-haspopup="listbox"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
      >
        <IconGlobe />
        <span>{label}</span>
        <span className="auth-v2-lang-caret" aria-hidden>
          ▼
        </span>
      </button>
      {open ? (
        <ul className="auth-v2-lang-menu" role="listbox" aria-label="Idioma">
          {(Object.keys(LABELS) as Locale[]).map((code) => (
            <li key={code}>
              <button
                type="button"
                role="option"
                aria-selected={locale === code}
                className={locale === code ? "selected" : ""}
                onClick={() => {
                  setLocale(code);
                  setOpen(false);
                }}
              >
                {LABELS[code]}
              </button>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}
