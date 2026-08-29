"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  ReactNode,
  useCallback,
  useEffect,
  useState,
} from "react";
import { apiJson, getSession, logout } from "../lib/api";
import type { OnboardingState } from "../lib/types";

const NAV = [
  { href: "/app", label: "Visão geral", exact: true },
  { href: "/app/onboarding", label: "Começar" },
  { href: "/app/agents", label: "Agentes" },
  { href: "/app/knowledge", label: "Base da empresa" },
  { href: "/app/inbox", label: "WhatsApp" },
  { href: "/app/crm", label: "CRM" },
  { href: "/app/finance", label: "Cobrança" },
  { href: "/app/marketing", label: "Marketing" },
  { href: "/app/team", label: "Equipe" },
  { href: "/app/billing", label: "Planos" },
  { href: "/app/settings/llm", label: "Inteligência (IA)" },
];

function isSelected(pathname: string, href: string, exact?: boolean) {
  if (exact) return pathname === href;
  return pathname === href || pathname.startsWith(`${href}/`);
}

function onboardingDone(state: OnboardingState | null) {
  if (!state) return true;
  if (state.completed_at) return true;
  const c = state.checklist ?? {};
  return Boolean(c.account && c.llm && c.faq && c.whatsapp && c.agent);
}

export default function AppLayout({ children }: { children: ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [ready, setReady] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const [billingDenied, setBillingDenied] = useState(false);
  const [onboarding, setOnboarding] = useState<OnboardingState | null>(null);

  const refreshOnboarding = useCallback(async () => {
    try {
      const data = await apiJson<OnboardingState>("/api/v1/settings/onboarding");
      setOnboarding(data);
    } catch {
      /* endpoint may still be deploying */
    }
  }, []);

  useEffect(() => {
    if (!getSession()) {
      router.replace("/login");
      return;
    }
    setReady(true);
    void refreshOnboarding();
  }, [router, refreshOnboarding]);

  useEffect(() => {
    const onDenied = () => setBillingDenied(true);
    window.addEventListener("operai:billing-denied", onDenied);
    return () => window.removeEventListener("operai:billing-denied", onDenied);
  }, []);

  useEffect(() => {
    setMenuOpen(false);
  }, [pathname]);

  function handleLogout() {
    logout();
    router.replace("/login");
  }

  if (!ready) {
    return (
      <main className="app-shell">
        <section className="workspace" style={{ padding: 40 }}>
          Carregando...
        </section>
      </main>
    );
  }

  const showOnboardingBanner =
    pathname !== "/app/onboarding" && !onboardingDone(onboarding);

  return (
    <>
      <div className="mobile-bar">
        <img src="/operai-logo.png" alt="OperAI" className="brand-logo-sm" height={28} />
        <button type="button" onClick={() => setMenuOpen(true)}>
          Menu
        </button>
      </div>
      {menuOpen && (
        <div
          className="sidebar-backdrop"
          onClick={() => setMenuOpen(false)}
          aria-hidden
        />
      )}
      <main className="app-shell">
        <aside className={menuOpen ? "open" : ""}>
          <img
            src="/operai-logo.png"
            alt="OperAI"
            className="brand-logo sidebar-logo"
            width={174}
            height={52}
          />
          <nav>
            {NAV.map((item) => (
              <Link
                key={item.href}
                href={item.href}
                className={
                  isSelected(pathname, item.href, item.exact) ? "selected" : ""
                }
              >
                {item.label}
              </Link>
            ))}
          </nav>
          <button className="logout" type="button" onClick={handleLogout}>
            Sair
          </button>
        </aside>
        <section className="workspace">
          {billingDenied && (
            <div className="banner banner-danger">
              <span>
                Seu acesso está limitado pelo plano ou trial. Regularize a
                assinatura para continuar.
              </span>
              <Link href="/app/billing">Ir para Billing</Link>
            </div>
          )}
          {showOnboardingBanner && (
            <div className="banner banner-warn">
              <span>
                Complete o setup: inteligência (IA), base da empresa e WhatsApp
                para colocar a operação no ar.
              </span>
              <Link href="/app/onboarding">Continuar setup</Link>
            </div>
          )}
          {children}
        </section>
      </main>
    </>
  );
}
