from datetime import UTC,date,datetime,timedelta
from typing import Annotated,Any
import hmac,secrets,uuid
from fastapi import APIRouter,Depends,Header,HTTPException,Request
from sqlalchemy import and_,select
from sqlalchemy.ext.asyncio import AsyncSession
from app import asaas,evolution,llm
from app.auth import Principal,current_principal,require_roles
from app.billing_guard import ensure_subscription_on_register,require_billing_access,subscription_access_payload
from app.core.config import get_settings
from app.core.database import get_session
from app.core.security import create_access_token,hash_password,hash_refresh_token,new_refresh_token,verify_password
from app.crypto import decrypt_secret,encrypt_secret
from app.models import (
    Agent,AgentTask,AuditLog,Channel,ChannelMessage,Contact,Conversation,ConversationMessage,
    InboxThread,KnowledgeChunk,KnowledgeDocument,LlmCredential,MarketingCampaign,MarketingEngagement,MarketingGovernance,
    MarketingLead,MarketingPlaybook,MarketingSpendRequest,Membership,
    Opportunity,Organization,OrganizationOnboarding,OrganizationSubscription,Receivable,
    ReceivablePayment,RefreshSession,Role,SaaSPlan,User,
)
from app.rag import embed_text,retrieve
from app.schemas import (
    AgentFromPresetIn,AgentIn,AgentQueryIn,AgentStatusIn,CampaignIn,CampaignStatusIn,ChannelIn,CheckoutIn,
    EvolutionConnectIn,IncomingMessageIn,KnowledgeDocumentIn,LlmSettingsIn,LoginIn,
    MarketingDiagnosisIn,MarketingDiscoveryIn,MarketingEngagementIn,MarketingGovernanceIn,MarketingLeadIn,MarketingPackageIn,MarketingSpendIn,
    MarketingSpendReviewIn,OnboardingUpdateIn,OpportunityIn,OutgoingMessageIn,PaymentIn,ReceivableIn,RefreshIn,
    RegisterIn,TeamMemberIn,TeamMemberUpdateIn,TokenPair,
)

router=APIRouter(prefix="/api/v1")
Db=Annotated[AsyncSession,Depends(get_session)]

def split_content(value:str,size:int=900,overlap:int=120)->list[str]:
    clean=" ".join(value.split());chunks=[];start=0
    while start<len(clean):
        end=min(start+size,len(clean));piece=clean[start:end]
        if end<len(clean) and " " in piece:piece=piece.rsplit(" ",1)[0];end=start+len(piece)
        chunks.append(piece)
        if end>=len(clean):break
        start=max(end-overlap,start+1)
    return chunks

def parse_uuid(value:str,label:str="Resource")->uuid.UUID:
    try:return uuid.UUID(value)
    except ValueError:raise HTTPException(404,f"{label} not found")

def _dig(payload:dict,path:str)->Any:
    cur:Any=payload
    for part in path.split("."):
        if not isinstance(cur,dict):return None
        cur=cur.get(part)
    return cur

def _parse_evolution_inbound(payload:dict)->dict|None:
    data=payload.get("data") if isinstance(payload.get("data"),dict) else payload
    text=(
        _dig(data,"message.conversation")
        or _dig(data,"message.extendedTextMessage.text")
        or data.get("text")
        or data.get("body")
        or payload.get("text")
    )
    if not text or not isinstance(text,str):return None
    remote=(
        _dig(data,"key.remoteJid")
        or data.get("remoteJid")
        or data.get("from")
        or data.get("phone")
        or payload.get("phone")
    )
    if not remote or not isinstance(remote,str):return None
    phone="".join(ch for ch in remote.split("@")[0] if ch.isdigit())
    if len(phone)<8:return None
    msg_id=(
        _dig(data,"key.id")
        or data.get("id")
        or data.get("messageId")
        or payload.get("id")
        or f"evo_{secrets.token_hex(8)}"
    )
    name=(
        data.get("pushName")
        or data.get("notifyName")
        or data.get("contact_name")
        or phone
    )
    from_me=_dig(data,"key.fromMe")
    if from_me is True:return None
    return {"external_message_id":str(msg_id),"phone":phone,"contact_name":str(name)[:160],"text":text.strip()[:12000]}

async def _org_llm_answer(org_id:uuid.UUID,agent:Agent,question:str,sources:list[dict],db:AsyncSession,history:list[dict[str,str]]|None=None)->tuple[str,str]:
    context="\n\n".join(f"[{x['document']}] {x['content']}" for x in sources[:5])
    type_prompt=llm.AGENT_SYSTEM_PROMPTS.get(agent.agent_type,"Você é um agente OperAI profissional.")
    system="\n\n".join([
        type_prompt,
        f"Instruções do agente:\n{agent.instructions}",
        f"Contexto da base de conhecimento:\n{context or 'Sem documentos relevantes.'}",
    ])
    cred=await db.scalar(select(LlmCredential).where(LlmCredential.organization_id==org_id))
    if not cred:
        local=f"Com base nos documentos recuperados para '{question}':\n\n{context}" if sources else "Não encontrei informações na base de conhecimento desta empresa."
        return f"{local}\n\nConfigure BYOK em Configurações > LLM para respostas com modelo externo.","local-rag"
    try:
        answer=await llm.chat(cred.provider,decrypt_secret(cred.api_key_encrypted).strip(),cred.model_name or agent.model,system,question,history=history)
        return answer,"byok"
    except Exception as exc:
        local=f"Com base nos documentos recuperados para '{question}':\n\n{context}" if sources else "Não encontrei informações na base de conhecimento desta empresa."
        return f"{local}\n\n(Aviso: falha no provedor LLM BYOK — {exc}. Verifique a chave em Configurações > LLM.)","local-rag-fallback"

@router.get("/health")
async def health():return {"status":"ok","service":"operai-api"}

@router.get("/health/db")
async def health_db(db:Db):
    await db.execute(select(1))
    return {"status":"ok","database":"up"}

@router.post("/auth/register",response_model=TokenPair,status_code=201)
async def register(data:RegisterIn,db:Db):
    if await db.scalar(select(User).where(User.email==data.email)):raise HTTPException(409,"Email already registered")
    if await db.scalar(select(Organization).where(Organization.slug==data.organization_slug)):raise HTTPException(409,"Organization slug unavailable")
    user=User(name=data.name,email=data.email,password_hash=hash_password(data.password))
    org=Organization(name=data.organization_name,slug=data.organization_slug)
    db.add_all([user,org]);await db.flush()
    db.add(Membership(user_id=user.id,organization_id=org.id,role=Role.OWNER))
    await ensure_subscription_on_register(org,db,plan_slug="start")
    raw,hashed=new_refresh_token()
    db.add(RefreshSession(user_id=user.id,organization_id=org.id,token_hash=hashed,expires_at=datetime.now(UTC)+timedelta(days=get_settings().refresh_token_days)))
    await db.commit()
    return TokenPair(access_token=create_access_token(user_id=str(user.id),organization_id=str(org.id),role=Role.OWNER.value),refresh_token=raw)

@router.post("/auth/login",response_model=TokenPair)
async def login(data:LoginIn,db:Db):
    row=(await db.execute(select(User,Organization,Membership).join(Membership,Membership.user_id==User.id).join(Organization,Organization.id==Membership.organization_id).where(and_(User.email==data.email,Organization.slug==data.organization_slug,Membership.active.is_(True))))).first()
    if not row or not verify_password(data.password,row.User.password_hash):raise HTTPException(401,"Invalid credentials")
    raw,hashed=new_refresh_token()
    db.add(RefreshSession(user_id=row.User.id,organization_id=row.Organization.id,token_hash=hashed,expires_at=datetime.now(UTC)+timedelta(days=get_settings().refresh_token_days)))
    await db.commit()
    return TokenPair(access_token=create_access_token(user_id=str(row.User.id),organization_id=str(row.Organization.id),role=row.Membership.role.value),refresh_token=raw)

@router.post("/auth/refresh",response_model=TokenPair)
async def refresh(data:RefreshIn,db:Db):
    session=await db.scalar(select(RefreshSession).where(RefreshSession.token_hash==hash_refresh_token(data.refresh_token)))
    if not session or session.revoked_at or session.expires_at<=datetime.now(UTC):raise HTTPException(401,"Invalid refresh token")
    membership=await db.scalar(select(Membership).where(and_(Membership.user_id==session.user_id,Membership.organization_id==session.organization_id,Membership.active.is_(True))))
    if not membership:raise HTTPException(401,"Membership unavailable")
    session.revoked_at=datetime.now(UTC);raw,hashed=new_refresh_token()
    db.add(RefreshSession(user_id=session.user_id,organization_id=session.organization_id,token_hash=hashed,expires_at=datetime.now(UTC)+timedelta(days=get_settings().refresh_token_days)))
    await db.commit()
    return TokenPair(access_token=create_access_token(user_id=str(session.user_id),organization_id=str(session.organization_id),role=membership.role.value),refresh_token=raw)

@router.get("/billing/plans")
async def billing_plans(db:Db):
    rows=(await db.scalars(select(SaaSPlan).where(and_(SaaSPlan.active.is_(True),SaaSPlan.slug.in_(["start","pro","business"]))).order_by(SaaSPlan.sort_order))).all()
    if not rows:
        rows=(await db.scalars(select(SaaSPlan).where(SaaSPlan.active.is_(True)).order_by(SaaSPlan.sort_order))).all()
    return [{
        "id":str(x.id),
        "slug":x.slug,
        "name":x.name,
        "price_cents":x.monthly_price_cents,
        "monthly_price_cents":x.monthly_price_cents,
        "currency":"BRL",
        "limits":x.limits or {},
        "features":x.features if isinstance(x.features,list) else (list(x.features.keys()) if isinstance(x.features,dict) else []),
        "active":bool(x.active),
        "sort_order":x.sort_order,
    } for x in rows]

@router.get("/billing/subscription")
async def billing_subscription(p:Annotated[Principal,Depends(current_principal)],db:Db):
    sub=await db.scalar(select(OrganizationSubscription).where(OrganizationSubscription.organization_id==p.organization_id))
    plan=None
    if sub:plan=await db.scalar(select(SaaSPlan).where(SaaSPlan.id==sub.plan_id))
    return subscription_access_payload(sub,plan)

@router.post("/billing/checkout")
async def billing_checkout(data:CheckoutIn,p:Annotated[Principal,Depends(require_roles(Role.OWNER,Role.ADMIN))],db:Db):
    plan=await db.scalar(select(SaaSPlan).where(and_(SaaSPlan.slug==data.plan_slug,SaaSPlan.active.is_(True))))
    if not plan:raise HTTPException(404,"Plan not found")
    org=await db.scalar(select(Organization).where(Organization.id==p.organization_id))
    user=await db.scalar(select(User).where(User.id==p.user_id))
    if not org or not user:raise HTTPException(404,"Organization not found")
    sub=await db.scalar(select(OrganizationSubscription).where(OrganizationSubscription.organization_id==p.organization_id))
    if not sub:
        sub=await ensure_subscription_on_register(org,db,plan_slug=plan.slug)
    customer_id=sub.asaas_customer_id
    if not customer_id:
        customer=await asaas.create_customer(org.name,user.email,data.cpf_cnpj)
        customer_id=str(customer.get("id") or "")
        sub.asaas_customer_id=customer_id
    value_reais=round(plan.monthly_price_cents/100,2)
    created=await asaas.create_subscription(customer_id,value_reais,f"OperAI {plan.name}",str(org.id))
    sub.plan_id=plan.id
    sub.asaas_subscription_id=str(created.get("id") or "")
    mode="local" if created.get("mode")=="local" or not get_settings().asaas_api_key.strip() else "asaas"
    if mode!="local":
        sub.status="pending"
    payment_url=created.get("invoiceUrl") or created.get("paymentLink") or created.get("checkoutUrl")
    if not payment_url:
        payment_url=f"{get_settings().frontend_url.rstrip('/')}/app/billing?subscription={created.get('id')}"
    db.add(AuditLog(organization_id=p.organization_id,user_id=p.user_id,action="billing.checkout",resource="subscription",detail=f"{plan.slug}:{mode}"))
    await db.commit()
    return {"checkout_url":payment_url,"payment_url":payment_url,"subscription_id":sub.asaas_subscription_id,"mode":mode,"plan_slug":plan.slug}

