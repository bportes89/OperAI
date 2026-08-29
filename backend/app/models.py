import enum,uuid
from datetime import date,datetime
from sqlalchemy import JSON,Boolean,Date,DateTime,Enum,ForeignKey,Index,Integer,String,Text,UniqueConstraint,func
from sqlalchemy.orm import DeclarativeBase,Mapped,mapped_column

class Base(DeclarativeBase):pass
class Role(str,enum.Enum):OWNER="owner";ADMIN="admin";MANAGER="manager";OPERATOR="operator";VIEWER="viewer"
class Organization(Base):
    __tablename__="organizations"
    id:Mapped[uuid.UUID]=mapped_column(primary_key=True,default=uuid.uuid4);name:Mapped[str]=mapped_column(String(120));slug:Mapped[str]=mapped_column(String(80),unique=True,index=True);active:Mapped[bool]=mapped_column(Boolean,default=True);created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),server_default=func.now())
class User(Base):
    __tablename__="users"
    id:Mapped[uuid.UUID]=mapped_column(primary_key=True,default=uuid.uuid4);email:Mapped[str]=mapped_column(String(255),unique=True,index=True);name:Mapped[str]=mapped_column(String(120));password_hash:Mapped[str]=mapped_column(Text);active:Mapped[bool]=mapped_column(Boolean,default=True)
class Membership(Base):
    __tablename__="memberships";__table_args__=(UniqueConstraint("organization_id","user_id"),)
    id:Mapped[uuid.UUID]=mapped_column(primary_key=True,default=uuid.uuid4);organization_id:Mapped[uuid.UUID]=mapped_column(ForeignKey("organizations.id",ondelete="CASCADE"),index=True);user_id:Mapped[uuid.UUID]=mapped_column(ForeignKey("users.id",ondelete="CASCADE"),index=True);role:Mapped[Role]=mapped_column(Enum(Role),default=Role.OPERATOR);active:Mapped[bool]=mapped_column(Boolean,default=True)
class RefreshSession(Base):
    __tablename__="refresh_sessions"
    id:Mapped[uuid.UUID]=mapped_column(primary_key=True,default=uuid.uuid4);user_id:Mapped[uuid.UUID]=mapped_column(ForeignKey("users.id",ondelete="CASCADE"),index=True);organization_id:Mapped[uuid.UUID]=mapped_column(ForeignKey("organizations.id",ondelete="CASCADE"),index=True);token_hash:Mapped[str]=mapped_column(String(64),unique=True,index=True);expires_at:Mapped[datetime]=mapped_column(DateTime(timezone=True));revoked_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True))
class Opportunity(Base):
    __tablename__="opportunities";__table_args__=(Index("ix_opportunity_tenant_stage","organization_id","stage"),)
    id:Mapped[uuid.UUID]=mapped_column(primary_key=True,default=uuid.uuid4);organization_id:Mapped[uuid.UUID]=mapped_column(ForeignKey("organizations.id",ondelete="CASCADE"),index=True);company:Mapped[str]=mapped_column(String(160));contact:Mapped[str]=mapped_column(String(160));stage:Mapped[str]=mapped_column(String(40),default="new");value_cents:Mapped[int]=mapped_column(Integer,default=0);source_title:Mapped[str|None]=mapped_column(String(180));source_channel:Mapped[str|None]=mapped_column(String(40));source_campaign_id:Mapped[uuid.UUID|None]=mapped_column(ForeignKey("marketing_campaigns.id",ondelete="SET NULL"),index=True);created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),server_default=func.now())
class Agent(Base):
    __tablename__="agents";__table_args__=(UniqueConstraint("organization_id","name"),Index("ix_agent_tenant_status","organization_id","status"))
    id:Mapped[uuid.UUID]=mapped_column(primary_key=True,default=uuid.uuid4);organization_id:Mapped[uuid.UUID]=mapped_column(ForeignKey("organizations.id",ondelete="CASCADE"),index=True);name:Mapped[str]=mapped_column(String(120));agent_type:Mapped[str]=mapped_column(String(50));status:Mapped[str]=mapped_column(String(30),default="draft");model:Mapped[str]=mapped_column(String(80),default="gpt-5-mini");instructions:Mapped[str]=mapped_column(Text);created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),server_default=func.now());updated_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),server_default=func.now(),onupdate=func.now())
