from datetime import date,datetime
from pydantic import BaseModel,EmailStr,Field

class RegisterIn(BaseModel):
    name:str=Field(min_length=2,max_length=120)
    email:EmailStr
    password:str=Field(min_length=8,max_length=128)
    organization_name:str=Field(min_length=2,max_length=120)
    organization_slug:str=Field(pattern=r"^[a-z0-9-]+$")

class LoginIn(BaseModel):
    email:EmailStr
    password:str
    organization_slug:str

class RefreshIn(BaseModel):
    refresh_token:str

class TokenPair(BaseModel):
    access_token:str
    refresh_token:str
    token_type:str="bearer"

class OpportunityIn(BaseModel):
    company:str=Field(min_length=2,max_length=160)
    contact:str=Field(min_length=2,max_length=160)
    stage:str="new"
    value_cents:int=Field(ge=0)

class AgentIn(BaseModel):
    name:str=Field(min_length=2,max_length=120)
    agent_type:str=Field(pattern=r"^(commercial|whatsapp|finance|marketing)$")
    model:str=Field(default="gpt-5-mini",max_length=80)
    instructions:str=Field(min_length=10,max_length=12000)

class AgentStatusIn(BaseModel):
    status:str=Field(pattern=r"^(draft|active|paused)$")

class KnowledgeDocumentIn(BaseModel):
    title:str=Field(min_length=2,max_length=180)
    content:str=Field(min_length=20,max_length=500000)
    source_type:str=Field(default="text",pattern=r"^(text|faq|policy|manual)$")

class AgentQueryIn(BaseModel):
    question:str=Field(min_length=3,max_length=4000)
    top_k:int=Field(default=5,ge=1,le=10)
    conversation_id:str|None=None

class ChannelIn(BaseModel):
    name:str=Field(min_length=2,max_length=120)
    external_key:str=Field(min_length=4,max_length=120,pattern=r"^[a-zA-Z0-9_-]+$")

class IncomingMessageIn(BaseModel):
    external_message_id:str=Field(min_length=2,max_length=160)
    phone:str=Field(min_length=8,max_length=30)
    contact_name:str=Field(min_length=1,max_length=160)
    text:str=Field(min_length=1,max_length=12000)

class OutgoingMessageIn(BaseModel):
    text:str=Field(min_length=1,max_length=12000)

class ReceivableIn(BaseModel):
    customer_name:str=Field(min_length=2,max_length=180)
    description:str=Field(min_length=2,max_length=240)
    amount_cents:int=Field(gt=0)
    due_date:date
    contact_id:str|None=None

class PaymentIn(BaseModel):
    amount_cents:int=Field(gt=0)
    method:str=Field(pattern=r"^(pix|bank_transfer|card|cash|boleto|other)$")
    paid_at:datetime|None=None

class TeamMemberIn(BaseModel):
    name:str=Field(min_length=2,max_length=120)
    email:EmailStr
    password:str=Field(min_length=8,max_length=128)
    role:str=Field(pattern=r"^(owner|admin|manager|operator|viewer)$")

class TeamMemberUpdateIn(BaseModel):
    role:str|None=Field(default=None,pattern=r"^(owner|admin|manager|operator|viewer)$")
    active:bool|None=None

class CampaignIn(BaseModel):
    name:str=Field(min_length=2,max_length=180)
    channel:str=Field(pattern=r"^(whatsapp|email|social)$")
    audience:str=Field(min_length=2,max_length=240)
    content:str=Field(min_length=5,max_length=12000)
    scheduled_at:datetime|None=None
    agent_id:str|None=None

class CampaignStatusIn(BaseModel):
    status:str=Field(pattern=r"^(draft|approved|scheduled|running|completed|cancelled)$")

class MarketingDiagnosisIn(BaseModel):
    channels_active:str=Field(min_length=2,max_length=2000)
    content_types:str=Field(min_length=2,max_length=2000)
    frequency:str=Field(min_length=2,max_length=500)
    engagement_notes:str=Field(default="",max_length=4000)
    brand_assets:str=Field(default="",max_length=2000)
    commercial_results:str=Field(default="",max_length=2000)

class MarketingDiscoveryIn(BaseModel):
    competitors:str=Field(min_length=2,max_length=2000)
    differentiators:str=Field(min_length=2,max_length=2000)
    ideal_customer:str=Field(min_length=2,max_length=2000)
    mission_values:str=Field(min_length=2,max_length=2000)
    brand_avoid:str=Field(default="",max_length=1000)
    lead_capacity:str=Field(min_length=1,max_length=500)
    seasonality:str=Field(default="",max_length=1000)
    monthly_budget:str=Field(min_length=1,max_length=500)

class LlmSettingsIn(BaseModel):
    provider:str=Field(pattern=r"^(openai|groq|openrouter)$")
    model_name:str=Field(min_length=2,max_length=120)
    api_key:str=Field(min_length=8,max_length=500)

class CheckoutIn(BaseModel):
    plan_slug:str=Field(pattern=r"^(start|pro|business)$")
    cpf_cnpj:str|None=Field(default=None,max_length=20)

class OnboardingUpdateIn(BaseModel):
    step:str|None=Field(default=None,max_length=40)
    checklist:dict|None=None
    completed:bool|None=None

class EvolutionConnectIn(BaseModel):
    name:str=Field(min_length=2,max_length=120)
    instance_name:str|None=Field(default=None,max_length=120)