@router.post("/billing/confirm-local")
async def billing_confirm_local(payload:dict,p:Annotated[Principal,Depends(require_roles(Role.OWNER,Role.ADMIN))],db:Db):
    if get_settings().asaas_api_key.strip():raise HTTPException(403,"Local confirm is only available when Asaas API key is empty")
    subscription_id=str(payload.get("subscription_id") or "")
    if not subscription_id:raise HTTPException(422,"subscription_id is required")
    sub=await db.scalar(select(OrganizationSubscription).where(OrganizationSubscription.organization_id==p.organization_id))
    if not sub or sub.asaas_subscription_id!=subscription_id:raise HTTPException(404,"Subscription not found")
    today=date.today()
    sub.status="active"
    sub.current_period_start=today
    sub.current_period_end=today+timedelta(days=30)
    sub.trial_ends_at=None
    await db.commit()
    return {"status":"active","subscription_id":subscription_id,"mode":"local"}

@router.post("/webhooks/asaas",status_code=202)
async def asaas_webhook(request:Request,db:Db,asaas_access_token:Annotated[str|None,Header(alias="asaas-access-token")]=None,x_asaas_token:Annotated[str|None,Header()]=None):
    token=asaas_access_token or x_asaas_token or request.headers.get("asaas-access-token")
    expected=get_settings().asaas_webhook_token
    if not token or not hmac.compare_digest(token,expected):raise HTTPException(401,"Invalid Asaas webhook token")
    payload=await request.json()
    event=str(payload.get("event") or payload.get("type") or "").upper()
    payment=payload.get("payment") if isinstance(payload.get("payment"),dict) else {}
    subscription=payload.get("subscription") if isinstance(payload.get("subscription"),dict) else {}
    asaas_sub_id=str(subscription.get("id") or payment.get("subscription") or "")
    external_ref=str(subscription.get("externalReference") or payment.get("externalReference") or "")
    sub=None
    if asaas_sub_id:
        sub=await db.scalar(select(OrganizationSubscription).where(OrganizationSubscription.asaas_subscription_id==asaas_sub_id))
    if not sub and external_ref:
        try:org_id=uuid.UUID(external_ref)
        except ValueError:org_id=None
        if org_id:sub=await db.scalar(select(OrganizationSubscription).where(OrganizationSubscription.organization_id==org_id))
    if not sub:return {"status":"ignored","reason":"subscription_not_found"}
    if event in {"PAYMENT_CONFIRMED","PAYMENT_RECEIVED","SUBSCRIPTION_ACTIVE"}:
        sub.status="active";sub.trial_ends_at=None
        if asaas_sub_id:sub.asaas_subscription_id=asaas_sub_id
    elif event in {"PAYMENT_OVERDUE","SUBSCRIPTION_OVERDUE"}:
        sub.status="past_due"
    elif event in {"SUBSCRIPTION_DELETED","SUBSCRIPTION_INACTIVATED","PAYMENT_DELETED"}:
        sub.status="canceled"
    await db.commit()
    return {"status":"ok","event":event,"subscription_status":sub.status}

@router.get("/settings/llm")
async def get_llm_settings(p:Annotated[Principal,Depends(current_principal)],db:Db):
    cred=await db.scalar(select(LlmCredential).where(LlmCredential.organization_id==p.organization_id))
    if not cred:return {"configured":False,"provider":None,"model_name":None,"api_key_masked":None}
    try:
        raw=decrypt_secret(cred.api_key_encrypted)
        masked=(raw[:4]+"…" +raw[-4:]) if len(raw)>=8 else "••••"
    except Exception:
        masked="••••"
    return {"configured":True,"provider":cred.provider,"model_name":cred.model_name,"api_key_masked":masked,"updated_at":cred.updated_at}

@router.post("/settings/llm/test")
async def test_llm_settings(data:LlmSettingsIn,p:Annotated[Principal,Depends(require_roles(Role.OWNER,Role.ADMIN))],db:Db):
    await require_billing_access(p.organization_id,db)
    try:
        answer=await llm.chat(
            data.provider,
            data.api_key.strip(),
            data.model_name,
            "Você é um assistente de teste da OperAI. Responda em uma frase curta em português.",
            "Confirme que a conexão está funcionando com a palavra OK.",
            temperature=0,
        )
        return {"ok":True,"provider":data.provider,"model_name":data.model_name,"sample":answer[:240]}
    except Exception as exc:
        raise HTTPException(422,f"Não foi possível validar a chave: {exc}") from exc

@router.put("/settings/llm")
async def put_llm_settings(data:LlmSettingsIn,p:Annotated[Principal,Depends(require_roles(Role.OWNER,Role.ADMIN))],db:Db):
    await require_billing_access(p.organization_id,db)
    # Valida a chave antes de gravar — evita PME “salvar” credencial inválida
    try:
        await llm.chat(
            data.provider,
            data.api_key.strip(),
            data.model_name,
            "Você é um assistente de teste da OperAI. Responda só OK.",
            "Responda OK.",
            temperature=0,
        )
    except Exception as exc:
        raise HTTPException(422,f"Chave ou modelo inválidos. Confira o provedor e tente de novo. ({exc})") from exc
    cred=await db.scalar(select(LlmCredential).where(LlmCredential.organization_id==p.organization_id))
    encrypted=encrypt_secret(data.api_key)
    if cred:
        cred.provider=data.provider;cred.model_name=data.model_name;cred.api_key_encrypted=encrypted;cred.updated_at=datetime.now(UTC)
    else:
        cred=LlmCredential(organization_id=p.organization_id,provider=data.provider,model_name=data.model_name,api_key_encrypted=encrypted)
        db.add(cred)
    onboarding=await db.scalar(select(OrganizationOnboarding).where(OrganizationOnboarding.organization_id==p.organization_id))
    if onboarding:
        checklist={**(onboarding.checklist or {}), "llm":True, "account":True}
        onboarding.checklist=checklist
        onboarding.step="llm"
    db.add(AuditLog(organization_id=p.organization_id,user_id=p.user_id,action="settings.llm_updated",resource="llm_credential",detail=data.provider))
    await db.commit()
    raw=data.api_key
    masked=(raw[:4]+"…" +raw[-4:]) if len(raw)>=8 else "••••"
    return {"configured":True,"provider":cred.provider,"model_name":cred.model_name,"api_key_masked":masked}

async def _onboarding_detected(org_id:uuid.UUID,db:AsyncSession)->dict:
    llm_ok=await db.scalar(select(LlmCredential.id).where(LlmCredential.organization_id==org_id).limit(1))
    faq_ok=await db.scalar(select(KnowledgeDocument.id).where(KnowledgeDocument.organization_id==org_id).limit(1))
    wa_ok=await db.scalar(select(Channel.id).where(and_(Channel.organization_id==org_id,Channel.active.is_(True))).limit(1))
    return {"account":True,"llm":bool(llm_ok),"faq":bool(faq_ok),"whatsapp":bool(wa_ok)}

@router.get("/settings/onboarding")
async def get_onboarding(p:Annotated[Principal,Depends(current_principal)],db:Db):
    row=await db.scalar(select(OrganizationOnboarding).where(OrganizationOnboarding.organization_id==p.organization_id))
    if not row:
        row=OrganizationOnboarding(organization_id=p.organization_id,step="welcome",checklist={})
        db.add(row);await db.commit();await db.refresh(row)
    detected=await _onboarding_detected(p.organization_id,db)
    # Validação real prevalece: não dá para “marcar feito” sem ter configurado
    checklist={
        "account":True,
        "llm":detected["llm"],
        "faq":detected["faq"],
        "whatsapp":detected["whatsapp"],
    }
    if all(checklist.values()) and not row.completed_at:
        row.completed_at=datetime.now(UTC);row.step="done";row.checklist=checklist
        await db.commit();await db.refresh(row)
    elif checklist!= (row.checklist or {}):
        row.checklist=checklist
        await db.commit();await db.refresh(row)
    return {"step":row.step,"completed_at":row.completed_at,"checklist":checklist,"detected":detected}

@router.patch("/settings/onboarding")
async def patch_onboarding(data:OnboardingUpdateIn,p:Annotated[Principal,Depends(current_principal)],db:Db):
    row=await db.scalar(select(OrganizationOnboarding).where(OrganizationOnboarding.organization_id==p.organization_id))
    if not row:
        row=OrganizationOnboarding(organization_id=p.organization_id,step="welcome",checklist={})
        db.add(row);await db.flush()
    detected=await _onboarding_detected(p.organization_id,db)
    checklist={
        "account":True,
        "llm":detected["llm"],
        "faq":detected["faq"],
        "whatsapp":detected["whatsapp"],
    }
    row.checklist=checklist
    if data.step is not None:row.step=data.step
    if all(checklist.values()):
        row.completed_at=datetime.now(UTC);row.step="done"
    elif data.completed is True and not all(checklist.values()):
        raise HTTPException(409,"Conclua inteligência, base da empresa e WhatsApp de verdade antes de finalizar.")
    await db.commit()
    return {"step":row.step,"completed_at":row.completed_at,"checklist":checklist,"detected":detected}

@router.get("/opportunities")
async def opportunities(p:Annotated[Principal,Depends(current_principal)],db:Db):
    rows=(await db.scalars(select(Opportunity).where(Opportunity.organization_id==p.organization_id))).all()
    return [{"id":str(x.id),"company":x.company,"contact":x.contact,"stage":x.stage,"value_cents":x.value_cents} for x in rows]

@router.post("/opportunities",status_code=201)
async def create_opportunity(data:OpportunityIn,p:Annotated[Principal,Depends(require_roles(Role.OWNER,Role.ADMIN,Role.MANAGER,Role.OPERATOR))],db:Db):
    await require_billing_access(p.organization_id,db)
    item=Opportunity(organization_id=p.organization_id,**data.model_dump())
    db.add_all([item,AuditLog(organization_id=p.organization_id,user_id=p.user_id,action="opportunity.created",resource="opportunity",detail=data.company)])
    await db.commit();await db.refresh(item)
    return {"id":str(item.id),**data.model_dump()}

def _agent_out(x:Agent)->dict:
    return {"id":str(x.id),"name":x.name,"agent_type":x.agent_type,"status":x.status,"model":x.model,"instructions":x.instructions}

@router.get("/agents/presets")
async def agent_presets(p:Annotated[Principal,Depends(current_principal)]):
    return [
        {
            "id":x["id"],
            "name":x["name"],
            "agent_type":x["agent_type"],
            "blurb":x["blurb"],
            "featured":x["featured"],
            "workspace_href":x["workspace_href"],
            "workspace_label":x["workspace_label"],
        }
        for x in llm.AGENT_PRESETS
    ]

@router.get("/agents")
async def agents(p:Annotated[Principal,Depends(current_principal)],db:Db):
    # Gestor sempre existe no produto — não só dentro do módulo Marketing
    await _ensure_marketing_agent(p.organization_id,p.user_id,db)
    await db.commit()
    rows=(await db.scalars(select(Agent).where(Agent.organization_id==p.organization_id).order_by(Agent.created_at.desc()))).all()
    return [_agent_out(x) for x in rows]

@router.post("/agents/from-preset",status_code=201)
async def create_agent_from_preset(data:AgentFromPresetIn,p:Annotated[Principal,Depends(require_roles(Role.OWNER,Role.ADMIN,Role.MANAGER))],db:Db):
    await require_billing_access(p.organization_id,db)
    preset=next((x for x in llm.AGENT_PRESETS if x["id"]==data.preset_id),None)
    if not preset:raise HTTPException(404,"Preset não encontrado")
    if preset["id"]=="gestor":
        item=await _ensure_marketing_agent(p.organization_id,p.user_id,db)
        await db.commit();await db.refresh(item)
        return _agent_out(item)
    name=data.name or preset["name"]
    existing=await db.scalar(select(Agent).where(and_(Agent.organization_id==p.organization_id,Agent.agent_type==preset["agent_type"])).order_by(Agent.created_at.asc()))
    if existing:
        if existing.status!="active":
            existing.status="active"
        await db.commit();await db.refresh(existing)
        return _agent_out(existing)
    if await db.scalar(select(Agent).where(and_(Agent.organization_id==p.organization_id,Agent.name==name))):
        raise HTTPException(409,"Já existe um agente com este nome")
    item=Agent(
        organization_id=p.organization_id,
        name=name,
        agent_type=preset["agent_type"],
        status="active",
        instructions=preset["instructions"],
    )
    db.add_all([item,AuditLog(organization_id=p.organization_id,user_id=p.user_id,action="agent.created",resource="agent",detail=f"preset:{preset['id']}")])
    await db.commit();await db.refresh(item)
    return _agent_out(item)