class KnowledgeDocument(Base):
    __tablename__="knowledge_documents";__table_args__=(Index("ix_knowledge_document_tenant_status","organization_id","status"),)
    id:Mapped[uuid.UUID]=mapped_column(primary_key=True,default=uuid.uuid4);organization_id:Mapped[uuid.UUID]=mapped_column(ForeignKey("organizations.id",ondelete="CASCADE"),index=True);title:Mapped[str]=mapped_column(String(180));source_type:Mapped[str]=mapped_column(String(30),default="text");content:Mapped[str]=mapped_column(Text);status:Mapped[str]=mapped_column(String(30),default="ready");chunk_count:Mapped[int]=mapped_column(Integer,default=0);created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),server_default=func.now())
class KnowledgeChunk(Base):
    __tablename__="knowledge_chunks";__table_args__=(UniqueConstraint("document_id","position"),Index("ix_knowledge_chunk_tenant_document","organization_id","document_id"))
    id:Mapped[uuid.UUID]=mapped_column(primary_key=True,default=uuid.uuid4);organization_id:Mapped[uuid.UUID]=mapped_column(ForeignKey("organizations.id",ondelete="CASCADE"),index=True);document_id:Mapped[uuid.UUID]=mapped_column(ForeignKey("knowledge_documents.id",ondelete="CASCADE"),index=True);position:Mapped[int]=mapped_column(Integer);content:Mapped[str]=mapped_column(Text);embedding:Mapped[list[float]|None]=mapped_column(JSON)
class Conversation(Base):
    __tablename__="conversations";__table_args__=(Index("ix_conversation_tenant_agent","organization_id","agent_id"),)
    id:Mapped[uuid.UUID]=mapped_column(primary_key=True,default=uuid.uuid4);organization_id:Mapped[uuid.UUID]=mapped_column(ForeignKey("organizations.id",ondelete="CASCADE"),index=True);agent_id:Mapped[uuid.UUID]=mapped_column(ForeignKey("agents.id",ondelete="CASCADE"),index=True);user_id:Mapped[uuid.UUID]=mapped_column(ForeignKey("users.id",ondelete="CASCADE"),index=True);title:Mapped[str]=mapped_column(String(180));created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),server_default=func.now());updated_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),server_default=func.now(),onupdate=func.now())
class ConversationMessage(Base):
    __tablename__="conversation_messages";__table_args__=(Index("ix_message_tenant_conversation","organization_id","conversation_id"),)
    id:Mapped[uuid.UUID]=mapped_column(primary_key=True,default=uuid.uuid4);organization_id:Mapped[uuid.UUID]=mapped_column(ForeignKey("organizations.id",ondelete="CASCADE"),index=True);conversation_id:Mapped[uuid.UUID]=mapped_column(ForeignKey("conversations.id",ondelete="CASCADE"),index=True);role:Mapped[str]=mapped_column(String(20));content:Mapped[str]=mapped_column(Text);sources:Mapped[list[dict]|None]=mapped_column(JSON);created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),server_default=func.now())
class Channel(Base):
    __tablename__="channels";__table_args__=(UniqueConstraint("organization_id","external_key"),)
    id:Mapped[uuid.UUID]=mapped_column(primary_key=True,default=uuid.uuid4);organization_id:Mapped[uuid.UUID]=mapped_column(ForeignKey("organizations.id",ondelete="CASCADE"),index=True);name:Mapped[str]=mapped_column(String(120));kind:Mapped[str]=mapped_column(String(30),default="whatsapp");external_key:Mapped[str]=mapped_column(String(120),unique=True,index=True);webhook_secret_hash:Mapped[str]=mapped_column(String(64));provider:Mapped[str]=mapped_column(String(40),default="webhook");instance_name:Mapped[str|None]=mapped_column(String(120));config:Mapped[dict|None]=mapped_column(JSON);active:Mapped[bool]=mapped_column(Boolean,default=True);created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),server_default=func.now())
