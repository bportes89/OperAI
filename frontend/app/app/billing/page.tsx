"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { apiJson } from "../../lib/api";
import { money } from "../../lib/format";
import type {
  BillingPlan,
  CheckoutResult,
  Subscription,
} from "../../lib/types";

export default function BillingPage() {
  const [plans, setPlans] = useState<BillingPlan[]>([]);
  const [subscription, setSubscription] = useState<Subscription | null>(null);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [localSubId, setLocalSubId] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setError("");
      const [planList, sub] = await Promise.all([
        apiJson<BillingPlan[]>("/api/v1/billing/plans"),
        apiJson<Subscription>("/api/v1/billing/subscription"),
      ]);
      setPlans(planList);
      setSubscription(sub);
    } catch (e) {
      setError((e as Error).message);
    }
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
          "Modo local: confirme abaixo para ativar a assinatura de desenvolvimento.",
        );
      } else {
        const url = result.checkout_url || result.payment_url;
        if (url) {
          window.location.href = url;
          return;
        }
        setMessage("Checkout criado. Aguarde confirmação do pagamento.");
      }
      await load();
    } catch (e) {
      setError((e as Error).message);
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
      setMessage("Assinatura local ativada.");
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
    if (plan.features && typeof plan.features === "object") {
      return Object.keys(plan.features);
    }
    return [];
  };

  return (
    <>
      <header>
        <div>
          <span>CONTA</span>
          <h1>Billing</h1>
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
        {subscription ? (
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
          <div className="empty">Carregando assinatura...</div>
        )}
        {subscription?.reason && (
          <p className="pricing-note">{subscription.reason}</p>
        )}
      </article>

      <div className="pricing-grid" style={{ marginBottom: 18 }}>
        {plans.length === 0 ? (
          <article className="panel">
            <div className="empty">
              <strong>Planos indisponíveis</strong>
              <p>Não foi possível carregar os planos do backend.</p>
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
                disabled={busy}
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
              <span>MODO LOCAL</span>
              <h2>Confirmar pagamento</h2>
            </div>
          </div>
          <p className="pricing-note">
            Ambiente de desenvolvimento (Asaas sem chave). Confirme para marcar
            a assinatura como ativa.
          </p>
          <form onSubmit={confirmLocal}>
            <button className="primary" disabled={busy}>
              Confirmar assinatura local
            </button>
          </form>
        </article>
      )}
    </>
  );
}