@router.post("/agents",status_code=201)
async def create_agent(data:AgentIn,p:Annotated[Principal,Depends(require_roles(Role.OWNER,Role.ADMIN,Role.MANAGER))],db:Db):
    await require_billing_access(p.organization_id,db)
    if await db.scalar(select(Agent).where(and_(Agent.organization_id==p.organization_id,Agent.name==data.name))):raise HTTPException(409,"Agent name already exists")
    item=Agent(organization_id=p.organization_id,**data.model_dump())
    db.add_all([item,AuditLog(organization_id=p.organization_id,user_id=p.user_id,action="agent.created",resource="agent",detail=data.name)])
    await db.commit();await db.refresh(item)
    return {"id":str(item.id),"status":item.status,**data.model_dump()}

@router.patch("/agents/{agent_id}/status")
async def change_agent_status(agent_id:str,data:AgentStatusIn,p:Annotated[Principal,Depends(require_roles(Role.OWNER,Role.ADMIN,Role.MANAGER))],db:Db):
    await require_billing_access(p.organization_id,db)
    item=await db.scalar(select(Agent).where(and_(Agent.id==parse_uuid(agent_id,"Agent"),Agent.organization_id==p.organization_id)))
    if not item:raise HTTPException(404,"Agent not found")
    item.status=data.status
    db.add(AuditLog(organization_id=p.organization_id,user_id=p.user_id,action="agent.status_changed",resource="agent",detail=f"{item.name}:{data.status}"))
    await db.commit();return {"id":str(item.id),"status":item.status}

@router.get("/knowledge/documents")
async def knowledge_documents(p:Annotated[Principal,Depends(current_principal)],db:Db):
    rows=(await db.scalars(select(KnowledgeDocument).where(KnowledgeDocument.organization_id==p.organization_id).order_by(KnowledgeDocument.created_at.desc()))).all()
    return [{"id":str(x.id),"title":x.title,"source_type":x.source_type,"status":x.status,"chunk_count":x.chunk_count} for x in rows]

@router.post("/knowledge/documents",status_code=201)
async def create_knowledge_document(data:KnowledgeDocumentIn,p:Annotated[Principal,Depends(require_roles(Role.OWNER,Role.ADMIN,Role.MANAGER,Role.OPERATOR))],db:Db):
    await require_billing_access(p.organization_id,db)
    parts=split_content(data.content)
    item=KnowledgeDocument(organization_id=p.organization_id,title=data.title,source_type=data.source_type,content=data.content,chunk_count=len(parts))
    db.add(item);await db.flush()
    db.add_all([KnowledgeChunk(organization_id=p.organization_id,document_id=item.id,position=i,content=part,embedding=embed_text(part)) for i,part in enumerate(parts)])
    db.add(AuditLog(organization_id=p.organization_id,user_id=p.user_id,action="knowledge.ingested",resource="knowledge_document",detail=f"{data.title}:{len(parts)} chunks"))
    await db.commit();return {"id":str(item.id),"title":item.title,"chunk_count":len(parts),"status":item.status}

@router.get("/knowledge/search")
async def search_knowledge(q:str,p:Annotated[Principal,Depends(current_principal)],db:Db):
    if len(q.strip())<2:raise HTTPException(422,"Query is too short")
    rows=(await db.execute(select(KnowledgeChunk,KnowledgeDocument.title).join(KnowledgeDocument,KnowledgeDocument.id==KnowledgeChunk.document_id).where(and_(KnowledgeChunk.organization_id==p.organization_id,KnowledgeChunk.content.ilike(f"%{q.strip()}%"))).limit(8))).all()
    return [{"chunk_id":str(chunk.id),"document":title,"content":chunk.content,"position":chunk.position} for chunk,title in rows]

@router.post("/agents/{agent_id}/query")
async def query_agent(agent_id:str,data:AgentQueryIn,p:Annotated[Principal,Depends(current_principal)],db:Db):
    agent=await db.scalar(select(Agent).where(and_(Agent.id==parse_uuid(agent_id,"Agent"),Agent.organization_id==p.organization_id)))
    if not agent:raise HTTPException(404,"Agent not found")
    if agent.status!="active":raise HTTPException(409,"Agent must be active")
    rows=(await db.execute(select(KnowledgeChunk,KnowledgeDocument.title).join(KnowledgeDocument,KnowledgeDocument.id==KnowledgeChunk.document_id).where(KnowledgeChunk.organization_id==p.organization_id))).all()
    sources=retrieve(data.question,list(rows),data.top_k)
    if data.conversation_id:
        conversation=await db.scalar(select(Conversation).where(and_(Conversation.id==parse_uuid(data.conversation_id,"Conversation"),Conversation.agent_id==agent.id,Conversation.organization_id==p.organization_id)))
        if not conversation:raise HTTPException(404,"Conversation not found")
    else:
        conversation=Conversation(organization_id=p.organization_id,agent_id=agent.id,user_id=p.user_id,title=data.question[:180]);db.add(conversation);await db.flush()
    prior=(await db.scalars(select(ConversationMessage).where(ConversationMessage.conversation_id==conversation.id).order_by(ConversationMessage.created_at))).all()
    history=[{"role":m.role,"content":m.content} for m in prior[-10:] if m.role in {"user","assistant"}]
    answer,mode=await _org_llm_answer(p.organization_id,agent,data.question,sources,db,history)
    conversation.updated_at=datetime.now(UTC)
    db.add_all([
        ConversationMessage(organization_id=p.organization_id,conversation_id=conversation.id,role="user",content=data.question),
        ConversationMessage(organization_id=p.organization_id,conversation_id=conversation.id,role="assistant",content=answer,sources=sources),
        AuditLog(organization_id=p.organization_id,user_id=p.user_id,action="agent.queried",resource="agent",detail=f"{agent.name}:{len(sources)} sources"),
    ])
    await db.commit()
    return {"agent":agent.name,"conversation_id":str(conversation.id),"answer":answer,"sources":sources,"mode":mode}

@router.get("/agents/{agent_id}/conversations")
async def agent_conversations(agent_id:str,p:Annotated[Principal,Depends(current_principal)],db:Db):
    rows=(await db.scalars(select(Conversation).where(and_(Conversation.agent_id==parse_uuid(agent_id,"Agent"),Conversation.organization_id==p.organization_id)).order_by(Conversation.updated_at.desc()))).all()
    return [{"id":str(x.id),"title":x.title,"created_at":x.created_at} for x in rows]

@router.get("/conversations/{conversation_id}/messages")
async def conversation_messages(conversation_id:str,p:Annotated[Principal,Depends(current_principal)],db:Db):
    conversation_uuid=parse_uuid(conversation_id,"Conversation")
    allowed=await db.scalar(select(Conversation.id).where(and_(Conversation.id==conversation_uuid,Conversation.organization_id==p.organization_id)))
    if not allowed:raise HTTPException(404,"Conversation not found")
    rows=(await db.scalars(select(ConversationMessage).where(and_(ConversationMessage.conversation_id==conversation_uuid,ConversationMessage.organization_id==p.organization_id)).order_by(ConversationMessage.created_at))).all()
    return [{"id":str(x.id),"role":x.role,"content":x.content,"sources":x.sources or [],"created_at":x.created_at} for x in rows]

@router.post("/channels",status_code=201)
async def create_channel(data:ChannelIn,p:Annotated[Principal,Depends(require_roles(Role.OWNER,Role.ADMIN))],db:Db):
    await require_billing_access(p.organization_id,db)
    if await db.scalar(select(Channel).where(Channel.external_key==data.external_key)):raise HTTPException(409,"Channel key unavailable")
    raw=secrets.token_urlsafe(32)
    item=Channel(organization_id=p.organization_id,name=data.name,external_key=data.external_key,webhook_secret_hash=hash_refresh_token(raw),provider="webhook")
    db.add(item);await db.commit();await db.refresh(item)
    return {"id":str(item.id),"name":item.name,"kind":item.kind,"external_key":item.external_key,"provider":item.provider,"webhook_secret":raw}

@router.get("/channels")
async def channels(p:Annotated[Principal,Depends(current_principal)],db:Db):
    rows=(await db.scalars(select(Channel).where(Channel.organization_id==p.organization_id))).all()
    return [{"id":str(x.id),"name":x.name,"kind":x.kind,"external_key":x.external_key,"provider":x.provider,"instance_name":x.instance_name,"active":x.active} for x in rows]

@router.post("/channels/evolution/connect",status_code=201)
async def evolution_connect(data:EvolutionConnectIn,p:Annotated[Principal,Depends(require_roles(Role.OWNER,Role.ADMIN))],db:Db):
    await require_billing_access(p.organization_id,db)
    instance=data.instance_name or f"operai-{str(p.organization_id)[:8]}-{secrets.token_hex(3)}"
    external_key=f"evo_{instance}"
    if await db.scalar(select(Channel).where(Channel.external_key==external_key)):raise HTTPException(409,"Evolution channel already exists")
    created=await evolution.create_instance(instance)
    raw=secrets.token_urlsafe(32)
    item=Channel(
        organization_id=p.organization_id,
        name=data.name,
        kind="whatsapp",
        external_key=external_key,
        webhook_secret_hash=hash_refresh_token(raw),
        provider="evolution",
        instance_name=instance,
        config={"created":created,"mode":created.get("mode","evolution")},
    )
    db.add(item);await db.commit();await db.refresh(item)
    qr=created.get("qrcode") if isinstance(created.get("qrcode"),dict) else {}
    qrcode_b64=qr.get("base64") or created.get("base64")
    pairing=qr.get("code") or created.get("pairingCode") or created.get("code")
    state=await evolution.connection_state(instance)
    instance_payload=state.get("instance") if isinstance(state.get("instance"),dict) else {}
    status_value=state.get("state") or instance_payload.get("state")
    return {
        "id":str(item.id),
        "name":item.name,
        "external_key":item.external_key,
        "provider":item.provider,
        "instance_name":item.instance_name,
        "qr":qr,
        "qrcode":qrcode_b64,
        "pairing_code":pairing,
        "status":status_value,
        "mode":created.get("mode","evolution"),
        "webhook_url":f"{get_settings().public_api_url.rstrip('/')}/api/v1/webhooks/evolution/{item.external_key}",
    }

@router.get("/channels/{channel_id}/evolution/qr")
async def evolution_qr(channel_id:str,p:Annotated[Principal,Depends(current_principal)],db:Db):
    item=await db.scalar(select(Channel).where(and_(Channel.id==parse_uuid(channel_id,"Channel"),Channel.organization_id==p.organization_id)))
    if not item:raise HTTPException(404,"Channel not found")
    if item.provider!="evolution" or not item.instance_name:raise HTTPException(409,"Channel is not an Evolution instance")
    data=await evolution.get_qrcode(item.instance_name)
    qr=data.get("qrcode") if isinstance(data.get("qrcode"),dict) else {}
    qrcode_b64=qr.get("base64") or data.get("base64")
    pairing=qr.get("code") or data.get("pairingCode") or data.get("code")
    state=await evolution.connection_state(item.instance_name)
    instance_payload=state.get("instance") if isinstance(state.get("instance"),dict) else {}
    status_value=state.get("state") or instance_payload.get("state")
    return {
        "id":str(item.id),
        "instance_name":item.instance_name,
        "qrcode":qrcode_b64,
        "pairing_code":pairing,
        "status":status_value,
    }

@router.get("/channels/{channel_id}/evolution/status")
async def evolution_status(channel_id:str,p:Annotated[Principal,Depends(current_principal)],db:Db):
    item=await db.scalar(select(Channel).where(and_(Channel.id==parse_uuid(channel_id,"Channel"),Channel.organization_id==p.organization_id)))
    if not item:raise HTTPException(404,"Channel not found")
    if item.provider!="evolution" or not item.instance_name:raise HTTPException(409,"Channel is not an Evolution instance")
    state=await evolution.connection_state(item.instance_name)
    return {"id":str(item.id),"instance_name":item.instance_name,"status":state,"active":item.active}

