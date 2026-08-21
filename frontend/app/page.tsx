import Link from "next/link";

const PLANS = [
  {
    slug: "start",
    name: "Start",
    price: "197",
    featured: false,
    items: [
      "1 agente de atendimento",
      "Base de conhecimento",
      "WhatsApp + BYOK",
      "Até 2 usuários",
    ],
  },
  {
    slug: "pro",
    name: "Pro",
    price: "397",
    featured: true,
    items: [
      "4 agentes (vendas, WhatsApp, cobrança, marketing)",
      "CRM + cobrança + campanhas",
      "Até 5 usuários",
      "BYOK incluso",
    ],
  },
  {
    slug: "business",
    name: "Business",
    price: "797",
    featured: false,
    items: [
      "Até 10 agentes",
      "Equipe maior (20 usuários)",
      "Base ampliada",
      "Prioridade no suporte",
    ],
  },
];

export default function LandingPage() {
  return (
    <main className="landing">
      <nav className="landing-nav">
        <div className="landing-brand">
          <div className="logo">O</div>
          OperAI
        </div>
        <div className="landing-nav-actions">
          <Link href="/login">Entrar</Link>
          <Link className="primary" href="/register">
            Começar trial
          </Link>
        </div>
      </nav>

      <section className="landing-hero">
        <div className="hero-copy">
          <span className="eyebrow">OperAI</span>
          <h1>Equipe de IA para PME</h1>
          <p>
            WhatsApp, cobrança e vendas com o conhecimento da sua empresa —
            agentes que atendem, cobram e vendem no contexto do seu negócio.
          </p>
          <div className="hero-ctas">
            <Link className="primary" href="/register">
              Criar conta grátis
            </Link>
            <Link className="secondary" href="/login">
              Já tenho conta
            </Link>
          </div>
        </div>
      </section>

      <section className="landing-section" id="precos">
        <h2>Planos claros, mensalidade previsível</h2>
        <p>
          Você traz a chave do LLM (BYOK). Nós entregamos a plataforma, o
          WhatsApp e os fluxos operacionais — sem surpresa na fatura de tokens.
        </p>
        <div className="pricing-grid">
          {PLANS.map((plan) => (
            <article
              key={plan.slug}
              className={`price-card${plan.featured ? " featured" : ""}`}
            >
              <h3>{plan.name}</h3>
              <div className="amount">
                R${plan.price}
                <small>/mês</small>
              </div>
              <ul>
                {plan.items.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
              <Link className="primary" href="/register">
                Assinar {plan.name}
              </Link>
            </article>
          ))}
        </div>
        <p className="pricing-note">
          BYOK: configure OpenAI, Groq ou OpenRouter na sua conta. O custo de
          tokens fica com você.
        </p>
      </section>

      <footer className="landing-footer">
        <span>© {new Date().getFullYear()} OperAI</span>
        <span>Feito para operações de PME no Brasil</span>
      </footer>
    </main>
  );
}
