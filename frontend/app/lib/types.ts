export type Opportunity = {
  id: string;
  company: string;
  contact: string;
  stage: string;
  value_cents: number;
};

export type Agent = {
  id: string;
  name: string;
  agent_type: string;
  status: string;
  model: string;
  instructions: string;
};

export type KnowledgeDocument = {
  id: string;
  title: string;
  source_type: string;
  status: string;
  chunk_count: number;
};

export type SearchHit = {
  chunk_id: string;
  document: string;
  content: string;
  position: number;
};

export type ChatResult = {
  agent: string;
  conversation_id: string;
  answer: string;
  sources: { document: string; content: string; score: number }[];
  mode?: string;
};

export type Channel = {
  id: string;
  name: string;
  kind: string;
  external_key: string;
  active: boolean;
  provider?: string;
  instance_name?: string | null;
};

export type InboxThread = {
  id: string;
  contact_name: string;
  phone: string;
  channel: string;
  status: string;
  unread_count: number;
  last_message_at?: string;
};

export type InboxMessage = {
  id: string;
  direction: string;
  content: string;
  status: string;
  created_at: string;
};

export type Receivable = {
  id: string;
  customer_name: string;
  description: string;
  amount_cents: number;
  due_date: string;
  status: string;
  paid_at: string | null;
};

export type FinanceSummary = {
  pending_cents: number;
  overdue_cents: number;
  paid_cents: number;
  total_count: number;
};

export type Analytics = {
  crm: { opportunities: number; pipeline_cents: number; won: number };
  finance: { pending_cents: number; overdue_cents: number; paid_cents: number };
  operations: {
    active_agents: number;
    open_threads: number;
    unread_messages: number;
    campaigns: number;
  };
  marketing?: {
    interests_7d: number;
    leads_7d: number;
    opportunities_7d: number;
  };
};

export type MarketingLead = {
  id: string;
  source_title: string;
  source_channel: string;
  contact_name: string;
  phone: string | null;
  email: string | null;
  note: string | null;
  status: string;
  campaign_id: string | null;
  contact_id: string | null;
  opportunity_id: string | null;
  consent_lgpd?: boolean;
  consent_at?: string | null;
  is_crisis?: boolean;
  created_at: string | null;
};

export type MarketingConversion = {
  window_days: number;
  interests: number;
  leads_with_contact: number;
  opportunities: number;
  crisis?: number;
  by_channel: { social: number; email: number; whatsapp: number };
};

export type MarketingGovernance = {
  id: string;
  monthly_ad_ceiling_cents: number;
  spent_cents: number;
  remaining_cents: number;
  crisis_escalation: boolean;
  lgpd_note: string | null;
  account_checklist: {
    google_business?: boolean;
    meta_business?: boolean;
    whatsapp_business?: boolean;
  };
  updated_at: string | null;
};

export type MarketingSpendRequest = {
  id: string;
  channel: string;
  description: string;
  amount_cents: number;
  status: string;
  created_at: string | null;
  reviewed_at: string | null;
};

export type Activity = {
  id: string;
  action: string;
  resource: string;
  detail: string | null;
  created_at: string;
};

export type TeamMember = {
  membership_id: string;
  user_id: string;
  name: string;
  email: string;
  role: string;
  active: boolean;
};

export type Campaign = {
  id: string;
  name: string;
  channel: string;
  audience: string;
  content: string;
  status: string;
  scheduled_at: string | null;
  sent_count: number;
  delivered_count: number;
  response_count: number;
};

export type MarketingPost = {
  title: string;
  channel: string;
  audience: string;
  content: string;
};

export type MarketingPlaybook = {
  id: string;
  package: string;
  step: string;
  diagnosis: Record<string, string>;
  discovery: Record<string, string>;
  diagnosis_summary: string | null;
  action_plan: string | null;
  posts: MarketingPost[];
  agent_id: string | null;
  updated_at: string | null;
};

export type OnboardingState = {
  step: string;
  completed_at: string | null;
  checklist: {
    account?: boolean;
    llm?: boolean;
    faq?: boolean;
    whatsapp?: boolean;
    [key: string]: boolean | undefined;
  };
};

export type LlmSettings = {
  provider: string | null;
  model_name: string | null;
  configured: boolean;
  has_api_key?: boolean;
};

export type BillingPlan = {
  slug: string;
  name: string;
  price_cents: number;
  currency?: string;
  limits?: Record<string, number>;
  features?: string[] | Record<string, unknown>;
  active?: boolean;
};

export type Subscription = {
  status: string;
  plan_slug?: string;
  plan?: BillingPlan | null;
  trial_ends_at?: string | null;
  access: boolean;
  reason?: string | null;
  asaas_subscription_id?: string | null;
  mode?: string;
};

export type CheckoutResult = {
  checkout_url?: string | null;
  payment_url?: string | null;
  subscription_id?: string;
  mode?: string;
};

export const AGENT_LABELS: Record<string, string> = {
  commercial: "Comercial",
  whatsapp: "Atendimento",
  finance: "Cobrança",
  marketing: "Marketing",
};

export const CAMPAIGN_TRANSITIONS: Record<string, string[]> = {
  draft: ["approved", "cancelled"],
  approved: ["scheduled", "running", "cancelled"],
  scheduled: ["running", "cancelled"],
  running: ["completed", "cancelled"],
  completed: [],
  cancelled: [],
};

export const CAMPAIGN_STATUS_LABELS: Record<string, string> = {
  approved: "Aprovar",
  scheduled: "Agendar",
  running: "Iniciar",
  completed: "Concluir",
  cancelled: "Cancelar",
};
