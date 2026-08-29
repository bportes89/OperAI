"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { apiJson } from "../../lib/api";
import type { TeamMember } from "../../lib/types";

export default function TeamPage() {
  const [team, setTeam] = useState<TeamMember[]>([]);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [tempPassword, setTempPassword] = useState<{
    email: string;
    password: string;
  } | null>(null);
  const [inviteLink, setInviteLink] = useState<{
    email: string;
    url: string;
  } | null>(null);
  const [busy, setBusy] = useState(false);
  const [setPasswordNow, setSetPasswordNow] = useState(false);

  const load = useCallback(async () => {
    try {
      setError("");
      setTeam(await apiJson<TeamMember[]>("/api/v1/team/members"));
    } catch (e) {
      setError((e as Error).message);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function createMember(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setMessage("");
    setTempPassword(null);
    setInviteLink(null);
    const form = event.currentTarget;
    const raw = Object.fromEntries(new FormData(form));
    const payload: Record<string, unknown> = {
      name: raw.name,
      email: raw.email,
      role: raw.role,
    };
    if (setPasswordNow && raw.password) {
      payload.password = raw.password;
    }
    try {
      const result = await apiJson<{
        message?: string;
        invite_url?: string | null;
        pending?: boolean;
      }>("/api/v1/team/members", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      form.reset();
      setSetPasswordNow(false);
      setMessage(result.message || "Membro adicionado.");
      if (result.invite_url) {
        setInviteLink({
          email: String(raw.email),
          url: result.invite_url,
        });
      }
      await load();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function toggleMember(item: TeamMember) {
    try {
      await apiJson(`/api/v1/team/members/${item.membership_id}`, {
        method: "PATCH",
        body: JSON.stringify({ active: !item.active }),
      });
      await load();
    } catch (e) {
      setError((e as Error).message);
    }
  }

  async function resetPassword(item: TeamMember) {
    if (
      !window.confirm(
        `Gerar senha temporária para ${item.name} (${item.email})? Sessões atuais serão encerradas.`,
      )
    ) {
      return;
    }
    setBusy(true);
    setError("");
    setMessage("");
    setTempPassword(null);
    setInviteLink(null);
    try {
      const result = await apiJson<{
        email: string;
        temporary_password: string;
        message?: string;
      }>(`/api/v1/team/members/${item.membership_id}/reset-password`, {
        method: "POST",
        body: "{}",
      });
      setTempPassword({
        email: result.email,
        password: result.temporary_password,
      });
      setMessage(result.message || "Senha temporária gerada.");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function resendInvite(item: TeamMember) {
    setBusy(true);
    setError("");
    setMessage("");
    setTempPassword(null);
    setInviteLink(null);
    try {
      const result = await apiJson<{
        email: string;
        invite_url: string;
        message?: string;
      }>(`/api/v1/team/members/${item.membership_id}/invite`, {
        method: "POST",
        body: "{}",
      });
      setInviteLink({ email: result.email, url: result.invite_url });
      setMessage(result.message || "Convite gerado.");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <header>
        <div>
          <span>ACESSOS</span>
          <h1>Equipe</h1>
        </div>
      </header>
      {error && <p className="error">{error}</p>}
      {message && <p className="success">{message}</p>}
      {tempPassword && (
        <div className="secret-box" style={{ marginBottom: 16 }}>
          <strong>Senha temporária — copie agora</strong>
          <p style={{ margin: "8px 0" }}>
            {tempPassword.email}
            <br />
            <code>{tempPassword.password}</code>
          </p>
          <button
            type="button"
            className="secondary"
            onClick={() =>
              void navigator.clipboard.writeText(tempPassword.password)
            }
          >
            Copiar senha
          </button>
        </div>
      )}
      {inviteLink && (
        <div className="secret-box" style={{ marginBottom: 16 }}>
          <strong>Link de convite (7 dias) — envie ao colega</strong>
          <p style={{ margin: "8px 0", wordBreak: "break-all" }}>
            {inviteLink.email}
            <br />
            <a href={inviteLink.url}>{inviteLink.url}</a>
          </p>
          <button
            type="button"
            className="secondary"
            onClick={() => void navigator.clipboard.writeText(inviteLink.url)}
          >
            Copiar link
          </button>
        </div>
      )}

      <div className="content-grid">
        <article className="panel">
          <div className="panel-title">
            <div>
              <span>MEMBROS</span>
              <h2>Pessoas com acesso</h2>
            </div>
          </div>
          {team.length === 0 ? (
            <div className="empty">
              <strong>Nenhum membro</strong>
              <p>Convide colegas com papéis e permissões.</p>
            </div>
          ) : (
            team.map((item) => (
              <div className="team-row" key={item.membership_id}>
                <div>
                  <strong>{item.name}</strong>
                  <small>
                    {item.email} · {item.role}
                    {item.pending ? " · convite pendente" : ""}
                  </small>
                </div>
                <span className={item.active ? "online" : "stage"}>
                  {item.pending
                    ? "pendente"
                    : item.active
                      ? "ativo"
                      : "inativo"}
                </span>
                <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                  {item.pending && (
                    <button
                      type="button"
                      disabled={busy}
                      onClick={() => void resendInvite(item)}
                    >
                      Reenviar convite
                    </button>
                  )}
                  {!item.pending && (
                    <button
                      type="button"
                      disabled={busy}
                      onClick={() => void resetPassword(item)}
                    >
                      Redefinir senha
                    </button>
                  )}
                  <button type="button" onClick={() => void toggleMember(item)}>
                    {item.active ? "Desativar" : "Ativar"}
                  </button>
                </div>
              </div>
            ))
          )}
        </article>

        <article className="panel">
          <div className="panel-title">
            <div>
              <span>CONVIDAR</span>
              <h2>Novo membro</h2>
            </div>
          </div>
          <p style={{ marginTop: 0, opacity: 0.85, lineHeight: 1.5 }}>
            Por padrão geramos um link de convite (7 dias) para o colega criar a
            própria senha. Sem SMTP: copie e envie no WhatsApp/e-mail.
          </p>
          <form onSubmit={createMember}>
            <label>
              Nome
              <input name="name" required minLength={2} />
            </label>
            <label>
              E-mail
              <input name="email" type="email" required />
            </label>
            <label>
              Papel
              <select name="role" defaultValue="operator">
                <option value="admin">Admin</option>
                <option value="manager">Manager</option>
                <option value="operator">Operator</option>
                <option value="viewer">Viewer</option>
              </select>
            </label>
            <label style={{ display: "flex", gap: 8, alignItems: "center" }}>
              <input
                type="checkbox"
                checked={setPasswordNow}
                onChange={(e) => setSetPasswordNow(e.target.checked)}
              />
              Definir senha agora (sem link)
            </label>
            {setPasswordNow && (
              <label>
                Senha temporária
                <input name="password" type="password" required minLength={8} />
              </label>
            )}
            <button className="primary" disabled={busy}>
              {setPasswordNow ? "Adicionar membro" : "Gerar convite"}
            </button>
          </form>
        </article>
      </div>
    </>
  );
}
