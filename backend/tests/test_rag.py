from app.rag import cosine,embed_text,retrieve

def test_embedding_is_deterministic_and_normalized():
    first=embed_text("política de cobrança");second=embed_text("política de cobrança")
    assert first==second
    assert 0.99<=cosine(first,first)<=1.01

def test_related_text_is_closer_than_unrelated_text():
    query=embed_text("cobrança de cliente em atraso")
    assert cosine(query,embed_text("cliente com cobrança atrasada"))>cosine(query,embed_text("agenda de férias do RH"))
