"""WhatsApp Cloud API (Meta) — envio, templates e parse de webhook."""
from __future__ import annotations

import httpx

GRAPH_BASE = "https://graph.facebook.com/v21.0"

# Catálogo local sugerido (PME cria no Meta Business com estes nomes)
STARTER_TEMPLATES = [
    {
        "name": "hello_world",
        "language": "en_US",
        "category": "UTILITY",
        "status": "SUGGESTED",
        "body_param_count": 0,
        "blurb": "Template de teste da Meta (sandbox). Útil para validar o envio.",
        "components": [],
    },
    {
        "name": "operai_cobranca_lembrete",
        "language": "pt_BR",
        "category": "UTILITY",
        "status": "SUGGESTED",
        "body_param_count": 3,
        "blurb": "Lembrete de cobrança. Variáveis: 1=nome, 2=valor, 3=vencimento. Crie no Meta com o mesmo nome.",
        "param_hints": ["Nome do cliente", "Valor (ex.: R$ 150,00)", "Vencimento (ex.: 10/09/2026)"],
        "components": [],
    },
    {
        "name": "operai_followup_comercial",
        "language": "pt_BR",
        "category": "MARKETING",
        "status": "SUGGESTED",
        "body_param_count": 2,
        "blurb": "Follow-up comercial. Variáveis: 1=nome, 2=assunto/oferta. Exige aprovação MARKETING na Meta.",
        "param_hints": ["Nome do contato", "Assunto / oferta"],
        "components": [],
    },
]


async def send_text(phone_number_id: str, access_token: str, to_phone: str, text: str) -> dict:
    number = "".join(ch for ch in to_phone if ch.isdigit())
    if not number:
        raise ValueError("Telefone inválido para envio Meta")
    if not phone_number_id.strip() or not access_token.strip():
        raise ValueError("Credenciais Meta incompletas")
    body = {
        "messaging_product": "whatsapp",
        "to": number,
        "type": "text",
        "text": {"body": text[:4096]},
    }
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{GRAPH_BASE}/{phone_number_id.strip()}/messages",
            headers={
                "Authorization": f"Bearer {access_token.strip()}",
                "Content-Type": "application/json",
            },
            json=body,
        )
        response.raise_for_status()
        return response.json()


async def send_template(
    phone_number_id: str,
    access_token: str,
    to_phone: str,
    template_name: str,
    language: str = "pt_BR",
    body_params: list[str] | None = None,
) -> dict:
    number = "".join(ch for ch in to_phone if ch.isdigit())
    if not number:
        raise ValueError("Telefone inválido para envio Meta")
    if not phone_number_id.strip() or not access_token.strip():
        raise ValueError("Credenciais Meta incompletas")
    if not template_name.strip():
        raise ValueError("Nome do template é obrigatório")
    components: list[dict] = []
    if body_params:
        components.append(
            {
                "type": "body",
                "parameters": [{"type": "text", "text": str(p)[:1024]} for p in body_params if str(p).strip()],
            }
        )
    body = {
        "messaging_product": "whatsapp",
        "to": number,
        "type": "template",
        "template": {
            "name": template_name.strip(),
            "language": {"code": (language or "pt_BR").strip()},
            "components": components,
        },
    }
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{GRAPH_BASE}/{phone_number_id.strip()}/messages",
            headers={
                "Authorization": f"Bearer {access_token.strip()}",
                "Content-Type": "application/json",
            },
            json=body,
        )
        response.raise_for_status()
        return response.json()


def _count_body_params(components: list) -> int:
    for c in components or []:
        if isinstance(c, dict) and str(c.get("type", "")).upper() == "BODY":
            text = str(c.get("text") or "")
            # {{1}} {{2}} …
            n = 0
            i = 1
            while f"{{{{{i}}}}}" in text:
                n = i
                i += 1
            return n
    return 0


async def list_message_templates(waba_id: str, access_token: str) -> list[dict]:
    if not waba_id.strip() or not access_token.strip():
        raise ValueError("WABA ID e access token são necessários para listar templates")
    async with httpx.AsyncClient(timeout=45.0) as client:
        response = await client.get(
            f"{GRAPH_BASE}/{waba_id.strip()}/message_templates",
            headers={"Authorization": f"Bearer {access_token.strip()}"},
            params={"limit": 100},
        )
        response.raise_for_status()
        data = response.json()
    out: list[dict] = []
    for t in data.get("data") or []:
        if not isinstance(t, dict):
            continue
        status = str(t.get("status") or "")
        if status and status != "APPROVED":
            continue
        components = t.get("components") or []
        out.append(
            {
                "name": str(t.get("name") or ""),
                "language": str(t.get("language") or "pt_BR"),
                "category": str(t.get("category") or ""),
                "status": status or "APPROVED",
                "body_param_count": _count_body_params(components if isinstance(components, list) else []),
                "blurb": "Template aprovado na sua conta Meta.",
                "components": components,
                "source": "meta",
            }
        )
    return [x for x in out if x["name"]]


def parse_inbound(payload: dict) -> list[dict]:
    """Extrai mensagens de texto do payload oficial da Meta."""
    out: list[dict] = []
    if not isinstance(payload, dict):
        return out
    for entry in payload.get("entry") or []:
        if not isinstance(entry, dict):
            continue
        for change in entry.get("changes") or []:
            if not isinstance(change, dict):
                continue
            value = change.get("value") or {}
            if not isinstance(value, dict):
                continue
            contacts: dict[str, str] = {}
            for c in value.get("contacts") or []:
                if isinstance(c, dict) and c.get("wa_id"):
                    profile = c.get("profile") if isinstance(c.get("profile"), dict) else {}
                    contacts[str(c["wa_id"])] = str(profile.get("name") or c["wa_id"])[:160]
            for msg in value.get("messages") or []:
                if not isinstance(msg, dict) or msg.get("type") != "text":
                    continue
                phone = str(msg.get("from") or "").strip()
                text = str((msg.get("text") or {}).get("body") or "").strip()
                msg_id = str(msg.get("id") or "").strip()
                if not phone or not text or not msg_id:
                    continue
                out.append(
                    {
                        "external_message_id": msg_id[:160],
                        "phone": phone[:30],
                        "contact_name": contacts.get(phone, phone)[:160],
                        "text": text[:12000],
                    }
                )
    return out
