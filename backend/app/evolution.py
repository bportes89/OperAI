import httpx
from app.core.config import get_settings


def _local_mode() -> bool:
    return not get_settings().evolution_api_key.strip()


def _headers() -> dict[str, str]:
    return {
        "apikey": get_settings().evolution_api_key,
        "Content-Type": "application/json",
    }


async def create_instance(name: str) -> dict:
    if _local_mode():
        return {
            "instance": {"instanceName": name, "status": "created"},
            "qrcode": {"base64": None, "code": f"local-qr-{name}"},
            "mode": "local",
        }
    body = {
        "instanceName": name,
        "qrcode": True,
        "integration": "WHATSAPP-BAILEYS",
    }
    async with httpx.AsyncClient(timeout=45.0) as client:
        response = await client.post(
            f"{get_settings().evolution_api_url.rstrip('/')}/instance/create",
            json=body,
            headers=_headers(),
        )
        response.raise_for_status()
        return response.json()


async def connection_state(name: str) -> dict:
    if _local_mode():
        return {"instance": name, "state": "open", "mode": "local"}
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(
            f"{get_settings().evolution_api_url.rstrip('/')}/instance/connectionState/{name}",
            headers=_headers(),
        )
        response.raise_for_status()
        return response.json()


async def get_qrcode(name: str) -> dict:
    if _local_mode():
        return {"qrcode": {"base64": None, "code": f"local-qr-{name}"}, "mode": "local"}
    async with httpx.AsyncClient(timeout=45.0) as client:
        response = await client.get(
            f"{get_settings().evolution_api_url.rstrip('/')}/instance/connect/{name}",
            headers=_headers(),
        )
        response.raise_for_status()
        return response.json()


async def send_text(instance: str, phone: str, text: str) -> dict:
    if _local_mode():
        return {"status": "sent", "instance": instance, "to": phone, "mode": "local"}
    number = "".join(ch for ch in phone if ch.isdigit())
    body = {"number": number, "text": text}
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{get_settings().evolution_api_url.rstrip('/')}/message/sendText/{instance}",
            json=body,
            headers=_headers(),
        )
        response.raise_for_status()
        return response.json()
