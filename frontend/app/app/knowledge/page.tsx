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
          <span>RAG</span>
          <h1>Conhecimento</h1>
        </div>
      </header>
      {error && <p className="error">{error}</p>}

      <div className="content-grid">
        <article className="panel">
          <div className="panel-title">
            <div>
              <span>DOCUMENTOS</span>
              <h2>Base processada</h2>
            </div>
          </div>
          <form className="search-form" onSubmit={searchKnowledge}>
            <input
              name="q"
              required
              minLength={2}
              placeholder="Buscar na base..."
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
              <strong>Base vazia</strong>
              <p>
                Suba um FAQ ou manual para os agentes responderem com contexto
                da empresa.
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
                <span>{doc.chunk_count} chunks</span>
              </div>
            ))
          )}
        </article>

        <article className="panel" id="ingest">
          <div className="panel-title">
            <div>
              <span>INGESTÃO</span>
              <h2>Adicionar documento</h2>
            </div>
          </div>
          <form onSubmit={createDocument}>
            <label>
              Título
              <input name="title" required minLength={2} />
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
              <textarea name="content" required minLength={20} />
            </label>
            <button className="primary" disabled={busy}>
              Processar documento
            </button>
          </form>
        </article>
      </div>
    </>
  );
}