class SaaSPlan(Base):
    __tablename__="saas_plans"
    id:Mapped[uuid.UUID]=mapped_column(primary_key=True,default=uuid.uuid4);slug:Mapped[str]=mapped_column(String(50),unique=True,index=True);name:Mapped[str]=mapped_column(String(80));monthly_price_cents:Mapped[int]=mapped_column(Integer);limits:Mapped[dict]=mapped_column(JSON);features:Mapped[list]=mapped_column(JSON);active:Mapped[bool]=mapped_column(Boolean,default=True);sort_order:Mapped[int]=mapped_column(Integer,default=0)
class OrganizationSubscription(Base):
    __tablename__="organization_subscriptions"
    id:Mapped[uuid.UUID]=mapped_column(primary_key=True,default=uuid.uuid4);organization_id:Mapped[uuid.UUID]=mapped_column(ForeignKey("organizations.id",ondelete="CASCADE"),unique=True,index=True);plan_id:Mapped[uuid.UUID]=mapped_column(ForeignKey("saas_plans.id",ondelete="RESTRICT"),index=True);status:Mapped[str]=mapped_column(String(30),default="trialing");current_period_start:Mapped[date]=mapped_column(Date);current_period_end:Mapped[date]=mapped_column(Date);cancel_at_period_end:Mapped[bool]=mapped_column(Boolean,default=False);asaas_customer_id:Mapped[str|None]=mapped_column(String(80));asaas_subscription_id:Mapped[str|None]=mapped_column(String(80));trial_ends_at:Mapped[date|None]=mapped_column(Date);created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),server_default=func.now())
class LlmCredential(Base):
    __tablename__="llm_credentials"
    id:Mapped[uuid.UUID]=mapped_column(primary_key=True,default=uuid.uuid4);organization_id:Mapped[uuid.UUID]=mapped_column(ForeignKey("organizations.id",ondelete="CASCADE"),unique=True,index=True);provider:Mapped[str]=mapped_column(String(40));model_name:Mapped[str]=mapped_column(String(120));api_key_encrypted:Mapped[str]=mapped_column(Text);created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),server_default=func.now());updated_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),server_default=func.now(),onupdate=func.now())
class OrganizationOnboarding(Base):
    __tablename__="organization_onboarding"
    organization_id:Mapped[uuid.UUID]=mapped_column(ForeignKey("organizations.id",ondelete="CASCADE"),primary_key=True);step:Mapped[str]=mapped_column(String(40),default="welcome");completed_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True));checklist:Mapped[dict]=mapped_column(JSON,default=dict)
class OrganizationBrandKit(Base):
    """Identidade verbal/visual da PME — usada por Marketing e agentes."""
    __tablename__="organization_brand_kits"
    organization_id:Mapped[uuid.UUID]=mapped_column(ForeignKey("organizations.id",ondelete="CASCADE"),primary_key=True)
    brand_name:Mapped[str]=mapped_column(String(120),default="")
    tagline:Mapped[str]=mapped_column(String(240),default="")
    voice_tone:Mapped[str]=mapped_column(Text,default="")
    primary_color:Mapped[str]=mapped_column(String(7),default="")
    secondary_color:Mapped[str]=mapped_column(String(7),default="")
    logo_url:Mapped[str]=mapped_column(String(1000),default="")
    avoid:Mapped[str]=mapped_column(Text,default="")
    notes:Mapped[str]=mapped_column(Text,default="")
    updated_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),server_default=func.now(),onupdate=func.now())
class Contact(Base):
    __tablename__="contacts";__table_args__=(UniqueConstraint("organization_id","phone"),)
    id:Mapped[uuid.UUID]=mapped_column(primary_key=True,default=uuid.uuid4);organization_id:Mapped[uuid.UUID]=mapped_column(ForeignKey("organizations.id",ondelete="CASCADE"),index=True);name:Mapped[str]=mapped_column(String(160));phone:Mapped[str]=mapped_column(String(30));created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),server_default=func.now())
class InboxThread(Base):
    __tablename__="inbox_threads";__table_args__=(UniqueConstraint("channel_id","contact_id"),Index("ix_inbox_thread_tenant_status","organization_id","status"))
    id:Mapped[uuid.UUID]=mapped_column(primary_key=True,default=uuid.uuid4);organization_id:Mapped[uuid.UUID]=mapped_column(ForeignKey("organizations.id",ondelete="CASCADE"),index=True);channel_id:Mapped[uuid.UUID]=mapped_column(ForeignKey("channels.id",ondelete="CASCADE"),index=True);contact_id:Mapped[uuid.UUID]=mapped_column(ForeignKey("contacts.id",ondelete="CASCADE"),index=True);status:Mapped[str]=mapped_column(String(30),default="open");unread_count:Mapped[int]=mapped_column(Integer,default=0);last_message_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),server_default=func.now())
