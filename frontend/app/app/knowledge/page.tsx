"use client";

import Link from "next/link";
import { FormEvent, useCallback, useEffect, useState } from "react";
import { apiJson } from "../../lib/api";
import type { BrandKit, KnowledgeDocument, SearchHit } from "../../lib/types";

const EMPTY_KIT: BrandKit = {
  configured: false,
  brand_name: "",
  tagline: "",
  voice_tone: "",
  primary_color: "",
  secondary_color: "",
  logo_url: "",
  avoid: "",
  notes: "",
};

export default function KnowledgePage() {
  const [documents, setDocuments] = useState<KnowledgeDocument[]>([]);
  const [kit, setKit] = useState<BrandKit>(EMPTY_KIT);
  const [hits, setHits] = useState<SearchHit[]>([]);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [kitBusy, setKitBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      setError("");
      const [docs, brand] = await Promise.all([
        apiJson<KnowledgeDocument[]>("/api/v1/knowledge/documents"),
        apiJson<BrandKit>("/api/v1/settings/brand-kit"),
      ]);
      setDocuments(docs);
      setKit(brand);
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

  async function saveBrandKit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setKitBusy(true);
    setError("");
    setMessage("");
    const data = Object.fromEntries(new FormData(event.currentTarget));
    try {
      const saved = await apiJson<BrandKit>("/api/v1/settings/brand-kit", {
        method: "PUT",
        body: JSON.stringify(data),
      });
      setKit(saved);
      setMessage(
        saved.configured
          ? "Kit de marca salvo — Marketing e agentes já usam este tom."
          : "Kit de marca limpo.",
      );
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setKitBusy(false);
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
          Aqui ficam a identidade da marca e o que a empresa sabe (FAQ,
          políticas, preços). Marketing e agentes usam o kit e os documentos
          para falar no tom do negócio — sem inventar o que não está
          publicado.
        </p>
      </article>

      <article className="panel" id="brand" style={{ marginBottom: 18 }}>
        <div className="panel-title">
          <div>
            <span>IDENTIDADE</span>
            <h2>Kit de marca</h2>
          </div>
          {kit.configured && kit.primary_color ? (
            <span
              title={kit.primary_color}
              style={{
                width: 28,
                height: 28,
                borderRadius: 6,
                background: kit.primary_color,
                border: "1px solid rgba(0,0,0,.12)",
                flexShrink: 0,
              }}
            />
          ) : null}
        </div>
        <p style={{ marginTop: 0, opacity: 0.85, lineHeight: 1.5 }}>
          Nome, tom, cores e o que evitar. Vale para posts, WhatsApp e
          cobrança — preencha uma vez.
        </p>
        <form
          key={`${kit.updated_at ?? "new"}-${kit.brand_name}`}
          onSubmit={saveBrandKit}
          style={{ display: "grid", gap: 12 }}
        >
          <div
            style={{
              display: "grid",
              gap: 12,
              gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
            }}
          >
            <label>
              Nome da marca
              <input
                name="brand_name"
                defaultValue={kit.brand_name}
                placeholder="Ex.: Café do Bairro"
                maxLength={120}
              />
            </label>
            <label>
              Slogan
              <input
                name="tagline"
                defaultValue={kit.tagline}
                placeholder="Ex.: Café fresco, conversa boa"
                maxLength={240}
              />
            </label>
          </div>
          <label>
            Tom de voz
            <textarea
              name="voice_tone"
              defaultValue={kit.voice_tone}
              placeholder="Ex.: próximo e descontraído, sem gírias exageradas; trate o cliente por você"
              maxLength={2000}
            />
          </label>
          <div
            style={{
              display: "grid",
              gap: 12,
              gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))",
            }}
          >
            <label>
              Cor primária
              <input
                name="primary_color"
                defaultValue={kit.primary_color}
                placeholder="#1A5F4A"
                maxLength={7}
              />
            </label>
            <label>
              Cor secundária
              <input
                name="secondary_color"
                defaultValue={kit.secondary_color}
                placeholder="#F5E6C8"
                maxLength={7}
              />
            </label>
            <label>
              URL do logo
              <input
                name="logo_url"
                defaultValue={kit.logo_url}
                placeholder="https://…"
                maxLength={1000}
              />
            </label>
          </div>
          <label>
            Evitar / nunca dizer
            <textarea
              name="avoid"
              defaultValue={kit.avoid}
              placeholder="Ex.: não prometer prazo sem confirmar; evitar ‘barato’ e ‘garantia vitalícia’"
              maxLength={2000}
            />
          </label>
          <label>
            Notas extras (materiais, tipografia, referências)
            <textarea
              name="notes"
              defaultValue={kit.notes}
              placeholder="Ex.: fotos com luz natural; tipografia arredondada; Instagram @cafe…"
              maxLength={4000}
            />
          </label>
          <button className="primary" disabled={kitBusy}>
            {kitBusy ? "Salvando…" : "Salvar kit de marca"}
          </button>
        </form>
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