@router.post("/webhooks/evolution/{channel_key}",status_code=202)
async def evolution_webhook(channel_key:str,request:Request,db:Db,x_evolution_token:Annotated[str|None,Header()]=None):
    expected=get_settings().evolution_webhook_token.strip()
    provided=(x_evolution_token or request.query_params.get("token") or "").strip()
    if not expected or not provided or not hmac.compare_digest(provided,expected):raise HTTPException(401,"Invalid webhook token")
    channel=await db.scalar(select(Channel).where(and_(Channel.external_key==channel_key,Channel.active.is_(True),Channel.provider=="evolution")))
    if not channel:raise HTTPException(404,"Channel not found")
    payload=await request.json()
    parsed=_parse_evolution_inbound(payload if isinstance(payload,dict) else {})
    if not parsed:return {"status":"ignored"}
    existing=await db.scalar(select(ChannelMessage).where(and_(ChannelMessage.channel_id==channel.id,ChannelMessage.external_message_id==parsed["external_message_id"])))
    if existing:return {"status":"duplicate","message_id":str(existing.id)}
    contact=await db.scalar(select(Contact).where(and_(Contact.organization_id==channel.organization_id,Contact.phone==parsed["phone"])))
    if not contact:contact=Contact(organization_id=channel.organization_id,name=parsed["contact_name"],phone=parsed["phone"]);db.add(contact);await db.flush()
    thread=await db.scalar(select(InboxThread).where(and_(InboxThread.channel_id==channel.id,InboxThread.contact_id==contact.id)))
    if not thread:thread=InboxThread(organization_id=channel.organization_id,channel_id=channel.id,contact_id=contact.id);db.add(thread);await db.flush()
    thread.unread_count+=1;thread.last_message_at=datetime.now(UTC)
    inbound=ChannelMessage(organization_id=channel.organization_id,channel_id=channel.id,thread_id=thread.id,external_message_id=parsed["external_message_id"],direction="inbound",content=parsed["text"],status="received")
    db.add(inbound)
    agent=await db.scalar(select(Agent).where(and_(Agent.organization_id==channel.organization_id,Agent.agent_type=="whatsapp",Agent.status=="active")))
    reply_text=None
    if agent:
        rows=(await db.execute(select(KnowledgeChunk,KnowledgeDocument.title).join(KnowledgeDocument,KnowledgeDocument.id==KnowledgeChunk.document_id).where(KnowledgeChunk.organization_id==channel.organization_id))).all()
        sources=retrieve(parsed["text"],list(rows),5)
        try:
            reply_text,_mode=await _org_llm_answer(channel.organization_id,agent,parsed["text"],sources,db)
        except HTTPException:
            reply_text="Recebemos sua mensagem. Em breve um atendente responde."
        if channel.instance_name:
            await evolution.send_text(channel.instance_name,parsed["phone"],reply_text)
        outbound=ChannelMessage(
            organization_id=channel.organization_id,
            channel_id=channel.id,
            thread_id=thread.id,
            external_message_id=f"out_{secrets.token_hex(10)}",
            direction="outbound",
            content=reply_text,
            status="sent",
        )
        db.add(outbound)
        db.add(AgentTask(organization_id=channel.organization_id,agent_id=agent.id,task_type="whatsapp.reply",title=f"Responder {parsed['contact_name']}",priority="high",status="completed",input_data={"thread_id":str(thread.id),"message":parsed["text"]},result_data={"reply":reply_text}))
        thread.last_message_at=datetime.now(UTC)
    await db.commit()
    return {"status":"accepted","thread_id":str(thread.id),"message_id":str(inbound.id),"replied":bool(reply_text)}

@router.post("/webhooks/whatsapp/{channel_key}",status_code=202)
async def whatsapp_webhook(channel_key:str,data:IncomingMessageIn,db:Db,x_operai_webhook_secret:Annotated[str|None,Header()]=None):
    channel=await db.scalar(select(Channel).where(and_(Channel.external_key==channel_key,Channel.active.is_(True))))
    if not channel or not x_operai_webhook_secret or not hmac.compare_digest(channel.webhook_secret_hash,hash_refresh_token(x_operai_webhook_secret)):raise HTTPException(401,"Invalid webhook secret")
    existing=await db.scalar(select(ChannelMessage).where(and_(ChannelMessage.channel_id==channel.id,ChannelMessage.external_message_id==data.external_message_id)))
    if existing:return {"status":"duplicate","message_id":str(existing.id)}
    contact=await db.scalar(select(Contact).where(and_(Contact.organization_id==channel.organization_id,Contact.phone==data.phone)))
    if not contact:contact=Contact(organization_id=channel.organization_id,name=data.contact_name,phone=data.phone);db.add(contact);await db.flush()
    thread=await db.scalar(select(InboxThread).where(and_(InboxThread.channel_id==channel.id,InboxThread.contact_id==contact.id)))
    if not thread:thread=InboxThread(organization_id=channel.organization_id,channel_id=channel.id,contact_id=contact.id);db.add(thread);await db.flush()
    thread.unread_count+=1;thread.last_message_at=datetime.now(UTC)
    message=ChannelMessage(organization_id=channel.organization_id,channel_id=channel.id,thread_id=thread.id,external_message_id=data.external_message_id,direction="inbound",content=data.text,status="received")
    agent=await db.scalar(select(Agent).where(and_(Agent.organization_id==channel.organization_id,Agent.agent_type=="whatsapp",Agent.status=="active")))
    db.add(message);db.add(AgentTask(organization_id=channel.organization_id,agent_id=agent.id if agent else None,task_type="whatsapp.reply",title=f"Responder {data.contact_name}",priority="high",input_data={"thread_id":str(thread.id),"message":data.text,"contact":data.contact_name}))
    await db.commit();return {"status":"accepted","thread_id":str(thread.id),"message_id":str(message.id)}

@router.get("/inbox/threads")
async def inbox_threads(p:Annotated[Principal,Depends(current_principal)],db:Db):
    rows=(await db.execute(select(InboxThread,Contact,Channel).join(Contact,Contact.id==InboxThread.contact_id).join(Channel,Channel.id==InboxThread.channel_id).where(InboxThread.organization_id==p.organization_id).order_by(InboxThread.last_message_at.desc()))).all()
    return [{"id":str(t.id),"contact_name":c.name,"phone":c.phone,"channel":ch.name,"status":t.status,"unread_count":t.unread_count,"last_message_at":t.last_message_at} for t,c,ch in rows]

@router.get("/inbox/threads/{thread_id}/messages")
async def inbox_messages(thread_id:str,p:Annotated[Principal,Depends(current_principal)],db:Db):
    thread=await db.scalar(select(InboxThread).where(and_(InboxThread.id==parse_uuid(thread_id,"Thread"),InboxThread.organization_id==p.organization_id)))
    if not thread:raise HTTPException(404,"Thread not found")
    thread.unread_count=0
    rows=(await db.scalars(select(ChannelMessage).where(and_(ChannelMessage.thread_id==thread.id,ChannelMessage.organization_id==p.organization_id)).order_by(ChannelMessage.created_at))).all()
    await db.commit()
    return [{"id":str(x.id),"direction":x.direction,"content":x.content,"status":x.status,"created_at":x.created_at} for x in rows]

@router.post("/inbox/threads/{thread_id}/messages",status_code=202)
async def queue_outgoing_message(thread_id:str,data:OutgoingMessageIn,p:Annotated[Principal,Depends(require_roles(Role.OWNER,Role.ADMIN,Role.MANAGER,Role.OPERATOR))],db:Db):
    await require_billing_access(p.organization_id,db)
    thread=await db.scalar(select(InboxThread).where(and_(InboxThread.id==parse_uuid(thread_id,"Thread"),InboxThread.organization_id==p.organization_id)))
    if not thread:raise HTTPException(404,"Thread not found")
    channel=await db.scalar(select(Channel).where(Channel.id==thread.channel_id))
    contact=await db.scalar(select(Contact).where(Contact.id==thread.contact_id))
    status="queued";error=None
    if channel and contact and channel.active and channel.provider=="evolution" and channel.instance_name:
        try:
            await evolution.send_text(channel.instance_name,contact.phone,data.text)
            status="sent"
        except Exception as exc:
            status="failed";error=str(exc)[:300]
    item=ChannelMessage(organization_id=p.organization_id,channel_id=thread.channel_id,thread_id=thread.id,external_message_id=f"queued_{secrets.token_hex(12)}",direction="outbound",content=data.text,status=status)
    thread.last_message_at=datetime.now(UTC)
    db.add_all([item,AuditLog(organization_id=p.organization_id,user_id=p.user_id,action=f"message.{status}",resource="inbox_thread",detail=str(thread.id))])
    await db.commit();await db.refresh(item);return {"id":str(item.id),"status":item.status,"error":error}

@router.get("/finance/receivables")
async def receivables(p:Annotated[Principal,Depends(current_principal)],db:Db):
    rows=(await db.scalars(select(Receivable).where(Receivable.organization_id==p.organization_id).order_by(Receivable.due_date))).all()
    return [{"id":str(x.id),"customer_name":x.customer_name,"description":x.description,"amount_cents":x.amount_cents,"due_date":x.due_date,"status":"overdue" if x.status=="pending" and x.due_date<date.today() else x.status,"paid_at":x.paid_at} for x in rows]

@router.get("/finance/summary")
async def finance_summary(p:Annotated[Principal,Depends(current_principal)],db:Db):
    rows=(await db.scalars(select(Receivable).where(Receivable.organization_id==p.organization_id))).all()
    pending=sum(x.amount_cents for x in rows if x.status=="pending")
    overdue=sum(x.amount_cents for x in rows if x.status=="pending" and x.due_date<date.today())
    paid=sum(x.amount_cents for x in rows if x.status=="paid")
    return {"pending_cents":pending,"overdue_cents":overdue,"paid_cents":paid,"total_count":len(rows)}

@router.post("/finance/receivables",status_code=201)
async def create_receivable(data:ReceivableIn,p:Annotated[Principal,Depends(require_roles(Role.OWNER,Role.ADMIN,Role.MANAGER))],db:Db):
    await require_billing_access(p.organization_id,db)
    contact_uuid=None
    if data.contact_id:
        contact_uuid=parse_uuid(data.contact_id,"Contact")
        if not await db.scalar(select(Contact.id).where(and_(Contact.id==contact_uuid,Contact.organization_id==p.organization_id))):raise HTTPException(404,"Contact not found")
    item=Receivable(organization_id=p.organization_id,created_by=p.user_id,contact_id=contact_uuid,**data.model_dump(exclude={"contact_id"}))
    agent=await db.scalar(select(Agent).where(and_(Agent.organization_id==p.organization_id,Agent.agent_type=="finance",Agent.status=="active")))
    db.add_all([
        item,
        AgentTask(organization_id=p.organization_id,agent_id=agent.id if agent else None,created_by=p.user_id,task_type="finance.follow_up",title=f"Acompanhar recebimento: {data.customer_name}",priority="normal",input_data={"amount_cents":data.amount_cents,"due_date":str(data.due_date)}),
        AuditLog(organization_id=p.organization_id,user_id=p.user_id,action="receivable.created",resource="receivable",detail=data.customer_name),
    ])
    await db.commit();await db.refresh(item);return {"id":str(item.id),"status":item.status}

@router.post("/finance/receivables/{receivable_id}/payments",status_code=201)
async def pay_receivable(receivable_id:str,data:PaymentIn,p:Annotated[Principal,Depends(require_roles(Role.OWNER,Role.ADMIN,Role.MANAGER))],db:Db):
    await require_billing_access(p.organization_id,db)
    item=await db.scalar(select(Receivable).where(and_(Receivable.id==parse_uuid(receivable_id,"Receivable"),Receivable.organization_id==p.organization_id)))
    if not item:raise HTTPException(404,"Receivable not found")
    if item.status=="paid":raise HTTPException(409,"Receivable already paid")
    if data.amount_cents!=item.amount_cents:raise HTTPException(422,"Payment must match receivable amount")
    paid_at=data.paid_at or datetime.now(UTC);item.status="paid";item.paid_at=paid_at
    db.add_all([ReceivablePayment(organization_id=p.organization_id,receivable_id=item.id,amount_cents=data.amount_cents,method=data.method,paid_at=paid_at,created_by=p.user_id),AuditLog(organization_id=p.organization_id,user_id=p.user_id,action="receivable.paid",resource="receivable",detail=f"{item.customer_name}:{data.amount_cents}")])
    await db.commit();return {"id":str(item.id),"status":item.status,"paid_at":item.paid_at}

