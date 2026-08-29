"use client";

import Link from "next/link";
import { FormEvent, useCallback, useEffect, useState } from "react";
import { apiJson } from "../../lib/api";
import type { KnowledgeDocument, SearchHit } from "../../lib/types";

export default function KnowledgePage() {
  const [documents, setDocuments] = useState<KnowledgeDocument[]>([]);
  const [hits, setHits] = useState<SearchHit[]>([]);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
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

  async function markFaqDone() {
    try {
      await apiJson("/api/v1/settings/onboarding", {
        method: "PATCH",
        body: JSON.stringify({ checklist: { faq: true }, step: "faq" }),
      });
    } catch {
      /* optional — checklist real vem da detecção */
    }
  }

  async function createDocument(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setMessage("");
    const form = event.currentTarget;
    try {
      await apiJson("/api/v1/knowledge/documents", {
        method: "POST",
        body: JSON.stringify(Object.fromEntries(new FormData(form))),
      });
      form.reset();
      setMessage("Conteúdo publicado na base.");
      await load();
      await markFaqDone();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function uploadDocument(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setMessage("");
    const form = event.currentTarget;
    const fd = new FormData(form);
    const file = fd.get("file");
    if (!(file instanceof File) || file.size === 0) {
      setError("Escolha um arquivo PDF ou Word (.docx).");
      setBusy(false);
      return;
    }
    try {
      const result = await apiJson<{
        title?: string;
        chunk_count?: number;
        ocr?: boolean;
        meta?: { note?: string; pages?: number };
      }>("/api/v1/knowledge/documents/upload", {
        method: "POST",
        body: fd,
      });
      form.reset();
      if (result.ocr) {
        setMessage(
          `Arquivo “${result.title ?? file.name}” lido por OCR` +
            (result.meta?.pages ? ` (${result.meta.pages} pág.)` : "") +
            ` · ${result.chunk_count ?? "?"} trechos publicados.`,
        );
      } else {
        setMessage(`Arquivo “${file.name}” publicado na base.`);
      }
      await load();
      await markFaqDone();
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
      {message && <p className="success">{message}</p>}

      <article className="panel" style={{ marginBottom: 16 }}>
        <p style={{ margin: 0, lineHeight: 1.55, opacity: 0.9 }}>
          Aqui fica o que a sua empresa sabe: FAQ, políticas e preços. Os
          agentes usam isso para responder no tom do negócio — sem inventar o
          que não está publicado. Você pode colar texto ou enviar PDF/Word.
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
              <p>Cole um FAQ ou envie um PDF/Word ao lado.</p>
              <Link className="primary" href="#ingest">
                Adicionar conteúdo
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

        <div style={{ display: "grid", gap: 18 }}>
          <article className="panel" id="upload">
            <div className="panel-title">
              <div>
                <span>ARQUIVO</span>
                <h2>Enviar PDF ou Word</h2>
              </div>
            </div>
            <p style={{ marginTop: 0, opacity: 0.85, lineHeight: 1.5 }}>
              Extraímos o texto automaticamente (até 5 MB). PDF com texto
              selecionável é o mais rápido; PDF escaneado usa OCR (até 15
              páginas, pt/en) — pode levar alguns segundos.
            </p>
            <form onSubmit={uploadDocument}>
              <label>
                Título (opcional)
                <input name="title" minLength={2} placeholder="Ex.: Manual de atendimento" />
              </label>
              <label>
                Arquivo
                <input
                  name="file"
                  type="file"
                  required
                  accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                />
              </label>
              <button className="primary" disabled={busy}>
                {busy ? "Lendo e publicando…" : "Publicar arquivo"}
              </button>
            </form>
          </article>

          <article className="panel" id="ingest">
            <div className="panel-title">
              <div>
                <span>TEXTO</span>
                <h2>Colar conteúdo</h2>
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
      </div>
    </>
  );
}
