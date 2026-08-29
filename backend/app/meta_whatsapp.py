"""WhatsApp Cloud API (Meta) — envio e parse de webhook."""
from __future__ import annotations

import httpx

GRAPH_BASE = "https://graph.facebook.com/v21.0"


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
