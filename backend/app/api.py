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
    InboxThread,KnowledgeChunk,KnowledgeDocument,LlmCredential,MarketingCampaign,Membership,
    Opportunity,Organization,OrganizationOnboarding,OrganizationSubscription,Receivable,
    ReceivablePayment,RefreshSession,Role,SaaSPlan,User,
)
from app.rag import embed_text,retrieve
from app.schemas import (
    AgentIn,AgentQueryIn,AgentStatusIn,CampaignIn,CampaignStatusIn,ChannelIn,CheckoutIn,
    EvolutionConnectIn,IncomingMessageIn,KnowledgeDocumentIn,LlmSettingsIn,LoginIn,
    OnboardingUpdateIn,OpportunityIn,OutgoingMessageIn,PaymentIn,ReceivableIn,RefreshIn,
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
    rows=(await db.scalars(select(SaaSPlan).where(SaaSPlan.active.is_(True)).order_by(SaaSPlan.sort_order))).all()
    return [{"id":str(x.id),"slug":x.slug,"name":x.name,"monthly_price_cents":x.monthly_price_cents,"limits":x.limits,"features":x.features,"sort_order":x.sort_order} for x in rows]

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

@router.put("/settings/llm")
async def put_llm_settings(data:LlmSettingsIn,p:Annotated[Principal,Depends(require_roles(Role.OWNER,Role.ADMIN))],db:Db):
    await require_billing_access(p.organization_id,db)
    cred=await db.scalar(select(LlmCredential).where(LlmCredential.organization_id==p.organization_id))
    encrypted=encrypt_secret(data.api_key)
    if cred:
        cred.provider=data.provider;cred.model_name=data.model_name;cred.api_key_encrypted=encrypted;cred.updated_at=datetime.now(UTC)
    else:
        cred=LlmCredential(organization_id=p.organization_id,provider=data.provider,model_name=data.model_name,api_key_encrypted=encrypted)
        db.add(cred)
    db.add(AuditLog(organization_id=p.organization_id,user_id=p.user_id,action="settings.llm_updated",resource="llm_credential",detail=data.provider))
    await db.commit()
    raw=data.api_key
    masked=(raw[:4]+"…" +raw[-4:]) if len(raw)>=8 else "••••"
    return {"configured":True,"provider":cred.provider,"model_name":cred.model_name,"api_key_masked":masked}

@router.get("/settings/onboarding")
async def get_onboarding(p:Annotated[Principal,Depends(current_principal)],db:Db):
    row=await db.scalar(select(OrganizationOnboarding).where(OrganizationOnboarding.organization_id==p.organization_id))
    if not row:
        row=OrganizationOnboarding(organization_id=p.organization_id,step="welcome",checklist={})
        db.add(row);await db.commit();await db.refresh(row)
    return {"step":row.step,"completed_at":row.completed_at,"checklist":row.checklist or {}}

@router.patch("/settings/onboarding")
async def patch_onboarding(data:OnboardingUpdateIn,p:Annotated[Principal,Depends(current_principal)],db:Db):
    row=await db.scalar(select(OrganizationOnboarding).where(OrganizationOnboarding.organization_id==p.organization_id))
    if not row:
        row=OrganizationOnboarding(organization_id=p.organization_id,step="welcome",checklist={})
        db.add(row);await db.flush()
    if data.step is not None:row.step=data.step
    if data.checklist is not None:row.checklist=data.checklist
    if data.completed is True:row.completed_at=datetime.now(UTC);row.step=data.step or "done"
    await db.commit();return {"step":row.step,"completed_at":row.completed_at,"checklist":row.checklist or {}}

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

@router.get("/agents")
async def agents(p:Annotated[Principal,Depends(current_principal)],db:Db):
    rows=(await db.scalars(select(Agent).where(Agent.organization_id==p.organization_id).order_by(Agent.created_at.desc()))).all()
    return [{"id":str(x.id),"name":x.name,"agent_type":x.agent_type,"status":x.status,"model":x.model,"instructions":x.instructions} for x in rows]

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
        "status":status_value,
        "mode":created.get("mode","evolution"),
        "webhook_url":f"{get_settings().public_api_url.rstrip('/')}/api/v1/webhooks/evolution/{item.external_key}",
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
    if not expected or not x_evolution_token or not hmac.compare_digest(x_evolution_token.strip(),expected):raise HTTPException(401,"Invalid webhook token")
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

@router.get("/analytics/overview")
async def analytics_overview(p:Annotated[Principal,Depends(current_principal)],db:Db):
    opportunities=(await db.scalars(select(Opportunity).where(Opportunity.organization_id==p.organization_id))).all()
    receivables=(await db.scalars(select(Receivable).where(Receivable.organization_id==p.organization_id))).all()
    agents_rows=(await db.scalars(select(Agent).where(Agent.organization_id==p.organization_id))).all()
    threads=(await db.scalars(select(InboxThread).where(InboxThread.organization_id==p.organization_id))).all()
    campaigns=(await db.scalars(select(MarketingCampaign).where(MarketingCampaign.organization_id==p.organization_id))).all()
    return {
        "crm":{"opportunities":len(opportunities),"pipeline_cents":sum(x.value_cents for x in opportunities),"won":sum(1 for x in opportunities if x.stage=="won")},
        "finance":{"pending_cents":sum(x.amount_cents for x in receivables if x.status=="pending"),"overdue_cents":sum(x.amount_cents for x in receivables if x.status=="pending" and x.due_date<date.today()),"paid_cents":sum(x.amount_cents for x in receivables if x.status=="paid")},
        "operations":{"active_agents":sum(1 for x in agents_rows if x.status=="active"),"open_threads":sum(1 for x in threads if x.status=="open"),"unread_messages":sum(x.unread_count for x in threads),"campaigns":len(campaigns)},
    }

@router.get("/analytics/activity")
async def analytics_activity(p:Annotated[Principal,Depends(current_principal)],db:Db):
    rows=(await db.scalars(select(AuditLog).where(AuditLog.organization_id==p.organization_id).order_by(AuditLog.created_at.desc()).limit(20))).all()
    return [{"id":str(x.id),"action":x.action,"resource":x.resource,"detail":x.detail,"created_at":x.created_at} for x in rows]

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
        ("Marketing Nexus","marketing","Você propõe campanhas e mensagens para aquisição."),
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
