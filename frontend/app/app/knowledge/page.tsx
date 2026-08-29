"use client";

import Link from "next/link";
import { FormEvent, useCallback, useEffect, useState } from "react";
import { apiJson } from "../../lib/api";
import type { KnowledgeDocument, SearchHit } from "../../lib/types";

export default function KnowledgePage() {
  const [documents, setDocuments] = useState<KnowledgeDocument[]>([]);
  const [hits, setHits] = useState<SearchHit[]>([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      setError("");
      setDocuments(await apiJson<KnowledgeDocument[]>("/api/v1/knowledge/documents"));
    } catch (e) {
      setError((e as Error).message);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function createDocument(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    const form = event.currentTarget;
    try {
      await apiJson("/api/v1/knowledge/documents", {
        method: "POST",
        body: JSON.stringify(Object.fromEntries(new FormData(form))),
      });
      form.reset();
      await load();
      try {
        await apiJson("/api/v1/settings/onboarding", {
          method: "PATCH",
          body: JSON.stringify({
            checklist: { faq: true },
            step: "faq",
          }),
        });
      } catch {
        /* optional */
      }
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function searchKnowledge(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const q = String(new FormData(event.currentTarget).get("q") ?? "");
    try {
      setHits(
        await apiJson<SearchHit[]>(
          `/api/v1/knowledge/search?q=${encodeURIComponent(q)}`,
        ),
      );
    } catch (e) {
      setError((e as Error).message);
    }
  }

  return (
    <>
      <header>
        <div>
          <span>BASE DA EMPRESA</span>
          <h1>Conhecimento</h1>
        </div>
      </header>
      {error && <p className="error">{error}</p>}

      <article className="panel" style={{ marginBottom: 16 }}>
        <p style={{ margin: 0, lineHeight: 1.55, opacity: 0.9 }}>
          Aqui fica o que a sua empresa sabe: FAQ, políticas e preços. Os
          agentes usam isso para responder no tom do negócio — sem inventar o
          que não está publicado.
        </p>
      </article>

      <div className="content-grid">
        <article className="panel">
          <div className="panel-title">
            <div>
              <span>PUBLICADOS</span>
              <h2>Conteúdos na base</h2>
            </div>
          </div>
          <form className="search-form" onSubmit={searchKnowledge}>
            <input
              name="q"
              required
              minLength={2}
              placeholder="Buscar no conhecimento da empresa…"
            />
            <button className="primary" type="submit">
              Buscar
            </button>
          </form>
          {hits.length > 0 ? (
            <div className="knowledge-list">
              {hits.map((hit) => (
                <div className="knowledge-hit" key={hit.chunk_id}>
                  <strong>{hit.document}</strong>
                  <p>{hit.content}</p>
                </div>
              ))}
            </div>
          ) : documents.length === 0 ? (
            <div className="empty">
              <strong>Base ainda vazia</strong>
              <p>
                Cole um FAQ curto para começar. Em breve: upload de PDF e Word.
              </p>
              <Link className="primary" href="#ingest">
                Adicionar FAQ
              </Link>
            </div>
          ) : (
            documents.map((doc) => (
              <div className="knowledge-doc" key={doc.id}>
                <div>
                  <strong>{doc.title}</strong>
                  <small>{doc.source_type}</small>
                </div>
                <span>{doc.chunk_count} trechos</span>
              </div>
            ))
          )}
        </article>

        <article className="panel" id="ingest">
          <div className="panel-title">
            <div>
              <span>NOVO</span>
              <h2>Publicar conteúdo</h2>
            </div>
          </div>
          <form onSubmit={createDocument}>
            <label>
              Título
              <input name="title" required minLength={2} placeholder="Ex.: FAQ comercial" />
            </label>
            <label>
              Tipo
              <select name="source_type" defaultValue="faq">
                <option value="faq">FAQ</option>
                <option value="text">Texto</option>
                <option value="policy">Política</option>
                <option value="manual">Manual</option>
              </select>
            </label>
            <label>
              Conteúdo
              <textarea
                name="content"
                required
                minLength={20}
                placeholder="Cole aqui perguntas e respostas, políticas ou scripts…"
              />
            </label>
            <button className="primary" disabled={busy}>
              Publicar na base
            </button>
          </form>
        </article>
      </div>
    </>
  );
}
