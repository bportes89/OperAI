"""Gera one-pager comercial OperAI (PDF)."""
from pathlib import Path

from fpdf import FPDF

OUT = Path(__file__).resolve().parent / "OperAI-comercial.pdf"
FONT = Path(r"C:\Windows\Fonts\arial.ttf")
FONT_B = Path(r"C:\Windows\Fonts\arialbd.ttf")


class Doc(FPDF):
    def footer(self) -> None:
        self.set_y(-14)
        self.set_font("Body", size=8)
        self.set_text_color(107, 120, 116)
        self.cell(0, 8, "OperAI — Equipe de IA para PME  |  oper-ai-brown.vercel.app", align="C")


def h(pdf: Doc, text: str, size: int = 14) -> None:
    pdf.set_font("BodyBold", size=size)
    pdf.set_text_color(11, 28, 36)
    pdf.ln(3)
    pdf.multi_cell(0, 7, text)
    pdf.ln(1)


def p(pdf: Doc, text: str, size: int = 10) -> None:
    pdf.set_font("Body", size=size)
    pdf.set_text_color(66, 83, 79)
    pdf.multi_cell(0, 5.2, text)
    pdf.ln(1.5)


def bullet(pdf: Doc, text: str) -> None:
    pdf.set_font("Body", size=10)
    pdf.set_text_color(66, 83, 79)
    pdf.set_x(pdf.l_margin + 2)
    pdf.multi_cell(0, 5.2, f"•  {text}")


def main() -> None:
    pdf = Doc(format="A4")
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.add_font("Body", fname=str(FONT))
    pdf.add_font("BodyBold", fname=str(FONT_B))
    pdf.add_page()
    pdf.set_margins(18, 16, 18)

    # Header bar
    pdf.set_fill_color(15, 107, 99)
    pdf.rect(0, 0, 210, 28, style="F")
    pdf.set_xy(18, 8)
    pdf.set_font("BodyBold", size=18)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(0, 8, "OperAI", ln=True)
    pdf.set_x(18)
    pdf.set_font("Body", size=10)
    pdf.cell(0, 6, "Equipe de IA para PME  ·  WhatsApp, cobrança e vendas com o conhecimento da empresa")

    pdf.set_y(34)

    h(pdf, "Proposta em uma frase", 13)
    p(
        pdf,
        "A OperAI coloca agentes de IA na operação da sua PME: atendimento, cobrança e vendas "
        "usando o FAQ e as políticas da sua empresa. Você traz a chave do modelo de IA (BYOK); "
        "nós entregamos a plataforma — mensalidade previsível, sem surpresa de tokens embutidos.",
    )

    h(pdf, "Por que a OperAI", 13)
    for t in [
        "BYOK: você controla o provedor e o custo de tokens (OpenAI, Groq ou OpenRouter).",
        "Agentes no contexto do seu negócio — respostas baseadas na sua base de conhecimento.",
        "Operação unificada: WhatsApp, CRM, cobrança, marketing e equipe em um só lugar.",
        "Multi-empresa desde o início: cada cliente com dados isolados e papéis de acesso.",
        "Entrada rápida: trial de 14 dias, onboarding guiado (conta → LLM → FAQ → WhatsApp).",
    ]:
        bullet(pdf, t)

    pdf.ln(2)
    h(pdf, "Planos", 13)
    pdf.set_font("BodyBold", size=10)
    pdf.set_text_color(11, 28, 36)
    pdf.cell(58, 7, "Start — R$ 197/mês", border=0)
    pdf.cell(58, 7, "Pro — R$ 397/mês", border=0)
    pdf.cell(58, 7, "Business — R$ 797/mês", border=0, ln=True)
    pdf.set_font("Body", size=9)
    pdf.set_text_color(66, 83, 79)
    pdf.cell(58, 5, "Entrada · 1 agente")
    pdf.cell(58, 5, "4 agentes + CRM + cobrança")
    pdf.cell(58, 5, "Escala · mais agentes/usuários", ln=True)
    pdf.ln(2)
    p(pdf, "Todos os planos incluem BYOK. Trial gratuito de 14 dias no Start.", 9)

    h(pdf, "Como o cliente usa (em 5 passos)", 13)
    for i, t in enumerate(
        [
            "Criar empresa (e-mail, senha e identificador).",
            "Colar a chave LLM em Configurações.",
            "Subir FAQ / políticas em Conhecimento.",
            "Ativar agentes (Atendimento, Comercial, Cobrança, Marketing).",
            "Operar WhatsApp, CRM, Cobrança e Marketing no dia a dia; assinar o plano quando o trial acabar.",
        ],
        start=1,
    ):
        bullet(pdf, f"{i}. {t}")

    pdf.ln(2)
    h(pdf, "O que já entrega / o que depende de setup", 13)
    p(
        pdf,
        "Pronto para piloto: cadastro, trial, agentes + conhecimento, CRM, cobrança interna, "
        "marketing, equipe, dashboard e billing.",
        9,
    )
    p(
        pdf,
        "WhatsApp real 24/7: requer Evolution API em infra do cliente (ou parceiro). "
        "Asaas em produção: chave live + webhook.",
        9,
    )

    pdf.ln(3)
    pdf.set_fill_color(243, 239, 230)
    pdf.set_x(18)
    y = pdf.get_y()
    pdf.rect(18, y, 174, 22, style="F")
    pdf.set_xy(22, y + 4)
    pdf.set_font("BodyBold", size=11)
    pdf.set_text_color(11, 28, 36)
    pdf.cell(0, 6, "Comece agora", ln=True)
    pdf.set_x(22)
    pdf.set_font("Body", size=10)
    pdf.set_text_color(15, 107, 99)
    pdf.cell(0, 6, "https://oper-ai-brown.vercel.app  ·  Criar conta / Começar trial")

    pdf.output(OUT)
    print(OUT)


if __name__ == "__main__":
    main()
