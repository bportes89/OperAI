import uuid
import httpx
from app.core.config import get_settings


def _local_mode() -> bool:
    return not get_settings().asaas_api_key.strip()


def _headers() -> dict[str, str]:
    return {
        "access_token": get_settings().asaas_api_key,
        "Content-Type": "application/json",
    }


async def create_customer(name: str, email: str, cpf_cnpj: str | None = None) -> dict:
    if _local_mode():
        return {"id": f"local_cus_{uuid.uuid4().hex[:12]}", "name": name, "email": email, "mode": "local"}
    body: dict = {"name": name, "email": email}
    if cpf_cnpj:
        body["cpfCnpj"] = cpf_cnpj
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{get_settings().asaas_api_url.rstrip('/')}/customers",
            json=body,
            headers=_headers(),
        )
        response.raise_for_status()
        return response.json()


async def create_subscription(
    customer_id: str,
    value_reais: float,
    description: str,
    external_reference: str,
    cycle: str = "MONTHLY",
) -> dict:
    if _local_mode():
        sub_id = f"local_sub_{uuid.uuid4().hex[:12]}"
        return {
            "id": sub_id,
            "customer": customer_id,
            "value": value_reais,
            "cycle": cycle,
            "description": description,
            "externalReference": external_reference,
            "invoiceUrl": f"{get_settings().frontend_url.rstrip('/')}/billing/local/{sub_id}",
            "mode": "local",
        }
    body = {
        "customer": customer_id,
        "billingType": "UNDEFINED",
        "value": value_reais,
        "cycle": cycle,
        "description": description,
        "externalReference": external_reference,
    }
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{get_settings().asaas_api_url.rstrip('/')}/subscriptions",
            json=body,
            headers=_headers(),
        )
        response.raise_for_status()
        return response.json()


async def get_subscription(subscription_id: str) -> dict:
    if _local_mode() or subscription_id.startswith("local_"):
        return {"id": subscription_id, "status": "ACTIVE", "mode": "local"}
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(
            f"{get_settings().asaas_api_url.rstrip('/')}/subscriptions/{subscription_id}",
            headers=_headers(),
        )
        response.raise_for_status()
        return response.json()