class ChannelMessage(Base):
    __tablename__="channel_messages";__table_args__=(UniqueConstraint("channel_id","external_message_id"),Index("ix_channel_message_tenant_thread","organization_id","thread_id"))
    id:Mapped[uuid.UUID]=mapped_column(primary_key=True,default=uuid.uuid4);organization_id:Mapped[uuid.UUID]=mapped_column(ForeignKey("organizations.id",ondelete="CASCADE"),index=True);channel_id:Mapped[uuid.UUID]=mapped_column(ForeignKey("channels.id",ondelete="CASCADE"),index=True);thread_id:Mapped[uuid.UUID]=mapped_column(ForeignKey("inbox_threads.id",ondelete="CASCADE"),index=True);external_message_id:Mapped[str]=mapped_column(String(160));direction:Mapped[str]=mapped_column(String(20));content:Mapped[str]=mapped_column(Text);status:Mapped[str]=mapped_column(String(30));created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),server_default=func.now())
class Receivable(Base):
    __tablename__="receivables";__table_args__=(Index("ix_receivable_tenant_due","organization_id","due_date"),)
    id:Mapped[uuid.UUID]=mapped_column(primary_key=True,default=uuid.uuid4);organization_id:Mapped[uuid.UUID]=mapped_column(ForeignKey("organizations.id",ondelete="CASCADE"),index=True);contact_id:Mapped[uuid.UUID|None]=mapped_column(ForeignKey("contacts.id",ondelete="SET NULL"),index=True);created_by:Mapped[uuid.UUID]=mapped_column(ForeignKey("users.id",ondelete="CASCADE"),index=True);customer_name:Mapped[str]=mapped_column(String(180));description:Mapped[str]=mapped_column(String(240));amount_cents:Mapped[int]=mapped_column(Integer);due_date:Mapped[date]=mapped_column(Date);status:Mapped[str]=mapped_column(String(30),default="pending");paid_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True));created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),server_default=func.now())
class ReceivablePayment(Base):
    __tablename__="receivable_payments"
    id:Mapped[uuid.UUID]=mapped_column(primary_key=True,default=uuid.uuid4);organization_id:Mapped[uuid.UUID]=mapped_column(ForeignKey("organizations.id",ondelete="CASCADE"),index=True);receivable_id:Mapped[uuid.UUID]=mapped_column(ForeignKey("receivables.id",ondelete="CASCADE"),index=True);amount_cents:Mapped[int]=mapped_column(Integer);method:Mapped[str]=mapped_column(String(30));paid_at:Mapped[datetime]=mapped_column(DateTime(timezone=True));created_by:Mapped[uuid.UUID]=mapped_column(ForeignKey("users.id",ondelete="CASCADE"),index=True)
class AgentTask(Base):
    __tablename__="agent_tasks";__table_args__=(Index("ix_agent_task_tenant_status","organization_id","status"),UniqueConstraint("organization_id","idempotency_key"))
    id:Mapped[uuid.UUID]=mapped_column(primary_key=True,default=uuid.uuid4);organization_id:Mapped[uuid.UUID]=mapped_column(ForeignKey("organizations.id",ondelete="CASCADE"),index=True);agent_id:Mapped[uuid.UUID|None]=mapped_column(ForeignKey("agents.id",ondelete="SET NULL"),index=True);created_by:Mapped[uuid.UUID|None]=mapped_column(ForeignKey("users.id",ondelete="SET NULL"),index=True);idempotency_key:Mapped[str|None]=mapped_column(String(180));task_type:Mapped[str]=mapped_column(String(60));title:Mapped[str]=mapped_column(String(180));priority:Mapped[str]=mapped_column(String(20),default="normal");status:Mapped[str]=mapped_column(String(30),default="queued");input_data:Mapped[dict]=mapped_column(JSON);result_data:Mapped[dict|None]=mapped_column(JSON);error:Mapped[str|None]=mapped_column(Text);created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),server_default=func.now());started_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True));completed_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True))
