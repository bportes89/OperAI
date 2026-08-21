"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { apiJson } from "../../lib/api";
import {
  CAMPAIGN_STATUS_LABELS,
  CAMPAIGN_TRANSITIONS,
  type Campaign,
} from "../../lib/types";

export default function MarketingPage() {
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      setError("");
      setCampaigns(await apiJson<Campaign[]>("/api/v1/marketing/campaigns"));
    } catch (e) {
      setError((e as Error).message);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function createCampaign(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    const form = event.currentTarget;
    const data = Object.fromEntries(new FormData(form));
    try {
      await apiJson("/api/v1/marketing/campaigns", {
        method: "POST",
        body: JSON.stringify({
          name: data.name,
          channel: data.channel,
          audience: data.audience,
          content: data.content,
        }),
      });
      form.reset();
      await load();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function campaignStatus(item: Campaign, status: string) {
    try {
      await apiJson(`/api/v1/marketing/campaigns/${item.id}/status`, {
        method: "PATCH",
        body: JSON.stringify({ status }),
      });
      await load();
    } catch (e) {
      setError((e as Error).message);
    }
  }

  return (
    <>
      <header>
        <div>
          <span>CRESCIMENTO</span>
          <h1>Marketing</h1>
        </div>
      </header>
      {error && <p className="error">{error}</p>}

      <div className="content-grid">
        <article className="panel">
          <div className="panel-title">
            <div>
              <span>CAMPANHAS</span>
              <h2>Ações multicanal</h2>
            </div>
          </div>
          {campaigns.length === 0 ? (
            <div className="empty">
              <strong>Nenhuma campanha</strong>
              <p>Planeje a primeira ação de WhatsApp, e-mail ou social.</p>
            </div>
          ) : (
            campaigns.map((item) => (
              <div className="campaign-card" key={item.id}>
                <div>
                  <strong>{item.name}</strong>
                  <small>
                    {item.channel} · {item.audience}
                  </small>
                </div>
                <span className={`finance-status ${item.status}`}>
                  {item.status}
                </span>
                <p>{item.content}</p>
                <div className="campaign-metrics">
                  <span>{item.sent_count} enviados</span>
                  <span>{item.delivered_count} entregues</span>
                  <span>{item.response_count} respostas</span>
                </div>
                <div className="proposal-actions">
                  {(CAMPAIGN_TRANSITIONS[item.status] ?? []).map((next) => (
                    <button
                      key={next}
                      type="button"
                      onClick={() => void campaignStatus(item, next)}
                    >
                      {CAMPAIGN_STATUS_LABELS[next] ?? next}
                    </button>
                  ))}
                </div>
              </div>
            ))
          )}
        </article>

        <article className="panel">
          <div className="panel-title">
            <div>
              <span>NOVA</span>
              <h2>Planejar ação</h2>
            </div>
          </div>
          <form onSubmit={createCampaign}>
            <label>
              Nome
              <input name="name" required minLength={2} />
            </label>
            <label>
              Canal
              <select name="channel" defaultValue="whatsapp">
                <option value="whatsapp">WhatsApp</option>
                <option value="email">E-mail</option>
                <option value="social">Redes sociais</option>
              </select>
            </label>
            <label>
              Público
              <input
                name="audience"
                required
                minLength={2}
                placeholder="Ex.: leads qualificados"
              />
            </label>
            <label>
              Conteúdo
              <textarea name="content" required minLength={5} />
            </label>
            <button className="primary" disabled={busy}>
              Criar campanha
            </button>
          </form>
        </article>
      </div>
    </>
  );
}