@router.get("/marketing/campaigns")
async def marketing_campaigns(p:Annotated[Principal,Depends(current_principal)],db:Db):
    rows=(await db.scalars(select(MarketingCampaign).where(MarketingCampaign.organization_id==p.organization_id).order_by(MarketingCampaign.created_at.desc()))).all()
    return [{"id":str(x.id),"name":x.name,"channel":x.channel,"audience":x.audience,"content":x.content,"status":x.status,"scheduled_at":x.scheduled_at,"sent_count":x.sent_count,"delivered_count":x.delivered_count,"response_count":x.response_count} for x in rows]

@router.post("/marketing/campaigns",status_code=201)
async def create_marketing_campaign(data:CampaignIn,p:Annotated[Principal,Depends(require_roles(Role.OWNER,Role.ADMIN,Role.MANAGER))],db:Db):
    await require_billing_access(p.organization_id,db)
    agent_uuid=None
    if data.agent_id:
        agent_uuid=parse_uuid(data.agent_id,"Agent")
        if not await db.scalar(select(Agent.id).where(and_(Agent.id==agent_uuid,Agent.organization_id==p.organization_id))):raise HTTPException(404,"Agent not found")
    item=MarketingCampaign(organization_id=p.organization_id,created_by=p.user_id,agent_id=agent_uuid,**data.model_dump(exclude={"agent_id"}))
    db.add_all([item,AuditLog(organization_id=p.organization_id,user_id=p.user_id,action="campaign.created",resource="marketing_campaign",detail=data.name)])
    await db.commit();await db.refresh(item);return {"id":str(item.id),"status":item.status}

@router.patch("/marketing/campaigns/{campaign_id}/status")
async def change_campaign_status(campaign_id:str,data:CampaignStatusIn,p:Annotated[Principal,Depends(require_roles(Role.OWNER,Role.ADMIN,Role.MANAGER))],db:Db):
    await require_billing_access(p.organization_id,db)
    item=await db.scalar(select(MarketingCampaign).where(and_(MarketingCampaign.id==parse_uuid(campaign_id,"Campaign"),MarketingCampaign.organization_id==p.organization_id)))
    if not item:raise HTTPException(404,"Campaign not found")
    allowed={"draft":{"approved","cancelled"},"approved":{"scheduled","running","cancelled"},"scheduled":{"running","cancelled"},"running":{"completed","cancelled"},"completed":set(),"cancelled":set()}
    if data.status not in allowed.get(item.status,set()):raise HTTPException(409,"Invalid campaign transition")
    item.status=data.status
    if data.status in {"scheduled","running"}:
        db.add(AgentTask(organization_id=p.organization_id,agent_id=item.agent_id,created_by=p.user_id,idempotency_key=f"campaign:{item.id}:{data.status}",task_type="marketing.campaign",title=f"Campanha: {item.name}",priority="normal",input_data={"campaign_id":str(item.id),"channel":item.channel,"audience":item.audience}))
    db.add(AuditLog(organization_id=p.organization_id,user_id=p.user_id,action="campaign.status_changed",resource="marketing_campaign",detail=f"{item.name}:{data.status}"))
    await db.commit();return {"id":str(item.id),"status":item.status}

def _playbook_out(item:MarketingPlaybook)->dict:
    return {
        "id":str(item.id),
        "package":item.package,
        "step":item.step,
        "diagnosis":item.diagnosis or {},
        "discovery":item.discovery or {},
        "diagnosis_summary":item.diagnosis_summary,
        "action_plan":item.action_plan,
        "posts":item.posts or [],
        "agent_id":str(item.agent_id) if item.agent_id else None,
        "updated_at":item.updated_at.isoformat() if item.updated_at else None,
    }

async def _get_or_create_playbook(p:Principal,db:AsyncSession)->MarketingPlaybook:
    item=await db.scalar(select(MarketingPlaybook).where(MarketingPlaybook.organization_id==p.organization_id))
    if item:return item
    item=MarketingPlaybook(organization_id=p.organization_id,created_by=p.user_id,package="essencial",step="diagnosis",diagnosis={},discovery={})
    db.add(item);await db.commit();await db.refresh(item);return item

async def _ensure_marketing_agent(org_id:uuid.UUID,user_id:uuid.UUID,db:AsyncSession)->Agent:
    agent=await db.scalar(select(Agent).where(and_(Agent.organization_id==org_id,Agent.agent_type=="marketing")).order_by(Agent.created_at.asc()))
    if agent:
        if agent.status!="active":
            agent.status="active"
        return agent
    agent=Agent(
        organization_id=org_id,
        name="Agente Gestor",
        agent_type="marketing",
        status="active",
        instructions=next(
            (x["instructions"] for x in llm.AGENT_PRESETS if x["id"]=="gestor"),
            "Você coordena o pacote Essencial (Gestor + Redação + Mídias). Diagnostique antes de produzir.",
        ),
    )
    db.add(agent);await db.flush()
    db.add(AuditLog(organization_id=org_id,user_id=user_id,action="agent.created",resource="agent",detail=agent.name))
    return agent

def _fallback_marketing_plan(diagnosis:dict,discovery:dict)->tuple[str,str,list[dict]]:
    audience=discovery.get("ideal_customer") or "cliente ideal ainda a detalhar"
    budget=discovery.get("monthly_budget") or "não informado"
    capacity=discovery.get("lead_capacity") or "capacidade não informada"
    channels=diagnosis.get("channels_active") or "redes sociais"
    summary=(
        f"As is: canais ({channels}); frequência {diagnosis.get('frequency','n/d')}; "
        f"resultados comerciais {diagnosis.get('commercial_results') or 'não medidos'}."
    )
    plan=(
        "## Plano Essencial (30 dias)\n\n"
        f"**Público:** {audience}\n"
        f"**Orçamento informado:** {budget}\n"
        f"**Capacidade de leads:** {capacity}\n\n"
        "### Prioridade de canais\n"
        "1. Perfil da empresa no Google + SEO básico (baixo custo, descoberta)\n"
        "2. Redes sociais orgânicas como vitrine (não como único vendedor)\n"
        "3. WhatsApp / e-mail para converter quem já demonstrou interesse\n"
        "4. Mídia paga só depois do orgânico estabilizar e com teto de gasto\n\n"
        "### Próximos passos\n"
        "- Publicar 4 peças com CTA claro para contato\n"
        "- Registrar todo interesse no CRM/Inbox\n"
        "- Revisar engajamento semanalmente com o Agente Gestor\n"
    )
    diff=discovery.get("differentiators") or "o diferencial da empresa"
    posts=[
        {"title":"Quem somos na prática","channel":"social","audience":audience,
         "content":f"Muita gente nos conhece pelas redes — poucos sabem {diff}. "
                   f"Se isso faz sentido para você, responda este post ou chame no WhatsApp. CTA: falar com a equipe."},
        {"title":"Problema que resolvemos","channel":"social","audience":audience,
         "content":f"Se você se identifica com o desafio do nosso cliente ideal ({audience}), "
                   "podemos ajudar com um próximo passo simples. CTA: pedir conversa / formulário."},
        {"title":"Prova de valor","channel":"email","audience":audience,
         "content":f"Assunto: um jeito direto de avançar. Corpo: com base no que já fazemos em {channels}, "
                   f"propomos um caminho curto. Responda este e-mail para agendar. CTA: responder."},
        {"title":"Convite WhatsApp","channel":"whatsapp","audience":audience,
         "content":f"Oi! Vi seu interesse no nosso conteúdo. Com orçamento {budget} e capacidade {capacity}, "
                   "posso te orientar no próximo passo sem enrolação. CTA: continuar a conversa."},
    ]
    return summary,plan,posts

@router.get("/marketing/playbook")
async def get_marketing_playbook(p:Annotated[Principal,Depends(current_principal)],db:Db):
    item=await _get_or_create_playbook(p,db)
    return _playbook_out(item)

@router.put("/marketing/playbook/diagnosis")
async def save_marketing_diagnosis(data:MarketingDiagnosisIn,p:Annotated[Principal,Depends(require_roles(Role.OWNER,Role.ADMIN,Role.MANAGER))],db:Db):
    await require_billing_access(p.organization_id,db)
    item=await _get_or_create_playbook(p,db)
    item.diagnosis=data.model_dump()
    item.step="discovery"
    item.updated_at=datetime.now(UTC)
    db.add(AuditLog(organization_id=p.organization_id,user_id=p.user_id,action="marketing.diagnosis_saved",resource="marketing_playbook",detail="essencial"))
    await db.commit();await db.refresh(item)
    return _playbook_out(item)

@router.put("/marketing/playbook/discovery")
async def save_marketing_discovery(data:MarketingDiscoveryIn,p:Annotated[Principal,Depends(require_roles(Role.OWNER,Role.ADMIN,Role.MANAGER))],db:Db):
    await require_billing_access(p.organization_id,db)
    item=await _get_or_create_playbook(p,db)
    if not item.diagnosis:raise HTTPException(409,"Complete o diagnóstico antes da descoberta")
    item.discovery=data.model_dump()
    item.step="plan"
    item.updated_at=datetime.now(UTC)
    db.add(AuditLog(organization_id=p.organization_id,user_id=p.user_id,action="marketing.discovery_saved",resource="marketing_playbook",detail="essencial"))
    await db.commit();await db.refresh(item)
    return _playbook_out(item)

@router.post("/marketing/playbook/generate")
async def generate_marketing_playbook(p:Annotated[Principal,Depends(require_roles(Role.OWNER,Role.ADMIN,Role.MANAGER))],db:Db):
    await require_billing_access(p.organization_id,db)
    item=await _get_or_create_playbook(p,db)
    if not item.diagnosis or not item.discovery:raise HTTPException(409,"Diagnóstico e descoberta são obrigatórios")
    agent=await _ensure_marketing_agent(p.organization_id,p.user_id,db)
    item.agent_id=agent.id
    rows=(await db.execute(select(KnowledgeChunk,KnowledgeDocument.title).join(KnowledgeDocument,KnowledgeDocument.id==KnowledgeChunk.document_id).where(KnowledgeChunk.organization_id==p.organization_id))).all()
    sources=retrieve("plano de marketing diagnóstico descoberta posicionamento",list(rows),5) if rows else []
    question=(
        "Com base no diagnóstico e na descoberta abaixo, atue como Agente Gestor (Essencial). "
        "Entregue em português, neste formato exato:\n"
        "### RESUMO\n(um parágrafo do as-is)\n"
        "### PLANO\n(plano 30 dias com priorização de canais e investimento)\n"
        "### POSTS\n"
        "1. Título | canal(social|email|whatsapp) | público | texto com CTA\n"
        "2. ...\n3. ...\n4. ...\n"
        "Não sugira Ads pagos se o orçamento for zero ou muito baixo.\n\n"
        f"DIAGNÓSTICO:\n{item.diagnosis}\n\nDESCOBERTA:\n{item.discovery}"
    )
    answer,mode=await _org_llm_answer(p.organization_id,agent,question,sources,db)
    summary,plan,posts=_fallback_marketing_plan(item.diagnosis,item.discovery)
    if "### PLANO" in answer or "### RESUMO" in answer:
        for part in answer.split("### "):
            if not part.strip():continue
            head,*rest=part.split("\n",1)
            body=(rest[0] if rest else "").strip()
            key=head.strip().upper()
            if key.startswith("RESUMO") and body:summary=body
            elif key.startswith("PLANO") and body:plan=body
            elif key.startswith("POSTS") and body:
                parsed=[]
                for line in body.splitlines():
                    line=line.strip()
                    if not line or not line[0].isdigit():continue
                    line=line.split(".",1)[-1].strip()
                    bits=[b.strip() for b in line.split("|")]
                    if len(bits)>=4:
                        ch=bits[1].lower()
                        if "whatsapp" in ch:ch="whatsapp"
                        elif "email" in ch or "e-mail" in ch:ch="email"
                        else:ch="social"
                        parsed.append({"title":bits[0][:180],"channel":ch,"audience":bits[2][:240],"content":"|".join(bits[3:])[:12000]})
                if len(parsed)>=2:posts=parsed[:4]
    elif mode.startswith("byok") and answer.strip():
        plan=answer
    item.diagnosis_summary=summary
    item.action_plan=plan
    item.posts=posts
    item.step="active"
    item.updated_at=datetime.now(UTC)
    db.add(AgentTask(
        organization_id=p.organization_id,agent_id=agent.id,created_by=p.user_id,
        idempotency_key=f"playbook:{item.id}:generate:{uuid.uuid4().hex[:8]}",
        task_type="marketing.plan",title="Plano Marketing Essencial",priority="normal",status="completed",
        input_data={"playbook_id":str(item.id)},result_data={"mode":mode,"posts":len(posts)},
        completed_at=datetime.now(UTC),
    ))
    db.add(AuditLog(organization_id=p.organization_id,user_id=p.user_id,action="marketing.plan_generated",resource="marketing_playbook",detail=mode))
    await db.commit();await db.refresh(item)
    return _playbook_out(item)

