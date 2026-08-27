import Link from "next/link";
import { HeroFloatLayer, HeroPanelTilt, LandingFX } from "./landing-fx";

const STEPS = [
  {
    n: "01",
    title: "Cadastre a empresa",
    text: "Crie a conta, defina o identificador e inicie o trial de 14 dias.",
  },
  {
    n: "02",
    title: "Configure a inteligência",
    text: "Cole a chave LLM (BYOK) e publique FAQ, políticas e scripts na base de conhecimento.",
  },
  {
    n: "03",
    title: "Ative a operação",
    text: "Ligue os agentes, conecte o WhatsApp e opere CRM, cobrança e marketing no mesmo ambiente.",
  },
  {
    n: "→",
    title: "Resultado",
    text: "Atendimento, vendas e cobrança com contexto da empresa — e custo de IA sob seu controle.",
  },
];

const FEATURES = [
  {
    title: "Agentes especializados",
    text: "Comercial, Atendimento, Cobrança e Marketing — prontos para o processo da sua PME.",
  },
  {
    title: "Base de conhecimento",
    text: "FAQ e documentos da empresa alimentam respostas com contexto real do negócio.",
  },
  {
    title: "WhatsApp e inbox",
    text: "Conversas centralizadas, com agentes preparados para responder no tom da operação.",
  },
  {
    title: "CRM e cobrança",
    text: "Oportunidades, títulos e baixas no mesmo fluxo operacional.",
  },
  {
    title: "Marketing e equipe",
    text: "Campanhas organizadas e papéis de acesso para times multiempresa.",
  },
  {
    title: "Billing e onboarding",
    text: "Trial, planos e checklist de setup para colocar a operação no ar com clareza.",
  },
];

const DIFFS = [
  {
    label: "Custo de IA",
    ours: "BYOK — tokens sob controle da empresa",
    theirs: "Pacotes opacos ou markup sobre consumo",
  },
  {
    label: "Contexto",
    ours: "Respostas ancoradas no seu FAQ e políticas",
    theirs: "Chat genérico, sem memória do negócio",
  },
  {
    label: "Escopo",
    ours: "WhatsApp, CRM, cobrança e marketing juntos",
    theirs: "Ferramentas isoladas e integrações frágeis",
  },
  {
    label: "Operação",
    ours: "Multi-empresa, papéis e trial estruturado",
    theirs: "Setup longo e dependência de consultoria",
  },
];

const USE_CASES = [
  {
    title: "Atendimento comercial",
    text: "Responde prazo, região e política com base no conhecimento publicado pela empresa.",
  },
  {
    title: "Cobrança recorrente",
    text: "Organiza títulos, acompanha atraso e padroniza a comunicação de follow-up.",
  },
  {
    title: "Time enxuto de PME",
    text: "Poucas pessoas operam vendas, WhatsApp e financeiro com apoio dos agentes.",
  },
];

const INTEGRATIONS = [
  { name: "OpenAI", detail: "BYOK" },
  { name: "Groq", detail: "BYOK" },
  { name: "OpenRouter", detail: "BYOK" },
  { name: "WhatsApp", detail: "Evolution / canais" },
  { name: "Asaas", detail: "Assinatura" },
  { name: "Postgres", detail: "Neon / produção" },
];

const RESULTS = [
  {
    quote:
      "Conseguimos padronizar o atendimento sem perder o tom da empresa — o FAQ virou a base do WhatsApp.",
    who: "Operação comercial · PME de serviços",
  },
  {
    quote:
      "O BYOK foi decisivo: previsibilidade de custo e liberdade para escolher o modelo.",
    who: "Fundador · software house",
  },
  {
    quote:
      "CRM, cobrança e agentes no mesmo lugar reduziram o vai-e-vem entre ferramentas.",
    who: "Gestão · time comercial enxuto",
  },
];