class MarketingCampaign(Base):
    __tablename__="marketing_campaigns";__table_args__=(Index("ix_marketing_campaign_tenant_status","organization_id","status"),)
    id:Mapped[uuid.UUID]=mapped_column(primary_key=True,default=uuid.uuid4);organization_id:Mapped[uuid.UUID]=mapped_column(ForeignKey("organizations.id",ondelete="CASCADE"),index=True);created_by:Mapped[uuid.UUID]=mapped_column(ForeignKey("users.id",ondelete="CASCADE"),index=True);agent_id:Mapped[uuid.UUID|None]=mapped_column(ForeignKey("agents.id",ondelete="SET NULL"),index=True);name:Mapped[str]=mapped_column(String(180));channel:Mapped[str]=mapped_column(String(30));audience:Mapped[str]=mapped_column(String(240));content:Mapped[str]=mapped_column(Text);status:Mapped[str]=mapped_column(String(30),default="draft");scheduled_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True));sent_count:Mapped[int]=mapped_column(Integer,default=0);delivered_count:Mapped[int]=mapped_column(Integer,default=0);response_count:Mapped[int]=mapped_column(Integer,default=0);created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),server_default=func.now())
class MarketingPlaybook(Base):
    """Pacote Essencial: diagnóstico → descoberta → plano (Gestor + Redação + Mídias)."""
    __tablename__="marketing_playbooks";__table_args__=(UniqueConstraint("organization_id"),)
    id:Mapped[uuid.UUID]=mapped_column(primary_key=True,default=uuid.uuid4)
    organization_id:Mapped[uuid.UUID]=mapped_column(ForeignKey("organizations.id",ondelete="CASCADE"),index=True)
    created_by:Mapped[uuid.UUID]=mapped_column(ForeignKey("users.id",ondelete="CASCADE"),index=True)
    agent_id:Mapped[uuid.UUID|None]=mapped_column(ForeignKey("agents.id",ondelete="SET NULL"),index=True)
    package:Mapped[str]=mapped_column(String(40),default="essencial")
    step:Mapped[str]=mapped_column(String(40),default="diagnosis")
    diagnosis:Mapped[dict]=mapped_column(JSON,default=dict)
    discovery:Mapped[dict]=mapped_column(JSON,default=dict)
    diagnosis_summary:Mapped[str|None]=mapped_column(Text)
    action_plan:Mapped[str|None]=mapped_column(Text)
    posts:Mapped[list|None]=mapped_column(JSON)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),server_default=func.now())
    updated_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),server_default=func.now(),onupdate=func.now())
class MarketingLead(Base):
    """Sprint 2/3: interesse → CRM + LGPD consent + escalonamento de crise."""
    __tablename__="marketing_leads";__table_args__=(Index("ix_marketing_lead_tenant_created","organization_id","created_at"),)
    id:Mapped[uuid.UUID]=mapped_column(primary_key=True,default=uuid.uuid4)
    organization_id:Mapped[uuid.UUID]=mapped_column(ForeignKey("organizations.id",ondelete="CASCADE"),index=True)
    created_by:Mapped[uuid.UUID]=mapped_column(ForeignKey("users.id",ondelete="CASCADE"),index=True)
    campaign_id:Mapped[uuid.UUID|None]=mapped_column(ForeignKey("marketing_campaigns.id",ondelete="SET NULL"),index=True)
    contact_id:Mapped[uuid.UUID|None]=mapped_column(ForeignKey("contacts.id",ondelete="SET NULL"),index=True)
    opportunity_id:Mapped[uuid.UUID|None]=mapped_column(ForeignKey("opportunities.id",ondelete="SET NULL"),index=True)
    source_title:Mapped[str]=mapped_column(String(180))
    source_channel:Mapped[str]=mapped_column(String(30),default="social")
    contact_name:Mapped[str]=mapped_column(String(160))
    phone:Mapped[str|None]=mapped_column(String(30))
    email:Mapped[str|None]=mapped_column(String(255))
    note:Mapped[str|None]=mapped_column(Text)
    status:Mapped[str]=mapped_column(String(30),default="handed_off")
    consent_lgpd:Mapped[bool]=mapped_column(Boolean,default=False)
    consent_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True))
    is_crisis:Mapped[bool]=mapped_column(Boolean,default=False)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),server_default=func.now())