@router.post("/marketing/playbook/materialize")
async def materialize_marketing_posts(p:Annotated[Principal,Depends(require_roles(Role.OWNER,Role.ADMIN,Role.MANAGER))],db:Db):
    await require_billing_access(p.organization_id,db)
    item=await _get_or_create_playbook(p,db)
    if not item.posts:raise HTTPException(409,"Gere o plano antes de criar campanhas")
    created=[]
    for post in item.posts:
        ch=post.get("channel") or "social"
        if ch not in {"whatsapp","email","social"}:ch="social"
        campaign=MarketingCampaign(
            organization_id=p.organization_id,
            created_by=p.user_id,
            agent_id=item.agent_id,
            name=str(post.get("title") or "Peça Essencial")[:180],
            channel=ch,
            audience=str(post.get("audience") or "público-alvo")[:240],
            content=str(post.get("content") or "")[:12000],
            status="draft",
        )
        db.add(campaign);created.append(campaign)
    db.add(AuditLog(organization_id=p.organization_id,user_id=p.user_id,action="marketing.posts_materialized",resource="marketing_playbook",detail=str(len(created))))
    await db.commit()
    return {"created":len(created),"campaigns":[{"id":str(c.id),"name":c.name,"channel":c.channel,"status":c.status} for c in created]}

def _normalize_phone(value:str|None)->str|None:
    if not value:return None
    digits="".join(ch for ch in value if ch.isdigit())
    return digits[:30] if digits else None

def _lead_out(item:MarketingLead)->dict:
    return {
        "id":str(item.id),
        "source_title":item.source_title,
        "source_channel":item.source_channel,
        "contact_name":item.contact_name,
        "phone":item.phone,
        "email":item.email,
        "note":item.note,
        "status":item.status,
        "campaign_id":str(item.campaign_id) if item.campaign_id else None,
        "contact_id":str(item.contact_id) if item.contact_id else None,
        "opportunity_id":str(item.opportunity_id) if item.opportunity_id else None,
        "consent_lgpd":bool(item.consent_lgpd),
        "consent_at":item.consent_at.isoformat() if item.consent_at else None,
        "is_crisis":bool(item.is_crisis),
        "created_at":item.created_at.isoformat() if item.created_at else None,
    }

DEFAULT_ACCOUNT_CHECKLIST={
    "google_business":False,
    "meta_business":False,
    "whatsapp_business":False,
}

DEFAULT_SEO_CHECKLIST={
    "google_business_profile":False,
    "nap_consistent":False,
    "site_basic_seo":False,
    "faq_on_site":False,
    "local_keywords":False,
}

def _gov_out(item:MarketingGovernance)->dict:
    checklist={**DEFAULT_ACCOUNT_CHECKLIST,**(item.account_checklist or {})}
    seo={**DEFAULT_SEO_CHECKLIST,**(getattr(item,"seo_checklist",None) or {})}
    remaining=max(0,int(item.monthly_ad_ceiling_cents)-int(item.spent_cents))
    return {
        "id":str(item.id),
        "monthly_ad_ceiling_cents":item.monthly_ad_ceiling_cents,
        "spent_cents":item.spent_cents,
        "remaining_cents":remaining,
        "crisis_escalation":bool(item.crisis_escalation),
        "lgpd_note":item.lgpd_note,
        "account_checklist":checklist,
        "seo_checklist":seo,
        "updated_at":item.updated_at.isoformat() if item.updated_at else None,
    }

async def _get_or_create_governance(org_id:uuid.UUID,user_id:uuid.UUID,db:AsyncSession)->MarketingGovernance:
    item=await db.scalar(select(MarketingGovernance).where(MarketingGovernance.organization_id==org_id))
    if item:return item
    item=MarketingGovernance(
        organization_id=org_id,updated_by=user_id,
        monthly_ad_ceiling_cents=0,spent_cents=0,crisis_escalation=True,
        account_checklist=dict(DEFAULT_ACCOUNT_CHECKLIST),
        seo_checklist=dict(DEFAULT_SEO_CHECKLIST),
        lgpd_note="A empresa contratante é controladora dos dados pessoais captados. A OperAI atua como processadora da plataforma.",
    )
    db.add(item);await db.commit();await db.refresh(item);return item

@router.get("/marketing/leads")
async def list_marketing_leads(p:Annotated[Principal,Depends(current_principal)],db:Db):
    rows=(await db.scalars(select(MarketingLead).where(MarketingLead.organization_id==p.organization_id).order_by(MarketingLead.created_at.desc()).limit(100))).all()
    return [_lead_out(x) for x in rows]

@router.get("/marketing/conversion")
async def marketing_conversion_stats(p:Annotated[Principal,Depends(current_principal)],db:Db):
    since=datetime.now(UTC)-timedelta(days=7)
    rows=(await db.scalars(select(MarketingLead).where(and_(MarketingLead.organization_id==p.organization_id,MarketingLead.created_at>=since)))).all()
    with_contact=sum(1 for x in rows if x.contact_id)
    with_opp=sum(1 for x in rows if x.opportunity_id)
    return {
        "window_days":7,
        "interests":len(rows),
        "leads_with_contact":with_contact,
        "opportunities":with_opp,
        "crisis":sum(1 for x in rows if x.is_crisis),
        "by_channel":{
            "social":sum(1 for x in rows if x.source_channel=="social"),
            "email":sum(1 for x in rows if x.source_channel=="email"),
            "whatsapp":sum(1 for x in rows if x.source_channel=="whatsapp"),
        },
    }

@router.post("/marketing/leads",status_code=201)
async def create_marketing_lead(data:MarketingLeadIn,p:Annotated[Principal,Depends(require_roles(Role.OWNER,Role.ADMIN,Role.MANAGER,Role.OPERATOR))],db:Db):
    await require_billing_access(p.organization_id,db)
    if not data.consent_lgpd:raise HTTPException(422,"Consentimento LGPD é obrigatório para captar o lead")
    phone=_normalize_phone(data.phone)
    email=(data.email or "").strip().lower() or None
    if not phone and not email:raise HTTPException(422,"Informe telefone ou e-mail do interessado")
    gov=await _get_or_create_governance(p.organization_id,p.user_id,db)
    campaign_uuid=None
    if data.campaign_id:
        campaign_uuid=parse_uuid(data.campaign_id,"Campaign")
        camp=await db.scalar(select(MarketingCampaign).where(and_(MarketingCampaign.id==campaign_uuid,MarketingCampaign.organization_id==p.organization_id)))
        if not camp:raise HTTPException(404,"Campaign not found")
        if camp.status in {"draft","approved","scheduled","running"}:
            camp.response_count=int(camp.response_count or 0)+1

    contact=None
    if phone:
        contact=await db.scalar(select(Contact).where(and_(Contact.organization_id==p.organization_id,Contact.phone==phone)))
    if not contact:
        contact_phone=phone or f"mkt:{email}"[:30]
        existing=await db.scalar(select(Contact).where(and_(Contact.organization_id==p.organization_id,Contact.phone==contact_phone)))
        if existing:
            contact=existing
            if data.contact_name and contact.name!=data.contact_name:contact.name=data.contact_name[:160]
        else:
            contact=Contact(organization_id=p.organization_id,name=data.contact_name[:160],phone=contact_phone)
            db.add(contact);await db.flush()

    company=(data.company or data.contact_name)[:160]
    opportunity=Opportunity(
        organization_id=p.organization_id,
        company=company,
        contact=data.contact_name[:160],
        stage="new",
        value_cents=data.value_cents,
    )
    db.add(opportunity);await db.flush()

    now=datetime.now(UTC)
    crisis=bool(data.is_crisis) and bool(gov.crisis_escalation)
    lead=MarketingLead(
        organization_id=p.organization_id,
        created_by=p.user_id,
        campaign_id=campaign_uuid,
        contact_id=contact.id,
        opportunity_id=opportunity.id,
        source_title=data.source_title[:180],
        source_channel=data.source_channel,
        contact_name=data.contact_name[:160],
        phone=phone,
        email=email,
        note=data.note,
        status="escalated" if crisis else "handed_off",
        consent_lgpd=True,
        consent_at=now,
        is_crisis=crisis,
    )
    db.add(lead);await db.flush()

    handoff_agent=await db.scalar(
        select(Agent).where(and_(Agent.organization_id==p.organization_id,Agent.agent_type.in_(["commercial","whatsapp"]),Agent.status=="active")).order_by(Agent.agent_type.asc())
    )
    if not handoff_agent:
        handoff_agent=await db.scalar(select(Agent).where(and_(Agent.organization_id==p.organization_id,Agent.agent_type=="marketing")).order_by(Agent.created_at.asc()))

    db.add(AgentTask(
        organization_id=p.organization_id,
        agent_id=None if crisis else (handoff_agent.id if handoff_agent else None),
        created_by=p.user_id,
        idempotency_key=f"mkt-lead:{lead.id}",
        task_type="marketing.crisis" if crisis else "marketing.handoff",
        title=("CRISE: " if crisis else "Lead: ")+data.contact_name[:70],
        priority="high",
        status="queued",
        input_data={
            "lead_id":str(lead.id),
            "opportunity_id":str(opportunity.id),
            "contact_id":str(contact.id),
            "source_title":data.source_title,
            "source_channel":data.source_channel,
            "phone":phone,
            "email":email,
            "note":data.note,
            "consent_lgpd":True,
            "is_crisis":crisis,
            "next_step":"Escalar para humano — não responder automaticamente" if crisis else "Qualificar no CRM e seguir no WhatsApp/comercial",
        },
    ))
    db.add(AuditLog(
        organization_id=p.organization_id,user_id=p.user_id,
        action="marketing.crisis_escalated" if crisis else "marketing.lead_handed_off",
        resource="marketing_lead",
        detail=f"{data.source_title}:{data.contact_name}",
    ))
    await db.commit();await db.refresh(lead)
    return {
        **_lead_out(lead),
        "handoff":{
            "contact_id":str(contact.id),
            "opportunity_id":str(opportunity.id),
            "agent_id":None if crisis else (str(handoff_agent.id) if handoff_agent else None),
            "human_required":crisis,
            "crm_path":"/app/crm",
            "inbox_path":"/app/inbox",
        },
    }

@router.post("/marketing/leads/{lead_id}/escalate")
async def escalate_marketing_lead(lead_id:str,p:Annotated[Principal,Depends(require_roles(Role.OWNER,Role.ADMIN,Role.MANAGER,Role.OPERATOR))],db:Db):
    await require_billing_access(p.organization_id,db)
    lead=await db.scalar(select(MarketingLead).where(and_(MarketingLead.id==parse_uuid(lead_id,"Lead"),MarketingLead.organization_id==p.organization_id)))
    if not lead:raise HTTPException(404,"Lead not found")
    lead.is_crisis=True;lead.status="escalated"
    db.add(AgentTask(
        organization_id=p.organization_id,agent_id=None,created_by=p.user_id,
        idempotency_key=f"mkt-crisis:{lead.id}:{uuid.uuid4().hex[:6]}",
        task_type="marketing.crisis",title=f"CRISE: {lead.contact_name[:70]}",priority="high",status="queued",
        input_data={"lead_id":str(lead.id),"note":lead.note,"next_step":"Resposta humana obrigatória"},
    ))
    db.add(AuditLog(organization_id=p.organization_id,user_id=p.user_id,action="marketing.crisis_escalated",resource="marketing_lead",detail=lead.contact_name))
    await db.commit();await db.refresh(lead)
    return _lead_out(lead)

@router.get("/marketing/governance")
async def get_marketing_governance(p:Annotated[Principal,Depends(current_principal)],db:Db):
    item=await _get_or_create_governance(p.organization_id,p.user_id,db)
    return _gov_out(item)