const SECURITY = [
  {
    title: "Isolamento multi-empresa",
    text: "Cada organização opera com slug próprio e dados separados por tenant.",
  },
  {
    title: "Chaves protegidas",
    text: "Credenciais LLM criptografadas e acesso sensível restrito a papéis elevados.",
  },
  {
    title: "Controle de acesso",
    text: "Papéis owner, admin, manager, operator e viewer para governança do time.",
  },
];

const FAQ = [
  {
    q: "O que é BYOK?",
    a: "Bring Your Own Key: você usa a própria chave de OpenAI, Groq ou OpenRouter. A mensalidade da OperAI cobre a plataforma; o custo de tokens fica com você.",
  },
  {
    q: "Preciso de cartão para o trial?",
    a: "O trial de 14 dias começa no cadastro da empresa. Depois você escolhe Start, Pro ou Business conforme a operação.",
  },
  {
    q: "O WhatsApp funciona de imediato?",
    a: "A plataforma já traz inbox e fluxo de agentes. WhatsApp real 24/7 depende da Evolution (ou canal equivalente) configurada no seu ambiente.",
  },
  {
    q: "Posso ter mais de um usuário?",
    a: "Sim. Convide a equipe e defina papéis. Os limites variam por plano (Start, Pro ou Business).",
  },
  {
    q: "Os agentes inventam respostas?",
    a: "Eles priorizam a base de conhecimento da empresa. Sem chave LLM, a resposta fica limitada ao conteúdo local publicado.",
  },
];

