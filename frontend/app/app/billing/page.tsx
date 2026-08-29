"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { apiJson } from "../../lib/api";
import { money } from "../../lib/format";
import type {
  BillingPlan,
  CheckoutResult,
  Subscription,
} from "../../lib/types";

function normalizePlan(raw: Record<string, unknown>): BillingPlan {
  const price =
    Number(raw.price_cents ?? raw.monthly_price_cents ?? 0) || 0;
  let features: string[] = [];
  if (Array.isArray(raw.features)) features = raw.features.map(String);
  else if (raw.features && typeof raw.features === "object") {
    features = Object.keys(raw.features as object);
  }
  return {
    slug: String(raw.slug ?? ""),
    name: String(raw.name ?? raw.slug ?? "Plano"),
    price_cents: price,
    currency: String(raw.currency ?? "BRL"),
    limits: (raw.limits as Record<string, number>) || undefined,
    features,
    active: raw.active !== false,
  };
}

export default function BillingPage() {
  const [plans, setPlans] = useState<BillingPlan[]>([]);
  const [subscription, setSubscription] = useState<Subscription | null>(null);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [localSubId, setLocalSubId] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    const errors: string[] = [];

    try {
      const planRaw = await apiJson<Record<string, unknown>[]>(
        "/api/v1/billing/plans",
      );
      setPlans((planRaw || []).map(normalizePlan).filter((p) => p.slug));
    } catch (e) {
      setPlans([]);
      errors.push(
        "Não foi possível carregar os planos agora. Atualize a página em instantes.",
      );
      if (e instanceof Error && e.message) {
        /* keep human message only */
      }
    }

    try {
      const sub = await apiJson<Subscription & { plan?: Record<string, unknown> }>(
        "/api/v1/billing/subscription",
      );
      const plan = sub.plan
        ? normalizePlan(sub.plan as unknown as Record<string, unknown>)
        : null;
      setSubscription({
        ...sub,
        plan_slug: sub.plan_slug ?? plan?.slug,
        plan,
      });
    } catch {
      setSubscription(null);
      errors.push("Não foi possível carregar o status da assinatura.");
    }

    if (errors.length) setError(errors.join(" "));
    setLoading(false);
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function checkout(planSlug: string) {
    setBusy(true);
    setError("");
    setMessage("");
    try {
      const result = await apiJson<CheckoutResult>("/api/v1/billing/checkout", {
        method: "POST",
        body: JSON.stringify({ plan_slug: planSlug }),
      });
      if (result.mode === "local") {
        setLocalSubId(result.subscription_id ?? null);
        setMessage(
          "Ambiente de desenvolvimento: confirme abaixo para ativar a assinatura.",
        );
      } else {
        const url = result.checkout_url || result.payment_url;
        if (url) {
          window.location.href = url;
          return;
        }
        setMessage("Checkout criado. Aguarde a confirmação do pagamento.");
      }
      await load();
    } catch (e) {
      setError(
        (e as Error).message ||
          "Não foi possível iniciar a assinatura. Tente novamente.",
      );
    } finally {
      setBusy(false);
    }
  }

  async function confirmLocal(event: FormEvent) {
    event.preventDefault();
    if (!localSubId) return;
    setBusy(true);
    setError("");
    try {
      await apiJson("/api/v1/billing/confirm-local", {
        method: "POST",
        body: JSON.stringify({ subscription_id: localSubId }),
      });
      setMessage("Assinatura ativada.");
      setLocalSubId(null);
      await load();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  const planFeatures = (plan: BillingPlan) => {
    if (Array.isArray(plan.features)) return plan.features.map(String);
    return [];
  };

  return (
    <>
      <header>
        <div>
          <span>CONTA</span>
          <h1>Planos e assinatura</h1>
        </div>
        <button type="button" className="secondary" onClick={() => void load()}>
          Atualizar
        </button>
      </header>
      {error && <p className="error">{error}</p>}
      {message && <p className="success">{message}</p>}

      <article className="panel" style={{ marginBottom: 18 }}>
        <div className="panel-title">
          <div>
            <span>ASSINATURA</span>
            <h2>Status atual</h2>
          </div>
        </div>
        {loading && !subscription ? (
          <div className="empty">Carregando assinatura…</div>
        ) : subscription ? (
          <div className="kpi-list">
            <div>
              <span>Plano</span>
              <strong>
                {subscription.plan?.name ??
                  subscription.plan_slug ??
                  "—"}
              </strong>
            </div>
            <div>
              <span>Status</span>
              <strong>{subscription.status}</strong>
            </div>
            <div>
              <span>Acesso</span>
              <strong>{subscription.access ? "Liberado" : "Bloqueado"}</strong>
            </div>
            <div>
              <span>Trial até</span>
              <strong>
                {subscription.trial_ends_at
                  ? new Date(
                      subscription.trial_ends_at.includes("T")
                        ? subscription.trial_ends_at
                        : `${subscription.trial_ends_at}T12:00:00`,
                    ).toLocaleDateString("pt-BR")
                  : "—"}
              </strong>
            </div>
          </div>
        ) : (
          <div className="empty">
            <strong>Assinatura indisponível</strong>
            <p>Atualize a página ou tente novamente em instantes.</p>
          </div>
        )}
        {subscription?.reason && (
          <p className="pricing-note">{subscription.reason}</p>
        )}
      </article>

      <div className="pricing-grid" style={{ marginBottom: 18 }}>
        {loading && plans.length === 0 ? (
          <article className="panel">
            <div className="empty">Carregando planos…</div>
          </article>
        ) : plans.length === 0 ? (
          <article className="panel">
            <div className="empty">
              <strong>Planos temporariamente indisponíveis</strong>
              <p>
                Não conseguimos listar os planos agora. Clique em Atualizar ou
                tente novamente em alguns segundos.
              </p>
            </div>
          </article>
        ) : (
          plans.map((plan) => (
            <article key={plan.slug} className="price-card">
              <h3>{plan.name}</h3>
              <div className="amount">
                {money(plan.price_cents)}
                <small>/mês</small>
              </div>
              <ul>
                {planFeatures(plan).length > 0 ? (
                  planFeatures(plan).map((f) => <li key={f}>{f}</li>)
                ) : (
                  <li>Recursos do plano {plan.name}</li>
                )}
              </ul>
              <button
                type="button"
                className="primary"
                disabled={busy || loading}
                onClick={() => void checkout(plan.slug)}
              >
                Assinar {plan.name}
              </button>
            </article>
          ))
        )}
      </div>

      {localSubId && (
        <article className="panel">
          <div className="panel-title">
            <div>
              <span>DESENVOLVIMENTO</span>
              <h2>Confirmar pagamento</h2>
            </div>
          </div>
          <p className="pricing-note">
            Ambiente sem cobrança real. Confirme para marcar a assinatura como
            ativa.
          </p>
          <form onSubmit={confirmLocal}>
            <button className="primary" disabled={busy}>
              Confirmar assinatura
            </button>
          </form>
        </article>
      )}
    </>
  );
}