@router.put("/marketing/governance")
async def update_marketing_governance(data:MarketingGovernanceIn,p:Annotated[Principal,Depends(require_roles(Role.OWNER,Role.ADMIN))],db:Db):
    await require_billing_access(p.organization_id,db)
    item=await _get_or_create_governance(p.organization_id,p.user_id,db)
    if data.monthly_ad_ceiling_cents is not None:item.monthly_ad_ceiling_cents=data.monthly_ad_ceiling_cents
    if data.crisis_escalation is not None:item.crisis_escalation=data.crisis_escalation
    if data.lgpd_note is not None:item.lgpd_note=data.lgpd_note
    if data.account_checklist is not None:
        merged={**DEFAULT_ACCOUNT_CHECKLIST,**(item.account_checklist or {})}
        for key in DEFAULT_ACCOUNT_CHECKLIST:
            if key in data.account_checklist:merged[key]=bool(data.account_checklist[key])
        item.account_checklist=merged
    if data.seo_checklist is not None:
        seo={**DEFAULT_SEO_CHECKLIST,**(item.seo_checklist or {})}
        for key in DEFAULT_SEO_CHECKLIST:
            if key in data.seo_checklist:seo[key]=bool(data.seo_checklist[key])
        item.seo_checklist=seo
    item.updated_by=p.user_id;item.updated_at=datetime.now(UTC)
    db.add(AuditLog(organization_id=p.organization_id,user_id=p.user_id,action="marketing.governance_updated",resource="marketing_governance",detail=str(item.monthly_ad_ceiling_cents)))
    await db.commit();await db.refresh(item)
    return _gov_out(item)

@router.get("/marketing/spend-requests")
async def list_spend_requests(p:Annotated[Principal,Depends(current_principal)],db:Db):
    rows=(await db.scalars(select(MarketingSpendRequest).where(MarketingSpendRequest.organization_id==p.organization_id).order_by(MarketingSpendRequest.created_at.desc()).limit(50))).all()
    return [{"id":str(x.id),"channel":x.channel,"description":x.description,"amount_cents":x.amount_cents,"status":x.status,"created_at":x.created_at.isoformat() if x.created_at else None,"reviewed_at":x.reviewed_at.isoformat() if x.reviewed_at else None} for x in rows]

@router.post("/marketing/spend-requests",status_code=201)
async def create_spend_request(data:MarketingSpendIn,p:Annotated[Principal,Depends(require_roles(Role.OWNER,Role.ADMIN,Role.MANAGER))],db:Db):
    await require_billing_access(p.organization_id,db)
    gov=await _get_or_create_governance(p.organization_id,p.user_id,db)
    remaining=max(0,gov.monthly_ad_ceiling_cents-gov.spent_cents)
    # Dentro do teto: aprovado automaticamente (ainda é gasto rastreado). Acima do teto: pending até o dono.
    needs_approval=data.amount_cents>remaining
    status="pending" if needs_approval else "approved"
    req=MarketingSpendRequest(
        organization_id=p.organization_id,created_by=p.user_id,
        channel=data.channel,description=data.description,amount_cents=data.amount_cents,status=status,
    )
    if status=="approved":
        gov.spent_cents=int(gov.spent_cents)+data.amount_cents
        req.reviewed_by=p.user_id;req.reviewed_at=datetime.now(UTC)
    db.add(req)
    db.add(AuditLog(organization_id=p.organization_id,user_id=p.user_id,action="marketing.spend_requested",resource="marketing_spend",detail=f"{status}:{data.amount_cents}"))
    await db.commit();await db.refresh(req)
    return {"id":str(req.id),"status":req.status,"needs_owner_approval":needs_approval,"remaining_cents":max(0,gov.monthly_ad_ceiling_cents-gov.spent_cents)}

@router.patch("/marketing/spend-requests/{request_id}")
async def review_spend_request(request_id:str,data:MarketingSpendReviewIn,p:Annotated[Principal,Depends(require_roles(Role.OWNER,Role.ADMIN))],db:Db):
    await require_billing_access(p.organization_id,db)
    req=await db.scalar(select(MarketingSpendRequest).where(and_(MarketingSpendRequest.id==parse_uuid(request_id,"Spend"),MarketingSpendRequest.organization_id==p.organization_id)))
    if not req:raise HTTPException(404,"Spend request not found")
    if req.status!="pending":raise HTTPException(409,"Request already reviewed")
    gov=await _get_or_create_governance(p.organization_id,p.user_id,db)
    req.status=data.status;req.reviewed_by=p.user_id;req.reviewed_at=datetime.now(UTC)
    if data.status=="approved":
        gov.spent_cents=int(gov.spent_cents)+int(req.amount_cents)
    db.add(AuditLog(organization_id=p.organization_id,user_id=p.user_id,action="marketing.spend_reviewed",resource="marketing_spend",detail=f"{req.id}:{data.status}"))
    await db.commit()
    return {"id":str(req.id),"status":req.status,"spent_cents":gov.spent_cents,"remaining_cents":max(0,gov.monthly_ad_ceiling_cents-gov.spent_cents)}

def _engagement_recommendation(views:int,clicks:int,likes:int,comments:int,best_day:str|None)->str:
    ctr=(clicks/views*100) if views else 0
    parts=[]
    if views==0 and likes==0:
        parts.append("Registre números reais das redes para sair do achismo.")
    elif ctr>=3:
        parts.append("CTR forte — priorize CTAs parecidos e leve tráfego para WhatsApp/CRM.")
    elif views>=100 and ctr<1:
        parts.append("Alcance sem clique — revise CTA e horário de publicação.")
    else:
        parts.append("Mantenha cadência e teste um formato (carrossel/bastidor) na próxima semana.")
    if comments>likes*0.3 and comments>0:
        parts.append("Comentários aquecidos — responda rápido e registre interesses no funil.")
    if best_day:
        parts.append(f"Concentre 1–2 posts em {best_day}.")
    return " ".join(parts)

def _upgrade_suggestion(*,package:str,campaigns:int,leads_7d:int,engagements:int,seo:dict,ceiling:int,playbook_active:bool)->dict:
    reasons=[]
    recommended=package
    if package=="essencial":
        if playbook_active and campaigns>=2 and (leads_7d>=2 or engagements>=2):
            recommended="crescimento"
            reasons=[
                "Orgânico já gera interesse ou você já mede engajamento.",
                "Crescimento adiciona Dados/SEO para profissionalizar leitura e busca local.",
            ]
        else:
            reasons=["Complete o Essencial: plano ativo, peças/campanhas e ao menos 2 interesses ou 2 leituras de engajamento."]
    elif package=="crescimento":
        seo_ready=sum(1 for v in seo.values() if v)>=3
        if seo_ready and ceiling>0 and leads_7d>=3:
            recommended="aceleracao"
            reasons=[
                "SEO/Google avançou e há teto de mídia — momento de testar Ads com governança.",
                "Aceleração inclui tráfego pago sob o teto definido pelo dono.",
            ]
        else:
            reasons=["Para Aceleração: avance o checklist SEO, defina teto de Ads (>0) e estabilize leads (3+ em 7 dias)."]
    else:
        reasons=["Pacote Aceleração ativo — foque otimização de campanhas dentro do teto."]
    return {
        "current_package":package,
        "recommended_package":recommended,
        "ready":recommended!=package,
        "reasons":reasons,
        "packages":{
            "essencial":["Agente Gestor","Redação","Mídias sociais"],
            "crescimento":["+ Design/criativo","+ SEO e conteúdo","+ Dados e análise"],
            "aceleracao":["+ Tráfego pago (Google/Meta) sob teto"],
        },
    }

@router.get("/marketing/engagements")
async def list_engagements(p:Annotated[Principal,Depends(current_principal)],db:Db):
    rows=(await db.scalars(select(MarketingEngagement).where(MarketingEngagement.organization_id==p.organization_id).order_by(MarketingEngagement.created_at.desc()).limit(40))).all()
    return [{"id":str(x.id),"label":x.label,"channel":x.channel,"campaign_id":str(x.campaign_id) if x.campaign_id else None,"views":x.views,"clicks":x.clicks,"likes":x.likes,"comments":x.comments,"best_day":x.best_day,"audience_note":x.audience_note,"recommendation":x.recommendation,"created_at":x.created_at.isoformat() if x.created_at else None} for x in rows]

@router.post("/marketing/engagements",status_code=201)
async def create_engagement(data:MarketingEngagementIn,p:Annotated[Principal,Depends(require_roles(Role.OWNER,Role.ADMIN,Role.MANAGER,Role.OPERATOR))],db:Db):
    await require_billing_access(p.organization_id,db)
    campaign_uuid=None
    if data.campaign_id:
        campaign_uuid=parse_uuid(data.campaign_id,"Campaign")
        if not await db.scalar(select(MarketingCampaign.id).where(and_(MarketingCampaign.id==campaign_uuid,MarketingCampaign.organization_id==p.organization_id))):
            raise HTTPException(404,"Campaign not found")
    rec=_engagement_recommendation(data.views,data.clicks,data.likes,data.comments,data.best_day)
    row=MarketingEngagement(
        organization_id=p.organization_id,created_by=p.user_id,campaign_id=campaign_uuid,
        channel=data.channel,label=data.label[:180],views=data.views,clicks=data.clicks,
        likes=data.likes,comments=data.comments,best_day=data.best_day,audience_note=data.audience_note,
        recommendation=rec,
    )
    db.add(row)
    db.add(AuditLog(organization_id=p.organization_id,user_id=p.user_id,action="marketing.engagement_logged",resource="marketing_engagement",detail=data.label[:120]))
    await db.commit();await db.refresh(row)
    return {"id":str(row.id),"recommendation":rec}

@router.get("/marketing/growth")
async def marketing_growth(p:Annotated[Principal,Depends(current_principal)],db:Db):
    playbook=await _get_or_create_playbook(p,db)
    gov=await _get_or_create_governance(p.organization_id,p.user_id,db)
    since=datetime.now(UTC)-timedelta(days=7)
    leads=(await db.scalars(select(MarketingLead).where(and_(MarketingLead.organization_id==p.organization_id,MarketingLead.created_at>=since)))).all()
    engagements=(await db.scalars(select(MarketingEngagement).where(and_(MarketingEngagement.organization_id==p.organization_id,MarketingEngagement.created_at>=since)))).all()
    campaigns=(await db.scalars(select(MarketingCampaign).where(MarketingCampaign.organization_id==p.organization_id))).all()
    views=sum(x.views for x in engagements)
    clicks=sum(x.clicks for x in engagements)
    likes=sum(x.likes for x in engagements)
    comments=sum(x.comments for x in engagements)
    best_days=[x.best_day for x in engagements if x.best_day]
    top_day=max(set(best_days),key=best_days.count) if best_days else None
    latest_rec=engagements[0].recommendation if engagements else _engagement_recommendation(views,clicks,likes,comments,top_day)
    seo={**DEFAULT_SEO_CHECKLIST,**(gov.seo_checklist or {})}
    suggestion=_upgrade_suggestion(
        package=playbook.package or "essencial",
        campaigns=len(campaigns),
        leads_7d=len(leads),
        engagements=len(engagements),
        seo=seo,
        ceiling=int(gov.monthly_ad_ceiling_cents or 0),
        playbook_active=playbook.step=="active" and bool(playbook.action_plan),
    )
    return {
        "package":playbook.package,
        "engagement_7d":{
            "entries":len(engagements),
            "views":views,
            "clicks":clicks,
            "likes":likes,
            "comments":comments,
            "ctr_pct":round((clicks/views*100),2) if views else 0,
            "best_day":top_day,
            "recommendation":latest_rec,
        },
        "conversion_7d":{"interests":len(leads),"opportunities":sum(1 for x in leads if x.opportunity_id)},
        "seo_checklist":seo,
        "upgrade":suggestion,
        "campaigns":len(campaigns),
    }