const PLANS = [
  {
    slug: "start",
    name: "Start",
    price: "197",
    featured: false,
    summary: "Entrada operacional com atendimento e base de conhecimento.",
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
    summary: "Operação completa: vendas, WhatsApp, cobrança e marketing.",
    items: [
      "4 agentes especializados",
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
    summary: "Escala para times maiores e mais agentes em paralelo.",
    items: [
      "Até 10 agentes",
      "Até 20 usuários",
      "Base ampliada",
      "Prioridade no suporte",
    ],
  },
];

export default function LandingPage() {
  return (
    <main className="lp">
      <LandingFX />
      <header className="lp-nav">
        <Link href="/" className="lp-brand" aria-label="OperAI">
          <img
            src="/operai-logo.png"
            alt="OperAI"
            width={200}
            height={63}
            className="lp-logo"
          />
        </Link>
        <nav className="lp-nav-links">
          <a href="#problema">Problema</a>
          <a href="#solucao">Solução</a>
          <a href="#como-funciona">Como funciona</a>
          <a href="#planos">Planos</a>
          <Link href="/login">Entrar</Link>
          <Link className="lp-btn lp-btn-primary" href="/register">
            Começar trial
          </Link>
        </nav>
      </header>

      <section className="lp-hero">
        <div className="lp-hero-plane" aria-hidden="true" />
        <HeroFloatLayer />
        <div className="lp-hero-inner">
          <p className="lp-brand-word">OperAI</p>
          <h1>
            Inteligência operacional para empresas que precisam de escala com
            controle.
          </h1>
          <p className="lp-hero-lead">
            Plataforma de agentes de IA para WhatsApp, cobrança e vendas — com o
            conhecimento da sua empresa e a chave LLM sob sua gestão.
          </p>
          <div className="lp-hero-actions">
            <Link className="lp-btn lp-btn-primary" href="/register">
              Iniciar trial de 14 dias
            </Link>
            <a className="lp-btn lp-btn-ghost" href="#problema">
              Ver o problema
            </a>
          </div>
        </div>
        <div className="lp-hero-visual">
          <HeroPanelTilt>
            <div className="lp-hero-panel">
              <div className="lp-panel-bar">
                <span>Operação</span>
                <span>Ao vivo</span>
              </div>
              <div className="lp-panel-body">
                <div className="lp-panel-line">
                  <strong>Atendimento</strong>
                  <em>Resposta com base na política comercial</em>
                </div>
                <div className="lp-panel-line">
                  <strong>Cobrança</strong>
                  <em>Follow-up de títulos em atraso</em>
                </div>
                <div className="lp-panel-line">
                  <strong>Comercial</strong>
                  <em>Qualificação com contexto do CRM</em>
                </div>
              </div>
            </div>
          </HeroPanelTilt>
        </div>
      </section>

      <section className="lp-section lp-reveal" id="problema">
        <div className="lp-kicker">O problema</div>
        <div className="lp-section-head">
          <h2>Ferramentas demais. Contexto de menos.</h2>
          <p>
            PME cresce com WhatsApp, planilha, CRM e cobrança em silos. A IA
            genérica não conhece a política da empresa — e o custo de tokens
            vira surpresa.
          </p>
        </div>
        <ul className="lp-problem-list">
          <li>Atendimento inconsistente entre canais e pessoas</li>
          <li>Conhecimento da empresa preso em documentos e cabeças</li>
          <li>Stack fragmentada: vender, atender e cobrar em lugares diferentes</li>
          <li>IA “pronta” sem controle de provedor, modelo e gasto</li>
        </ul>
      </section>

      <section className="lp-section lp-section-alt lp-reveal" id="solucao">
        <div className="lp-kicker">A solução</div>
        <div className="lp-section-head">
          <h2>Uma plataforma. Uma operação coerente.</h2>
          <p>
            A OperAI reúne agentes, base de conhecimento e fluxos de WhatsApp,
            CRM, cobrança e marketing — com BYOK para a empresa mandar na
            inteligência.
          </p>
        </div>
      </section>

      <section className="lp-section lp-reveal" id="como-funciona">
        <div className="lp-kicker">Como funciona</div>
        <div className="lp-section-head">
          <h2>Do cadastro ao resultado em quatro tempos.</h2>
          <p>Um caminho curto para colocar a operação no ar com clareza.</p>
        </div>
        <div className="lp-steps">
          {STEPS.map((step) => (
            <article key={step.n + step.title} className="lp-step">
              <span className="lp-step-n">{step.n}</span>
              <h3>{step.title}</h3>
              <p>{step.text}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="lp-section lp-section-alt lp-reveal" id="funcionalidades">
        <div className="lp-kicker">Principais funcionalidades</div>
        <div className="lp-section-head">
          <h2>O essencial para operar com agentes.</h2>
          <p>Módulos pensados para o dia a dia da PME — sem excesso de dashboard.</p>
        </div>
        <div className="lp-feature-grid">
          {FEATURES.map((item) => (
            <article key={item.title} className="lp-feature">
              <h3>{item.title}</h3>
              <p>{item.text}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="lp-section lp-reveal" id="diferenciais">
        <div className="lp-kicker">Diferenciais</div>
        <div className="lp-section-head">
          <h2>OperAI × soluções tradicionais</h2>
          <p>Comparação direta do que muda na operação e no custo.</p>
        </div>
        <div className="lp-compare">
          <div className="lp-compare-head">
            <span>Critério</span>
            <span>OperAI</span>
            <span>Soluções tradicionais</span>
          </div>
          {DIFFS.map((row) => (
            <div key={row.label} className="lp-compare-row">
              <strong>{row.label}</strong>
              <span>{row.ours}</span>
              <span className="muted">{row.theirs}</span>
            </div>
          ))}
        </div>
      </section>

      <section className="lp-section lp-section-alt lp-reveal" id="casos-de-uso">
        <div className="lp-kicker">Casos de uso</div>
        <div className="lp-section-head">
          <h2>Onde a plataforma gera tração primeiro.</h2>
          <p>Cenários típicos de PME que precisam de ritmo sem perder padrão.</p>
        </div>
        <div className="lp-usecases">
          {USE_CASES.map((item) => (
            <article key={item.title} className="lp-usecase">
              <h3>{item.title}</h3>
              <p>{item.text}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="lp-section lp-reveal" id="integracoes">
        <div className="lp-kicker">Integrações</div>
        <div className="lp-section-head">
          <h2>Encaixa na stack que você já escolhe.</h2>
          <p>Provedores de LLM, canais e billing — sem prender a empresa a um único vendor.</p>
        </div>
        <ul className="lp-integrations">
          {INTEGRATIONS.map((item) => (
            <li key={item.name}>
              <strong>{item.name}</strong>
              <span>{item.detail}</span>
            </li>
          ))}
        </ul>
      </section>

      <section className="lp-section lp-section-alt lp-reveal" id="resultados">
        <div className="lp-kicker">Resultados e depoimentos</div>
        <div className="lp-section-head">
          <h2>O que muda quando o contexto fica centralizado.</h2>
          <p>Relatos de operação — o tipo de ganho que a plataforma busca entregar.</p>
        </div>
        <div className="lp-quotes">
          {RESULTS.map((item) => (
            <blockquote key={item.who} className="lp-quote">
              <p>“{item.quote}”</p>
              <footer>{item.who}</footer>
            </blockquote>
          ))}
        </div>
      </section>

      <section className="lp-section lp-reveal" id="seguranca">
        <div className="lp-kicker">Segurança</div>
        <div className="lp-section-head">
          <h2>Controle de acesso e isolamento por empresa.</h2>
          <p>Governança para times que compartilham a plataforma sem misturar dados.</p>
        </div>
        <div className="lp-security">
          {SECURITY.map((item) => (
            <article key={item.title} className="lp-security-item">
              <h3>{item.title}</h3>
              <p>{item.text}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="lp-section lp-section-alt lp-reveal" id="faq">
        <div className="lp-kicker">FAQ</div>
        <div className="lp-section-head">
          <h2>Perguntas frequentes</h2>
          <p>Respostas diretas para quem está avaliando o trial.</p>
        </div>
        <div className="lp-faq">
          {FAQ.map((item) => (
            <details key={item.q} className="lp-faq-item">
              <summary>{item.q}</summary>
              <p>{item.a}</p>
            </details>
          ))}
        </div>
      </section>

      <section className="lp-section lp-reveal" id="planos">
        <div className="lp-kicker">Planos</div>
        <div className="lp-section-head">
          <h2>Planos para cada estágio da operação</h2>
          <p>Mensalidade clara. Trial incluso. Sem surpresa de tokens na fatura da OperAI.</p>
        </div>
        <div className="lp-plans">
          {PLANS.map((plan) => (
            <article
              key={plan.slug}
              className={`lp-plan${plan.featured ? " featured" : ""}`}
            >
              <header>
                <h3>{plan.name}</h3>
                <p>{plan.summary}</p>
              </header>
              <div className="lp-plan-price">
                <span>R$</span>
                {plan.price}
                <small>/mês</small>
              </div>
              <ul>
                {plan.items.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
              <Link className="lp-btn lp-btn-primary" href="/register">
                Assinar {plan.name}
              </Link>
            </article>
          ))}
        </div>
      </section>

      <section className="lp-cta-final">
        <h2>Comece o trial e monte sua equipe de IA.</h2>
        <p>14 dias para configurar BYOK, publicar o conhecimento e ativar os agentes.</p>
        <Link className="lp-btn lp-btn-primary" href="/register">
          Criar conta
        </Link>
      </section>

      <footer className="lp-footer">
        <img
          src="/operai-logo.png"
          alt="OperAI"
          width={140}
          height={44}
          className="lp-logo-sm"
        />
        <div className="lp-footer-meta">
          <span>© {new Date().getFullYear()} OperAI</span>
          <span>Plataforma institucional de agentes de IA para PME</span>
        </div>
        <div className="lp-footer-links">
          <Link href="/login">Entrar</Link>
          <Link href="/register">Criar conta</Link>
        </div>
      </footer>
    </main>
  );
}