class MarketingGovernance(Base):
    """Sprint 3: teto de mídia, checklist de contas (só o dono) e regras de crise/LGPD."""
    __tablename__="marketing_governance";__table_args__=(UniqueConstraint("organization_id"),)
    id:Mapped[uuid.UUID]=mapped_column(primary_key=True,default=uuid.uuid4)
    organization_id:Mapped[uuid.UUID]=mapped_column(ForeignKey("organizations.id",ondelete="CASCADE"),index=True)
    updated_by:Mapped[uuid.UUID|None]=mapped_column(ForeignKey("users.id",ondelete="SET NULL"),index=True)
    monthly_ad_ceiling_cents:Mapped[int]=mapped_column(Integer,default=0)
    spent_cents:Mapped[int]=mapped_column(Integer,default=0)
    crisis_escalation:Mapped[bool]=mapped_column(Boolean,default=True)
    lgpd_note:Mapped[str|None]=mapped_column(Text)
    account_checklist:Mapped[dict]=mapped_column(JSON,default=dict)
    seo_checklist:Mapped[dict]=mapped_column(JSON,default=dict)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),server_default=func.now())
    updated_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),server_default=func.now(),onupdate=func.now())
class MarketingSpendRequest(Base):
    __tablename__="marketing_spend_requests";__table_args__=(Index("ix_marketing_spend_tenant_status","organization_id","status"),)
    id:Mapped[uuid.UUID]=mapped_column(primary_key=True,default=uuid.uuid4)
    organization_id:Mapped[uuid.UUID]=mapped_column(ForeignKey("organizations.id",ondelete="CASCADE"),index=True)
    created_by:Mapped[uuid.UUID]=mapped_column(ForeignKey("users.id",ondelete="CASCADE"),index=True)
    reviewed_by:Mapped[uuid.UUID|None]=mapped_column(ForeignKey("users.id",ondelete="SET NULL"),index=True)
    channel:Mapped[str]=mapped_column(String(40))
    description:Mapped[str]=mapped_column(String(240))
    amount_cents:Mapped[int]=mapped_column(Integer)
    status:Mapped[str]=mapped_column(String(30),default="pending")
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),server_default=func.now())
    reviewed_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True))
class MarketingEngagement(Base):
    """Sprint 4: leitura de engajamento orientando o que publicar."""
    __tablename__="marketing_engagements";__table_args__=(Index("ix_marketing_engagement_tenant_created","organization_id","created_at"),)
    id:Mapped[uuid.UUID]=mapped_column(primary_key=True,default=uuid.uuid4)
    organization_id:Mapped[uuid.UUID]=mapped_column(ForeignKey("organizations.id",ondelete="CASCADE"),index=True)
    created_by:Mapped[uuid.UUID]=mapped_column(ForeignKey("users.id",ondelete="CASCADE"),index=True)
    campaign_id:Mapped[uuid.UUID|None]=mapped_column(ForeignKey("marketing_campaigns.id",ondelete="SET NULL"),index=True)
    channel:Mapped[str]=mapped_column(String(30),default="social")
    label:Mapped[str]=mapped_column(String(180))
    views:Mapped[int]=mapped_column(Integer,default=0)
    clicks:Mapped[int]=mapped_column(Integer,default=0)
    likes:Mapped[int]=mapped_column(Integer,default=0)
    comments:Mapped[int]=mapped_column(Integer,default=0)
    best_day:Mapped[str|None]=mapped_column(String(40))
    audience_note:Mapped[str|None]=mapped_column(Text)
    recommendation:Mapped[str|None]=mapped_column(Text)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),server_default=func.now())
class AuditLog(Base):
    __tablename__="audit_logs"
    id:Mapped[uuid.UUID]=mapped_column(primary_key=True,default=uuid.uuid4);organization_id:Mapped[uuid.UUID]=mapped_column(index=True);user_id:Mapped[uuid.UUID]=mapped_column(index=True);action:Mapped[str]=mapped_column(String(80));resource:Mapped[str]=mapped_column(String(120));detail:Mapped[str|None]=mapped_column(Text);created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),server_default=func.now(),index=True)