@router.post("/marketing/playbook/upgrade")
async def upgrade_marketing_package(data:MarketingPackageIn,p:Annotated[Principal,Depends(require_roles(Role.OWNER,Role.ADMIN))],db:Db):
    await require_billing_access(p.organization_id,db)
    playbook=await _get_or_create_playbook(p,db)
    order={"essencial":0,"crescimento":1,"aceleracao":2}
    if order.get(data.package,0)<order.get(playbook.package or "essencial",0):
        raise HTTPException(409,"Downgrade de pacote não é suportado por este endpoint")
    growth=await marketing_growth(p,db)
    suggested=growth["upgrade"]["recommended_package"]
    # Owner pode forçar upgrade; se não for o sugerido e pular etapas, ainda permite com audit
    playbook.package=data.package
    playbook.updated_at=datetime.now(UTC)
    db.add(AgentTask(
        organization_id=p.organization_id,agent_id=playbook.agent_id,created_by=p.user_id,
        idempotency_key=f"playbook:{playbook.id}:pkg:{data.package}:{uuid.uuid4().hex[:6]}",
        task_type="marketing.package_upgrade",title=f"Pacote Marketing: {data.package}",priority="normal",status="completed",
        input_data={"from":growth["package"],"to":data.package,"suggested":suggested},
        result_data={"ready":growth["upgrade"]["ready"]},completed_at=datetime.now(UTC),
    ))
    db.add(AuditLog(organization_id=p.organization_id,user_id=p.user_id,action="marketing.package_upgraded",resource="marketing_playbook",detail=data.package))
    await db.commit();await db.refresh(playbook)
    return {"package":playbook.package,"suggested":suggested,"growth":await marketing_growth(p,db)}

@router.get("/analytics/overview")
async def analytics_overview(p:Annotated[Principal,Depends(current_principal)],db:Db):
    opportunities=(await db.scalars(select(Opportunity).where(Opportunity.organization_id==p.organization_id))).all()
    receivables=(await db.scalars(select(Receivable).where(Receivable.organization_id==p.organization_id))).all()
    agents_rows=(await db.scalars(select(Agent).where(Agent.organization_id==p.organization_id))).all()
    threads=(await db.scalars(select(InboxThread).where(InboxThread.organization_id==p.organization_id))).all()
    campaigns=(await db.scalars(select(MarketingCampaign).where(MarketingCampaign.organization_id==p.organization_id))).all()
    since=datetime.now(UTC)-timedelta(days=7)
    mkt_leads=(await db.scalars(select(MarketingLead).where(and_(MarketingLead.organization_id==p.organization_id,MarketingLead.created_at>=since)))).all()
    audits=(await db.scalars(select(AuditLog).where(and_(AuditLog.organization_id==p.organization_id,AuditLog.created_at>=since)).order_by(AuditLog.created_at.asc()))).all()

    stage_order=["new","qualified","proposal","won","lost"]
    stage_labels={"new":"Novos","qualified":"Qualificados","proposal":"Proposta","won":"Ganhos","lost":"Perdidos"}
    stage_counts={s:0 for s in stage_order}
    for opp in opportunities:
        key=opp.stage if opp.stage in stage_counts else "new"
        stage_counts[key]+=1
    crm_funnel=[{"stage":s,"label":stage_labels[s],"count":stage_counts[s]} for s in stage_order]

    day_keys=[(datetime.now(UTC)-timedelta(days=i)).date().isoformat() for i in range(6,-1,-1)]
    activity_by_day={d:0 for d in day_keys}
    for row in audits:
        if not row.created_at:continue
        key=row.created_at.astimezone(UTC).date().isoformat()
        if key in activity_by_day:activity_by_day[key]+=1
    activity_series=[{"date":d,"count":activity_by_day[d]} for d in day_keys]

    pending=sum(x.amount_cents for x in receivables if x.status=="pending")
    overdue=sum(x.amount_cents for x in receivables if x.status=="pending" and x.due_date<date.today())
    paid=sum(x.amount_cents for x in receivables if x.status=="paid")

    return {
        "crm":{"opportunities":len(opportunities),"pipeline_cents":sum(x.value_cents for x in opportunities),"won":sum(1 for x in opportunities if x.stage=="won")},
        "finance":{"pending_cents":pending,"overdue_cents":overdue,"paid_cents":paid},
        "operations":{"active_agents":sum(1 for x in agents_rows if x.status=="active"),"open_threads":sum(1 for x in threads if x.status=="open"),"unread_messages":sum(x.unread_count for x in threads),"campaigns":len(campaigns)},
        "marketing":{"interests_7d":len(mkt_leads),"leads_7d":sum(1 for x in mkt_leads if x.contact_id),"opportunities_7d":sum(1 for x in mkt_leads if x.opportunity_id)},
        "charts":{
            "crm_funnel":crm_funnel,
            "finance_mix":[
                {"key":"paid","label":"Recebido","cents":paid},
                {"key":"pending","label":"Em aberto","cents":max(pending-overdue,0)},
                {"key":"overdue","label":"Em atraso","cents":overdue},
            ],
            "activity_7d":activity_series,
        },
    }

def _human_activity(action:str,resource:str,detail:str|None)->tuple[str,str]:
    d=(detail or "").strip()
    money_hint=""
    if ":" in d and d.rsplit(":",1)[-1].isdigit():
        name,cents=d.rsplit(":",1)
        try:
            value=int(cents)/100
            money_hint=f"{name} · R$ {value:.2f}".replace(".", ",")
        except ValueError:
            money_hint=d
    labels={
        "opportunity.created":("Nova oportunidade no CRM",d or "Negócio registrado"),
        "agent.created":("Agente adicionado à equipe",d or "Novo agente"),
        "agent.status_changed":("Status de agente atualizado",d.replace(":"," → ") if d else "Alteração de status"),
        "agent.queried":("Consulta a um agente",d or "Pergunta respondida"),
        "knowledge.ingested":("Conteúdo publicado na base",d.split(":")[0] if d else "Novo documento"),
        "settings.llm_updated":("Inteligência (IA) conectada",d or "Chave atualizada"),
        "receivable.created":("Cobrança lançada",d or "Novo recebível"),
        "receivable.paid":("Pagamento recebido",money_hint or d or "Recebimento confirmado"),
        "campaign.created":("Campanha criada",d or "Nova campanha"),
        "campaign.status_changed":("Campanha atualizada",d.replace(":"," → ") if d else "Status alterado"),
        "message.sent":("Mensagem enviada no WhatsApp",d or "Envio"),
        "message.received":("Mensagem recebida no WhatsApp",d or "Entrada"),
        "marketing.diagnosis_saved":("Marketing: diagnóstico salvo","Playbook Essencial"),
        "marketing.discovery_saved":("Marketing: descoberta salva","Playbook Essencial"),
        "marketing.plan_generated":("Plano de Marketing gerado",d or "Plano Essencial"),
        "marketing.posts_materialized":("Peças publicadas como campanhas",f"{d} peça(s)" if d else "Campanhas criadas"),
        "marketing.lead_handed_off":("Interesse virando oportunidade",d or "Handoff comercial"),
        "marketing.crisis_escalated":("Crise de marketing escalada",d or "Atenção necessária"),
        "marketing.governance_updated":("Governança de marketing atualizada","Teto e regras"),
        "marketing.spend_requested":("Pedido de verba de anúncio",d or "Aguardando aprovação"),
        "marketing.spend_reviewed":("Verba de anúncio revisada",d or "Decisão registrada"),
        "marketing.engagement_logged":("Engajamento registrado",d or "Métrica"),
        "marketing.package_upgraded":("Pacote de Marketing atualizado",d or "Upgrade"),
        "billing.checkout":("Assinatura / checkout",d or "Billing"),
        "team.member_created":("Membro adicionado à equipe",d or "Novo acesso"),
        "team.member_updated":("Equipe atualizada",d or "Permissão alterada"),
    }
    title,summary=labels.get(action,(action.replace("."," · ").replace("_"," "),d or resource))
    return title,summary

@router.get("/analytics/activity")
async def analytics_activity(p:Annotated[Principal,Depends(current_principal)],db:Db):
    rows=(await db.scalars(select(AuditLog).where(AuditLog.organization_id==p.organization_id).order_by(AuditLog.created_at.desc()).limit(20))).all()
    out=[]
    for x in rows:
        title,summary=_human_activity(x.action,x.resource,x.detail)
        out.append({
            "id":str(x.id),
            "action":x.action,
            "resource":x.resource,
            "detail":x.detail,
            "title":title,
            "summary":summary,
            "created_at":x.created_at,
        })
    return out

@router.get("/team/members")
async def team_members(p:Annotated[Principal,Depends(current_principal)],db:Db):
    rows=(await db.execute(select(Membership,User).join(User,User.id==Membership.user_id).where(Membership.organization_id==p.organization_id))).all()
    return [{"membership_id":str(m.id),"user_id":str(u.id),"name":u.name,"email":u.email,"role":m.role.value,"active":m.active} for m,u in rows]

@router.post("/team/members",status_code=201)
async def create_team_member(data:TeamMemberIn,p:Annotated[Principal,Depends(require_roles(Role.OWNER,Role.ADMIN))],db:Db):
    await require_billing_access(p.organization_id,db)
    if data.role=="owner" and p.role!=Role.OWNER:raise HTTPException(403,"Only owners can create owners")
    if await db.scalar(select(User.id).where(User.email==data.email)):raise HTTPException(409,"Email already belongs to an account")
    user=User(name=data.name,email=data.email,password_hash=hash_password(data.password));db.add(user);await db.flush()
    membership=Membership(organization_id=p.organization_id,user_id=user.id,role=Role(data.role))
    db.add_all([membership,AuditLog(organization_id=p.organization_id,user_id=p.user_id,action="team.member_created",resource="membership",detail=f"{data.email}:{data.role}")])
    await db.commit();await db.refresh(membership)
    return {"membership_id":str(membership.id),"user_id":str(user.id),"role":membership.role.value,"active":membership.active}

@router.patch("/team/members/{membership_id}")
async def update_team_member(membership_id:str,data:TeamMemberUpdateIn,p:Annotated[Principal,Depends(require_roles(Role.OWNER,Role.ADMIN))],db:Db):
    await require_billing_access(p.organization_id,db)
    item=await db.scalar(select(Membership).where(and_(Membership.id==parse_uuid(membership_id,"Membership"),Membership.organization_id==p.organization_id)))
    if not item:raise HTTPException(404,"Membership not found")
    if item.user_id==p.user_id and data.active is False:raise HTTPException(409,"You cannot deactivate yourself")
    if item.role==Role.OWNER and p.role!=Role.OWNER:raise HTTPException(403,"Only owners can modify owners")
    if data.role:
        if data.role=="owner" and p.role!=Role.OWNER:raise HTTPException(403,"Only owners can assign owner role")
        item.role=Role(data.role)
    if data.active is not None:item.active=data.active
    db.add(AuditLog(organization_id=p.organization_id,user_id=p.user_id,action="team.member_updated",resource="membership",detail=f"{item.id}:{item.role.value}:{item.active}"))
    await db.commit();return {"membership_id":str(item.id),"role":item.role.value,"active":item.active}

@router.post("/demo/seed-nexus")
async def seed_nexus(p:Annotated[Principal,Depends(require_roles(Role.OWNER))],db:Db):
    await require_billing_access(p.organization_id,db)
    existing=(await db.scalars(select(Agent).where(Agent.organization_id==p.organization_id))).all()
    created=[]
    defaults=[
        ("Comercial Nexus","commercial","Você qualifica leads B2B e agenda demos OperAI."),
        ("WhatsApp Nexus","whatsapp","Você atende clientes no WhatsApp com respostas curtas e úteis."),
        ("Financeiro Nexus","finance","Você acompanha cobranças e explica status de recebíveis."),
        ("Marketing Nexus","marketing","Você é o Agente Gestor Essencial: diagnostique, descubra e só então proponha plano e peças com CTA."),
    ]
    for name,agent_type,instructions in defaults:
        if any(a.name==name for a in existing):continue
        item=Agent(organization_id=p.organization_id,name=name,agent_type=agent_type,status="active",instructions=instructions)
        db.add(item);created.append(name)
    if not await db.scalar(select(KnowledgeDocument).where(and_(KnowledgeDocument.organization_id==p.organization_id,KnowledgeDocument.title=="OperAI Nexus FAQ"))):
        content=("OperAI é a plataforma SaaS de agentes de operação para PME. "
                 "Planos Start, Pro e Business. BYOK permite usar sua chave OpenAI/Groq/OpenRouter. "
                 "WhatsApp via Evolution API. Cobrança via Asaas.")
        parts=split_content(content)
        doc=KnowledgeDocument(organization_id=p.organization_id,title="OperAI Nexus FAQ",source_type="faq",content=content,chunk_count=len(parts))
        db.add(doc);await db.flush()
        db.add_all([KnowledgeChunk(organization_id=p.organization_id,document_id=doc.id,position=i,content=part,embedding=embed_text(part)) for i,part in enumerate(parts)])
        created.append("knowledge")
    await db.commit()
    return {"seeded":created,"status":"ok"}
