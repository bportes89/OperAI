import httpx

PROVIDERS = {
    "openai": "https://api.openai.com/v1",
    "groq": "https://api.groq.com/openai/v1",
    "openrouter": "https://openrouter.ai/api/v1",
}

AGENT_SYSTEM_PROMPTS = {
    "commercial": (
        "Você é o agente comercial da OperAI. Seja profissional, objetivo e consultivo. "
        "Qualifique leads, esclareça dúvidas sobre oferta e conduza o próximo passo sem pressão."
    ),
    "whatsapp": (
        "Você é o agente de atendimento WhatsApp da OperAI. Responda em português brasileiro, "
        "de forma curta, clara e cordial. Use o contexto da empresa e peça esclarecimentos quando necessário."
    ),
    "finance": (
        "Você é o agente financeiro da OperAI. Ajude com cobranças, prazos e status de recebíveis "
        "com linguagem profissional, precisa e sem inventar valores."
    ),
    "marketing": (
        "Você é o agente de marketing da OperAI. Sugira campanhas, mensagens e posicionamento "
        "com tom profissional, criativo e alinhado à marca do cliente."
    ),
}


async def chat(
    provider: str,
    api_key: str,
    model: str,
    system: str,
    user: str,
    temperature: float = 0.3,
    history: list[dict[str, str]] | None = None,
) -> str:
    base = PROVIDERS.get(provider.lower())
    if not base:
        raise ValueError(f"Unsupported LLM provider: {provider}")
    if not api_key.strip():
        raise ValueError("LLM API key is required")
    messages: list[dict[str, str]] = [{"role": "system", "content": system}]
    if history:
        messages.extend(history[-10:])
    messages.append({"role": "user", "content": user})
    payload = {
        "model": model,
        "temperature": temperature,
        "messages": messages,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    if provider.lower() == "openrouter":
        headers["HTTP-Referer"] = "https://operai.app"
        headers["X-Title"] = "OperAI"
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(f"{base}/chat/completions", json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
    except httpx.HTTPStatusError as exc:
        detail = exc.response.text[:400]
        raise RuntimeError(f"LLM provider error ({exc.response.status_code}): {detail}") from exc
    except httpx.HTTPError as exc:
        raise RuntimeError(f"LLM request failed: {exc}") from exc
    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError("LLM response missing message content") from exc
    if not isinstance(content, str) or not content.strip():
        raise RuntimeError("LLM returned empty content")
    return content.strip()
