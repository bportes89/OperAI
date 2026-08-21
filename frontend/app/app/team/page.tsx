"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { apiJson } from "../../lib/api";
import type { TeamMember } from "../../lib/types";

export default function TeamPage() {
  const [team, setTeam] = useState<TeamMember[]>([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

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
    const form = event.currentTarget;
    try {
      await apiJson("/api/v1/team/members", {
        method: "POST",
        body: JSON.stringify(Object.fromEntries(new FormData(form))),
      });
      form.reset();
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

  return (
    <>
      <header>
        <div>
          <span>ACESSOS</span>
          <h1>Equipe</h1>
        </div>
      </header>
      {error && <p className="error">{error}</p>}

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
                  </small>
                </div>
                <span className={item.active ? "online" : "stage"}>
                  {item.active ? "ativo" : "inativo"}
                </span>
                <button type="button" onClick={() => void toggleMember(item)}>
                  {item.active ? "Desativar" : "Ativar"}
                </button>
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
              Senha temporária
              <input name="password" type="password" required minLength={8} />
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
            <button className="primary" disabled={busy}>
              Adicionar membro
            </button>
          </form>
        </article>
      </div>
    </>
  );
}
