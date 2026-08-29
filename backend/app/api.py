from datetime import UTC,date,datetime,timedelta
from typing import Annotated,Any
import hmac,secrets,uuid
from fastapi import APIRouter,Depends,File,Form,Header,HTTPException,Request,UploadFile
from fastapi.responses import PlainTextResponse
from sqlalchemy import and_,select
from sqlalchemy.ext.asyncio import AsyncSession
from app import asaas,evolution,llm,meta_whatsapp
from app.auth import Principal,current_principal,require_roles
from app.billing_guard import ensure_subscription_on_register,require_billing_access,subscription_access_payload
from app.core.config import get_settings
from app.core.database import get_session
from app.core.security import create_access_token,create_password_reset_token,decode_password_reset_token,hash_password,hash_refresh_token,new_refresh_token,verify_password
from app.crypto import decrypt_secret,encrypt_secret
from app.documents import extract_text_from_upload
from app.models import (
    Agent,AgentTask,AuditLog,Channel,ChannelMessage,Contact,Conversation,ConversationMessage,
    InboxThread,KnowledgeChunk,KnowledgeDocument,LlmCredential,MarketingCampaign,MarketingEngagement,MarketingGovernance,
    MarketingLead,MarketingPlaybook,MarketingSpendRequest,Membership,
    Opportunity,Organization,OrganizationBrandKit,OrganizationOnboarding,OrganizationSubscription,Receivable,
    ReceivablePayment,RefreshSession,Role,SaaSPlan,User,
)
from app.rag import embed_text,retrieve
from app.schemas import (
    AgentFromPresetIn,AgentIn,AgentQueryIn,AgentStatusIn,BrandKitIn,CampaignIn,CampaignSpendRequestIn,CampaignStatusIn,ChannelIn,CheckoutIn,
    EvolutionConnectIn,ForgotPasswordIn,IncomingMessageIn,InboxThreadStatusIn,KnowledgeDocumentIn,LlmSettingsIn,LoginIn,MetaConnectIn,
    MarketingDiagnosisIn,MarketingDiscoveryIn,MarketingEngagementIn,MarketingGovernanceIn,MarketingLeadIn,MarketingPackageIn,MarketingSpendIn,
    MarketingSpendReviewIn,OnboardingUpdateIn,OpportunityIn,OpportunityStageIn,OpportunityUpdateIn,OutgoingMessageIn,PaymentIn,ReceivableIn,RefreshIn,
    FinanceSendIn,RegisterIn,ResetPasswordIn,TeamMemberIn,TeamMemberUpdateIn,TemplateSendIn,TokenPair,
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

def _thread_allows_auto_reply(thread:InboxThread)->bool:
    """IA só responde em conversas 'open'. 'human' = atendente; 'closed' = encerrada."""
    return (thread.status or "open") == "open"

def _prepare_thread_for_inbound(thread:InboxThread)->None:
    """Nova mensagem em conversa fechada reabre para a IA; 'human' permanece."""
    if (thread.status or "open") == "closed":
        thread.status="open"

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
    brand_block=await _brand_kit_prompt(org_id,db)
    system="\n\n".join([
        type_prompt,
        f"Instruções do agente:\n{agent.instructions}",
        brand_block or "Kit de marca: ainda não cadastrado — use tom profissional neutro em português brasileiro.",
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

def _normalize_hex_color(value:str)->str:
    raw=(value or "").strip()
    if not raw:return ""
    if not raw.startswith("#"):raw=f"#{raw}"
    if len(raw)!=7 or any(c not in "0123456789abcdefABCDEF" for c in raw[1:]):
        raise HTTPException(422,"Cor inválida. Use formato #RRGGBB.")
    return raw.upper()

def _brand_kit_out(item:OrganizationBrandKit|None)->dict:
    if not item:
        return {
            "configured":False,
            "brand_name":"","tagline":"","voice_tone":"",
            "primary_color":"","secondary_color":"","logo_url":"",
            "avoid":"","notes":"","updated_at":None,
        }
    filled=any([
        item.brand_name.strip(),item.tagline.strip(),item.voice_tone.strip(),
        item.primary_color.strip(),item.secondary_color.strip(),item.logo_url.strip(),
        item.avoid.strip(),item.notes.strip(),
    ])
    return {
        "configured":filled,
        "brand_name":item.brand_name or "",
        "tagline":item.tagline or "",
        "voice_tone":item.voice_tone or "",
        "primary_color":item.primary_color or "",
        "secondary_color":item.secondary_color or "",
        "logo_url":item.logo_url or "",
        "avoid":item.avoid or "",
        "notes":item.notes or "",
        "updated_at":item.updated_at,
    }

async def _get_brand_kit(org_id:uuid.UUID,db:AsyncSession)->OrganizationBrandKit|None:
    return await db.scalar(select(OrganizationBrandKit).where(OrganizationBrandKit.organization_id==org_id))

async def _brand_kit_prompt(org_id:uuid.UUID,db:AsyncSession)->str:
    item=await _get_brand_kit(org_id,db)
    if not item:return ""
    lines=[]
    if item.brand_name.strip():lines.append(f"Nome da marca: {item.brand_name.strip()}")
    if item.tagline.strip():lines.append(f"Slogan: {item.tagline.strip()}")
    if item.voice_tone.strip():lines.append(f"Tom de voz: {item.voice_tone.strip()}")
    colors=[]
    if item.primary_color.strip():colors.append(f"primária {item.primary_color.strip()}")
    if item.secondary_color.strip():colors.append(f"secundária {item.secondary_color.strip()}")
    if colors:lines.append("Cores: "+", ".join(colors))
    if item.logo_url.strip():lines.append(f"Logo: {item.logo_url.strip()}")
    if item.avoid.strip():lines.append(f"Evitar / nunca dizer: {item.avoid.strip()}")
    if item.notes.strip():lines.append(f"Notas de marca: {item.notes.strip()}")
    if not lines:return ""
    return (
        "Kit de marca da empresa (obrigatório respeitar em textos, posts e atendimento):\n"
        + "\n".join(f"- {line}" for line in lines)
    )

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

@router.post("/auth/forgot-password")
async def forgot_password(data:ForgotPasswordIn,db:Db):
    """Gera link de redefinição (1h). Sem SMTP: devolve o link na resposta se a conta existir."""
    generic={"message":"Se a conta existir, use o link de redefinição (válido por 1 hora)."}
    row=(await db.execute(
        select(User,Organization,Membership)
        .join(Membership,Membership.user_id==User.id)
        .join(Organization,Organization.id==Membership.organization_id)
        .where(and_(
            User.email==data.email.strip().lower(),
            Organization.slug==data.organization_slug.strip().lower(),
            Membership.active.is_(True),
            User.active.is_(True),
        ))
    )).first()
    if not row:
        return {**generic,"reset_url":None}
    token=create_password_reset_token(user_id=str(row.User.id),organization_id=str(row.Organization.id))
    base=get_settings().frontend_url.rstrip("/")
    reset_url=f"{base}/reset-password?token={token}&org={row.Organization.slug}"
    db.add(AuditLog(
        organization_id=row.Organization.id,user_id=row.User.id,
        action="auth.password_reset_requested",resource="user",detail=row.User.email,
    ))
    await db.commit()
    return {**generic,"reset_url":reset_url,"expires_in_minutes":60}

@router.post("/auth/reset-password")
async def reset_password(data:ResetPasswordIn,db:Db):
    try:
        payload=decode_password_reset_token(data.token)
    except Exception:
        raise HTTPException(400,"Link inválido ou expirado. Solicite uma nova recuperação.") from None
    user_id=parse_uuid(str(payload.get("sub") or ""),"User")
    org_id=parse_uuid(str(payload.get("org") or ""),"Organization")
    user=await db.scalar(select(User).where(and_(User.id==user_id,User.active.is_(True))))
    if not user:raise HTTPException(400,"Link inválido ou expirado. Solicite uma nova recuperação.")
    membership=await db.scalar(select(Membership).where(and_(Membership.user_id==user.id,Membership.organization_id==org_id,Membership.active.is_(True))))
    if not membership:raise HTTPException(400,"Link inválido ou expirado. Solicite uma nova recuperação.")
    user.password_hash=hash_password(data.password)
    sessions=(await db.scalars(select(RefreshSession).where(and_(RefreshSession.user_id==user.id,RefreshSession.revoked_at.is_(None))))).all()
    now=datetime.now(UTC)
    for s in sessions:
        s.revoked_at=now
    db.add(AuditLog(
        organization_id=org_id,user_id=user.id,
        action="auth.password_reset",resource="user",detail=user.email,
    ))
    await db.commit()
    return {"status":"ok","message":"Senha atualizada. Entre com a nova senha.","organization_slug":(await db.scalar(select(Organization.slug).where(Organization.id==org_id)))}

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

@router.get("/settings/brand-kit")
async def get_brand_kit(p:Annotated[Principal,Depends(current_principal)],db:Db):
    return _brand_kit_out(await _get_brand_kit(p.organization_id,db))

@router.put("/settings/brand-kit")
async def put_brand_kit(data:BrandKitIn,p:Annotated[Principal,Depends(require_roles(Role.OWNER,Role.ADMIN,Role.MANAGER))],db:Db):
    await require_billing_access(p.organization_id,db)
    primary=_normalize_hex_color(data.primary_color)
    secondary=_normalize_hex_color(data.secondary_color)
    logo=(data.logo_url or "").strip()
    if logo and not (logo.startswith("https://") or logo.startswith("http://")):
        raise HTTPException(422,"URL do logo deve começar com http:// ou https://")
    item=await _get_brand_kit(p.organization_id,db)
    if not item:
        item=OrganizationBrandKit(organization_id=p.organization_id)
        db.add(item)
    item.brand_name=(data.brand_name or "").strip()[:120]
    item.tagline=(data.tagline or "").strip()[:240]
    item.voice_tone=(data.voice_tone or "").strip()[:2000]
    item.primary_color=primary
    item.secondary_color=secondary
    item.logo_url=logo[:1000]
    item.avoid=(data.avoid or "").strip()[:2000]
    item.notes=(data.notes or "").strip()[:4000]
    item.updated_at=datetime.now(UTC)
    db.add(AuditLog(
        organization_id=p.organization_id,user_id=p.user_id,
        action="settings.brand_kit_updated",resource="organization_brand_kit",
        detail=item.brand_name or "kit",
    ))
    await db.commit();await db.refresh(item)
    return _brand_kit_out(item)

async def _onboarding_detected(org_id:uuid.UUID,db:AsyncSession)->dict:
    llm_ok=await db.scalar(select(LlmCredential.id).where(LlmCredential.organization_id==org_id).limit(1))
    faq_ok=await db.scalar(select(KnowledgeDocument.id).where(KnowledgeDocument.organization_id==org_id).limit(1))
    wa_ok=await db.scalar(select(Channel.id).where(and_(Channel.organization_id==org_id,Channel.active.is_(True))).limit(1))
    agent_ok=await db.scalar(select(Agent.id).where(and_(Agent.organization_id==org_id,Agent.agent_type=="whatsapp",Agent.status=="active")).limit(1))
    return {"account":True,"llm":bool(llm_ok),"faq":bool(faq_ok),"whatsapp":bool(wa_ok),"agent":bool(agent_ok)}

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
        "agent":detected["agent"],
    }
    if all(checklist.values()):
        if not row.completed_at:
            row.completed_at=datetime.now(UTC)
        row.step="done"
        row.checklist=checklist
        await db.commit();await db.refresh(row)
    else:
        # Novo requisito (ex.: agente) reabre o setup se ainda faltava algo
        changed=checklist!=(row.checklist or {}) or row.completed_at is not None
        if changed:
            row.checklist=checklist
            row.completed_at=None
            if row.step=="done":row.step="agent"
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
        "agent":detected["agent"],
    }
    row.checklist=checklist
    if data.step is not None:row.step=data.step
    if all(checklist.values()):
        row.completed_at=datetime.now(UTC);row.step="done"
    else:
        row.completed_at=None
        if data.completed is True:
            raise HTTPException(409,"Conclua inteligência, base, WhatsApp e agente de atendimento antes de finalizar.")
    await db.commit()
    return {"step":row.step,"completed_at":row.completed_at,"checklist":checklist,"detected":detected}

@router.post("/settings/onboarding/activate-whatsapp-agent",status_code=201)
async def activate_onboarding_whatsapp_agent(p:Annotated[Principal,Depends(require_roles(Role.OWNER,Role.ADMIN,Role.MANAGER))],db:Db):
    """Atalho do setup: cria/ativa o agente de Atendimento WhatsApp."""
    await require_billing_access(p.organization_id,db)
    preset=next((x for x in llm.AGENT_PRESETS if x["id"]=="whatsapp"),None)
    if not preset:raise HTTPException(404,"Preset WhatsApp não encontrado")
    existing=await db.scalar(select(Agent).where(and_(Agent.organization_id==p.organization_id,Agent.agent_type=="whatsapp")).order_by(Agent.created_at.asc()))
    if existing:
        if existing.status!="active":
            existing.status="active"
            db.add(AuditLog(organization_id=p.organization_id,user_id=p.user_id,action="agent.status_changed",resource="agent",detail=f"{existing.name}:active"))
        await db.commit();await db.refresh(existing)
        return _agent_out(existing)
    item=Agent(
        organization_id=p.organization_id,
        name=preset["name"],
        agent_type="whatsapp",
        status="active",
        instructions=preset["instructions"],
    )
    db.add_all([item,AuditLog(organization_id=p.organization_id,user_id=p.user_id,action="agent.created",resource="agent",detail="preset:whatsapp:onboarding")])
    await db.commit();await db.refresh(item)
    return _agent_out(item)

def _opportunity_out(x:Opportunity,campaign_name:str|None=None,lead_source:tuple[str|None,str|None]|None=None)->dict:
    source_title=x.source_title
    source_channel=x.source_channel
    if lead_source:
        if not source_title:source_title=lead_source[0]
        if not source_channel:source_channel=lead_source[1]
    return {
        "id":str(x.id),
        "company":x.company,
        "contact":x.contact,
        "stage":x.stage,
        "value_cents":x.value_cents,
        "source_title":source_title,
        "source_channel":source_channel,
        "source_campaign_id":str(x.source_campaign_id) if x.source_campaign_id else None,
        "campaign_name":campaign_name,
        "created_at":x.created_at.isoformat() if x.created_at else None,
    }

@router.get("/opportunities")
async def opportunities(p:Annotated[Principal,Depends(current_principal)],db:Db):
    rows=(await db.scalars(select(Opportunity).where(Opportunity.organization_id==p.organization_id).order_by(Opportunity.created_at.desc()))).all()
    leads=(await db.scalars(select(MarketingLead).where(and_(MarketingLead.organization_id==p.organization_id,MarketingLead.opportunity_id.isnot(None))))).all()
    lead_by_opp={str(l.opportunity_id):(l.source_title,l.source_channel,l.campaign_id) for l in leads}
    campaign_ids={x.source_campaign_id for x in rows if x.source_campaign_id}
    campaign_ids|={cid for _,_,cid in lead_by_opp.values() if cid}
    campaigns={}
    if campaign_ids:
        camps=(await db.scalars(select(MarketingCampaign).where(MarketingCampaign.id.in_(list(campaign_ids))))).all()
        campaigns={c.id:c.name for c in camps}
    out=[]
    for x in rows:
        lead=lead_by_opp.get(str(x.id))
        camp_id=x.source_campaign_id or (lead[2] if lead else None)
        camp_name=campaigns.get(camp_id) if camp_id else None
        out.append(_opportunity_out(x,camp_name,(lead[0],lead[1]) if lead else None))
    return out

@router.post("/opportunities",status_code=201)
async def create_opportunity(data:OpportunityIn,p:Annotated[Principal,Depends(require_roles(Role.OWNER,Role.ADMIN,Role.MANAGER,Role.OPERATOR))],db:Db):
    await require_billing_access(p.organization_id,db)
    payload=data.model_dump()
    item=Opportunity(organization_id=p.organization_id,**payload)
    db.add_all([item,AuditLog(organization_id=p.organization_id,user_id=p.user_id,action="opportunity.created",resource="opportunity",detail=data.company)])
    await db.commit();await db.refresh(item)
    return _opportunity_out(item)

@router.patch("/opportunities/{opportunity_id}/stage")
async def change_opportunity_stage(opportunity_id:str,data:OpportunityStageIn,p:Annotated[Principal,Depends(require_roles(Role.OWNER,Role.ADMIN,Role.MANAGER,Role.OPERATOR))],db:Db):
    await require_billing_access(p.organization_id,db)
    item=await db.scalar(select(Opportunity).where(and_(Opportunity.id==parse_uuid(opportunity_id,"Opportunity"),Opportunity.organization_id==p.organization_id)))
    if not item:raise HTTPException(404,"Opportunity not found")
    prev=item.stage
    item.stage=data.stage
    db.add(AuditLog(organization_id=p.organization_id,user_id=p.user_id,action="opportunity.stage_changed",resource="opportunity",detail=f"{item.company}:{prev}:{data.stage}"))
    await db.commit();await db.refresh(item)
    return _opportunity_out(item)

@router.patch("/opportunities/{opportunity_id}")
async def update_opportunity(opportunity_id:str,data:OpportunityUpdateIn,p:Annotated[Principal,Depends(require_roles(Role.OWNER,Role.ADMIN,Role.MANAGER,Role.OPERATOR))],db:Db):
    await require_billing_access(p.organization_id,db)
    item=await db.scalar(select(Opportunity).where(and_(Opportunity.id==parse_uuid(opportunity_id,"Opportunity"),Opportunity.organization_id==p.organization_id)))
    if not item:raise HTTPException(404,"Opportunity not found")
    payload=data.model_dump(exclude_unset=True)
    if not payload:raise HTTPException(422,"Nada para atualizar")
    prev_stage=item.stage
    if "company" in payload and payload["company"] is not None:item.company=payload["company"].strip()
    if "contact" in payload and payload["contact"] is not None:item.contact=payload["contact"].strip()
    if "value_cents" in payload and payload["value_cents"] is not None:item.value_cents=payload["value_cents"]
    if "stage" in payload and payload["stage"] is not None:item.stage=payload["stage"]
    if "source_title" in payload:item.source_title=(payload["source_title"] or "").strip() or None
    if "source_channel" in payload:item.source_channel=(payload["source_channel"] or "").strip() or None
    detail=item.company
    if "stage" in payload and payload["stage"] and payload["stage"]!=prev_stage:
        db.add(AuditLog(organization_id=p.organization_id,user_id=p.user_id,action="opportunity.stage_changed",resource="opportunity",detail=f"{item.company}:{prev_stage}:{item.stage}"))
    db.add(AuditLog(organization_id=p.organization_id,user_id=p.user_id,action="opportunity.updated",resource="opportunity",detail=detail))
    await db.commit();await db.refresh(item)
    return _opportunity_out(item)

@router.delete("/opportunities/{opportunity_id}",status_code=204)
async def delete_opportunity(opportunity_id:str,p:Annotated[Principal,Depends(require_roles(Role.OWNER,Role.ADMIN,Role.MANAGER))],db:Db):
    await require_billing_access(p.organization_id,db)
    item=await db.scalar(select(Opportunity).where(and_(Opportunity.id==parse_uuid(opportunity_id,"Opportunity"),Opportunity.organization_id==p.organization_id)))
    if not item:raise HTTPException(404,"Opportunity not found")
    company=item.company
    # Desvincula leads de marketing que apontam para esta oportunidade
    leads=(await db.scalars(select(MarketingLead).where(and_(MarketingLead.organization_id==p.organization_id,MarketingLead.opportunity_id==item.id)))).all()
    for lead in leads:
        lead.opportunity_id=None
    db.add(AuditLog(organization_id=p.organization_id,user_id=p.user_id,action="opportunity.deleted",resource="opportunity",detail=company))
    await db.delete(item)
    await db.commit()
    return None

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
    await db.commit();return {"id":str(item.id),"title":item.title,"chunk_count":len(parts),"status":item.status,"source_type":item.source_type}

@router.post("/knowledge/documents/upload",status_code=201)
async def upload_knowledge_document(
    p:Annotated[Principal,Depends(require_roles(Role.OWNER,Role.ADMIN,Role.MANAGER,Role.OPERATOR))],
    db:Db,
    file:UploadFile=File(...),
    title:str|None=Form(default=None),
):
    await require_billing_access(p.organization_id,db)
    raw=await file.read()
    try:
        content,source_type,meta=extract_text_from_upload(file.filename or "arquivo.pdf",raw)
    except ValueError as exc:
        raise HTTPException(422,str(exc)) from exc
    doc_title=(title or "").strip() or (file.filename or "Documento").rsplit(".",1)[0][:180]
    if len(doc_title)<2:doc_title="Documento da empresa"
    if meta.get("ocr"):
        doc_title=f"{doc_title} (OCR)"[:180]
    parts=split_content(content)
    item=KnowledgeDocument(organization_id=p.organization_id,title=doc_title,source_type=source_type,content=content,chunk_count=len(parts))
    db.add(item);await db.flush()
    db.add_all([KnowledgeChunk(organization_id=p.organization_id,document_id=item.id,position=i,content=part,embedding=embed_text(part)) for i,part in enumerate(parts)])
    ocr_flag="ocr" if meta.get("ocr") else "text"
    db.add(AuditLog(organization_id=p.organization_id,user_id=p.user_id,action="knowledge.ingested",resource="knowledge_document",detail=f"{doc_title}:{len(parts)} chunks:{source_type}:{ocr_flag}"))
    await db.commit()
    return {
        "id":str(item.id),
        "title":item.title,
        "chunk_count":len(parts),
        "status":item.status,
        "source_type":item.source_type,
        "ocr":bool(meta.get("ocr")),
        "meta":meta,
    }

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

@router.post("/channels/meta/connect",status_code=201)
async def meta_connect(data:MetaConnectIn,p:Annotated[Principal,Depends(require_roles(Role.OWNER,Role.ADMIN))],db:Db):
    """Conecta WhatsApp oficial (Cloud API). O dono cria o app na Meta e cola as credenciais."""
    await require_billing_access(p.organization_id,db)
    external_key=f"meta_{data.phone_number_id}"
    if await db.scalar(select(Channel).where(Channel.external_key==external_key)):
        raise HTTPException(409,"Já existe um canal Meta com este Phone Number ID")
    verify=data.verify_token.strip() if data.verify_token else secrets.token_urlsafe(18)
    item=Channel(
        organization_id=p.organization_id,
        name=data.name,
        kind="whatsapp",
        external_key=external_key,
        webhook_secret_hash=hash_refresh_token(verify),
        provider="meta",
        instance_name=data.phone_number_id,
        config={
            "phone_number_id":data.phone_number_id,
            "waba_id":data.waba_id,
            "access_token_encrypted":encrypt_secret(data.access_token.strip()),
            "graph_version":"v21.0",
        },
    )
    db.add(item)
    db.add(AuditLog(organization_id=p.organization_id,user_id=p.user_id,action="channel.meta_connected",resource="channel",detail=data.phone_number_id))
    await db.commit();await db.refresh(item)
    webhook_url=f"{get_settings().public_api_url.rstrip('/')}/api/v1/webhooks/meta/{item.external_key}"
    return {
        "id":str(item.id),
        "name":item.name,
        "provider":item.provider,
        "external_key":item.external_key,
        "phone_number_id":data.phone_number_id,
        "webhook_url":webhook_url,
        "verify_token":verify,
        "message":"Cole a URL e o verify token no painel da Meta (Webhook do WhatsApp).",
    }

@router.get("/webhooks/meta/{channel_key}")
async def meta_webhook_verify(channel_key:str,request:Request,db:Db):
    mode=request.query_params.get("hub.mode")
    token=request.query_params.get("hub.verify_token") or ""
    challenge=request.query_params.get("hub.challenge") or ""
    if mode!="subscribe" or not token or not challenge:
        raise HTTPException(400,"Parâmetros de verificação Meta incompletos")
    channel=await db.scalar(select(Channel).where(and_(Channel.external_key==channel_key,Channel.active.is_(True),Channel.provider=="meta")))
    if not channel or not hmac.compare_digest(channel.webhook_secret_hash,hash_refresh_token(token)):
        raise HTTPException(403,"Verify token inválido")
    return PlainTextResponse(challenge)

@router.post("/webhooks/meta/{channel_key}",status_code=200)
async def meta_webhook(channel_key:str,request:Request,db:Db):
    channel=await db.scalar(select(Channel).where(and_(Channel.external_key==channel_key,Channel.active.is_(True),Channel.provider=="meta")))
    if not channel:raise HTTPException(404,"Channel not found")
    payload=await request.json()
    parsed_list=meta_whatsapp.parse_inbound(payload if isinstance(payload,dict) else {})
    if not parsed_list:return {"status":"ignored"}
    cfg=channel.config or {}
    phone_number_id=str(cfg.get("phone_number_id") or channel.instance_name or "")
    token_enc=cfg.get("access_token_encrypted")
    access_token=decrypt_secret(token_enc) if token_enc else ""
    accepted=0
    for parsed in parsed_list:
        existing=await db.scalar(select(ChannelMessage).where(and_(ChannelMessage.channel_id==channel.id,ChannelMessage.external_message_id==parsed["external_message_id"])))
        if existing:continue
        contact=await db.scalar(select(Contact).where(and_(Contact.organization_id==channel.organization_id,Contact.phone==parsed["phone"])))
        if not contact:
            contact=Contact(organization_id=channel.organization_id,name=parsed["contact_name"],phone=parsed["phone"])
            db.add(contact);await db.flush()
        thread=await db.scalar(select(InboxThread).where(and_(InboxThread.channel_id==channel.id,InboxThread.contact_id==contact.id)))
        if not thread:
            thread=InboxThread(organization_id=channel.organization_id,channel_id=channel.id,contact_id=contact.id)
            db.add(thread);await db.flush()
        _prepare_thread_for_inbound(thread)
        thread.unread_count+=1;thread.last_message_at=datetime.now(UTC)
        inbound=ChannelMessage(organization_id=channel.organization_id,channel_id=channel.id,thread_id=thread.id,external_message_id=parsed["external_message_id"],direction="inbound",content=parsed["text"],status="received")
        db.add(inbound)
        agent=await db.scalar(select(Agent).where(and_(Agent.organization_id==channel.organization_id,Agent.agent_type=="whatsapp",Agent.status=="active")))
        if agent and access_token and phone_number_id and _thread_allows_auto_reply(thread):
            rows=(await db.execute(select(KnowledgeChunk,KnowledgeDocument.title).join(KnowledgeDocument,KnowledgeDocument.id==KnowledgeChunk.document_id).where(KnowledgeChunk.organization_id==channel.organization_id))).all()
            sources=retrieve(parsed["text"],list(rows),5)
            try:
                reply_text,_mode=await _org_llm_answer(channel.organization_id,agent,parsed["text"],sources,db)
            except HTTPException:
                reply_text="Recebemos sua mensagem. Em breve um atendente responde."
            try:
                await meta_whatsapp.send_text(phone_number_id,access_token,parsed["phone"],reply_text)
                status="sent"
            except Exception:
                status="failed"
            db.add(ChannelMessage(
                organization_id=channel.organization_id,channel_id=channel.id,thread_id=thread.id,
                external_message_id=f"out_{secrets.token_hex(10)}",direction="outbound",content=reply_text,status=status,
            ))
            db.add(AgentTask(organization_id=channel.organization_id,agent_id=agent.id,task_type="whatsapp.reply",title=f"Responder {parsed['contact_name']}",priority="high",status="completed",input_data={"thread_id":str(thread.id),"message":parsed["text"]},result_data={"reply":reply_text}))
            thread.last_message_at=datetime.now(UTC)
        accepted+=1
    await db.commit()
    return {"status":"accepted","messages":accepted}

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
    _prepare_thread_for_inbound(thread)
    thread.unread_count+=1;thread.last_message_at=datetime.now(UTC)
    inbound=ChannelMessage(organization_id=channel.organization_id,channel_id=channel.id,thread_id=thread.id,external_message_id=parsed["external_message_id"],direction="inbound",content=parsed["text"],status="received")
    db.add(inbound)
    agent=await db.scalar(select(Agent).where(and_(Agent.organization_id==channel.organization_id,Agent.agent_type=="whatsapp",Agent.status=="active")))
    reply_text=None
    if agent and _thread_allows_auto_reply(thread):
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
    _prepare_thread_for_inbound(thread)
    thread.unread_count+=1;thread.last_message_at=datetime.now(UTC)
    message=ChannelMessage(organization_id=channel.organization_id,channel_id=channel.id,thread_id=thread.id,external_message_id=data.external_message_id,direction="inbound",content=data.text,status="received")
    agent=await db.scalar(select(Agent).where(and_(Agent.organization_id==channel.organization_id,Agent.agent_type=="whatsapp",Agent.status=="active")))
    db.add(message);db.add(AgentTask(organization_id=channel.organization_id,agent_id=agent.id if agent else None,task_type="whatsapp.reply",title=f"Responder {data.contact_name}",priority="high",input_data={"thread_id":str(thread.id),"message":data.text,"contact":data.contact_name}))
    await db.commit();return {"status":"accepted","thread_id":str(thread.id),"message_id":str(message.id)}

@router.get("/inbox/threads")
async def inbox_threads(p:Annotated[Principal,Depends(current_principal)],db:Db):
    rows=(await db.execute(select(InboxThread,Contact,Channel).join(Contact,Contact.id==InboxThread.contact_id).join(Channel,Channel.id==InboxThread.channel_id).where(InboxThread.organization_id==p.organization_id).order_by(InboxThread.last_message_at.desc()))).all()
    return [{"id":str(t.id),"contact_name":c.name,"phone":c.phone,"channel":ch.name,"channel_id":str(ch.id),"provider":ch.provider,"status":t.status,"unread_count":t.unread_count,"last_message_at":t.last_message_at} for t,c,ch in rows]

@router.patch("/inbox/threads/{thread_id}/status")
async def patch_inbox_thread_status(thread_id:str,data:InboxThreadStatusIn,p:Annotated[Principal,Depends(require_roles(Role.OWNER,Role.ADMIN,Role.MANAGER,Role.OPERATOR))],db:Db):
    await require_billing_access(p.organization_id,db)
    thread=await db.scalar(select(InboxThread).where(and_(InboxThread.id==parse_uuid(thread_id,"Thread"),InboxThread.organization_id==p.organization_id)))
    if not thread:raise HTTPException(404,"Thread not found")
    prev=thread.status or "open"
    thread.status=data.status
    db.add(AuditLog(
        organization_id=p.organization_id,user_id=p.user_id,
        action="inbox.thread_status",resource="inbox_thread",
        detail=f"{thread.id}:{prev}:{data.status}",
    ))
    await db.commit();await db.refresh(thread)
    contact=await db.scalar(select(Contact).where(Contact.id==thread.contact_id))
    channel=await db.scalar(select(Channel).where(Channel.id==thread.channel_id))
    return {
        "id":str(thread.id),
        "contact_name":contact.name if contact else "",
        "phone":contact.phone if contact else "",
        "channel":channel.name if channel else "",
        "channel_id":str(channel.id) if channel else None,
        "provider":channel.provider if channel else None,
        "status":thread.status,
        "unread_count":thread.unread_count,
        "last_message_at":thread.last_message_at,
    }

@router.get("/inbox/threads/{thread_id}/messages")
async def inbox_messages(thread_id:str,p:Annotated[Principal,Depends(current_principal)],db:Db):
    thread=await db.scalar(select(InboxThread).where(and_(InboxThread.id==parse_uuid(thread_id,"Thread"),InboxThread.organization_id==p.organization_id)))
    if not thread:raise HTTPException(404,"Thread not found")
    thread.unread_count=0
    rows=(await db.scalars(select(ChannelMessage).where(and_(ChannelMessage.thread_id==thread.id,ChannelMessage.organization_id==p.organization_id)).order_by(ChannelMessage.created_at))).all()
    await db.commit()
    return [{"id":str(x.id),"direction":x.direction,"content":x.content,"status":x.status,"created_at":x.created_at} for x in rows]

def _meta_channel_creds(channel:Channel)->tuple[str,str,str|None]:
    cfg=channel.config or {}
    phone_number_id=str(cfg.get("phone_number_id") or channel.instance_name or "")
    token_enc=cfg.get("access_token_encrypted")
    if not phone_number_id or not token_enc:
        raise HTTPException(409,"Canal Meta sem credenciais")
    waba=cfg.get("waba_id")
    return phone_number_id,decrypt_secret(token_enc),str(waba) if waba else None

@router.get("/channels/{channel_id}/meta/templates")
async def meta_list_templates(channel_id:str,p:Annotated[Principal,Depends(current_principal)],db:Db):
    """Lista templates aprovados na Meta; se WABA ausente/falhar, devolve catálogo sugerido."""
    channel=await db.scalar(select(Channel).where(and_(Channel.id==parse_uuid(channel_id,"Channel"),Channel.organization_id==p.organization_id)))
    if not channel:raise HTTPException(404,"Channel not found")
    if channel.provider!="meta":raise HTTPException(409,"Canal não é Meta Cloud API")
    phone_number_id,token,waba_id=_meta_channel_creds(channel)
    source="suggested"
    templates=[]
    error=None
    if waba_id:
        try:
            templates=await meta_whatsapp.list_message_templates(waba_id,token)
            source="meta"
        except Exception as exc:
            error=str(exc)[:300]
            templates=[]
    if not templates:
        templates=[{**t,"source":"suggested"} for t in meta_whatsapp.STARTER_TEMPLATES]
        source="suggested"
    return {
        "channel_id":str(channel.id),
        "phone_number_id":phone_number_id,
        "waba_id":waba_id,
        "source":source,
        "error":error,
        "templates":templates,
        "hint":(
            "Templates aprovados na sua WABA."
            if source=="meta"
            else "Cadastre templates no Meta Business Manager com estes nomes (ou informe o WABA ID no canal) e aguarde aprovação — especialmente MARKETING."
        ),
    }

@router.post("/inbox/threads/{thread_id}/messages",status_code=202)
async def queue_outgoing_message(thread_id:str,data:OutgoingMessageIn,p:Annotated[Principal,Depends(require_roles(Role.OWNER,Role.ADMIN,Role.MANAGER,Role.OPERATOR))],db:Db):
    await require_billing_access(p.organization_id,db)
    thread=await db.scalar(select(InboxThread).where(and_(InboxThread.id==parse_uuid(thread_id,"Thread"),InboxThread.organization_id==p.organization_id)))
    if not thread:raise HTTPException(404,"Thread not found")
    channel=await db.scalar(select(Channel).where(Channel.id==thread.channel_id))
    contact=await db.scalar(select(Contact).where(Contact.id==thread.contact_id))
    status="queued";error=None
    if channel and contact and channel.active:
        if channel.provider=="evolution" and channel.instance_name:
            try:
                await evolution.send_text(channel.instance_name,contact.phone,data.text)
                status="sent"
            except Exception as exc:
                status="failed";error=str(exc)[:300]
        elif channel.provider=="meta":
            try:
                phone_number_id,token,_waba=_meta_channel_creds(channel)
                await meta_whatsapp.send_text(phone_number_id,token,contact.phone,data.text)
                status="sent"
            except Exception as exc:
                status="failed";error=str(exc)[:300]
    item=ChannelMessage(organization_id=p.organization_id,channel_id=thread.channel_id,thread_id=thread.id,external_message_id=f"queued_{secrets.token_hex(12)}",direction="outbound",content=data.text,status=status)
    thread.last_message_at=datetime.now(UTC)
    # Resposta humana → pausa a IA nesta conversa
    if (thread.status or "open") == "open":
        thread.status="human"
    db.add_all([item,AuditLog(organization_id=p.organization_id,user_id=p.user_id,action=f"message.{status}",resource="inbox_thread",detail=str(thread.id))])
    await db.commit();await db.refresh(item);return {"id":str(item.id),"status":item.status,"error":error,"thread_status":thread.status}

@router.post("/inbox/threads/{thread_id}/template",status_code=202)
async def send_thread_template(thread_id:str,data:TemplateSendIn,p:Annotated[Principal,Depends(require_roles(Role.OWNER,Role.ADMIN,Role.MANAGER,Role.OPERATOR))],db:Db):
    """Envia template aprovado (fora da janela 24h) via Meta Cloud API."""
    await require_billing_access(p.organization_id,db)
    thread=await db.scalar(select(InboxThread).where(and_(InboxThread.id==parse_uuid(thread_id,"Thread"),InboxThread.organization_id==p.organization_id)))
    if not thread:raise HTTPException(404,"Thread not found")
    channel=await db.scalar(select(Channel).where(Channel.id==thread.channel_id))
    contact=await db.scalar(select(Contact).where(Contact.id==thread.contact_id))
    if not channel or not contact:raise HTTPException(404,"Canal ou contato não encontrado")
    if channel.provider!="meta":
        raise HTTPException(409,"Templates oficiais só funcionam no canal Meta Cloud API")
    phone_number_id,token,_waba=_meta_channel_creds(channel)
    preview=f"[template:{data.template_name}]"
    if data.body_params:
        preview+=" "+" · ".join(data.body_params[:6])
    status="sent";error=None
    try:
        await meta_whatsapp.send_template(
            phone_number_id,token,contact.phone,
            data.template_name,data.language,data.body_params,
        )
    except Exception as exc:
        status="failed";error=str(exc)[:400]
    item=ChannelMessage(
        organization_id=p.organization_id,channel_id=thread.channel_id,thread_id=thread.id,
        external_message_id=f"tpl_{secrets.token_hex(10)}",direction="outbound",content=preview[:12000],status=status,
    )
    thread.last_message_at=datetime.now(UTC)
    if (thread.status or "open") == "open":
        thread.status="human"
    db.add_all([
        item,
        AuditLog(
            organization_id=p.organization_id,user_id=p.user_id,
            action="message.template_sent" if status=="sent" else "message.template_failed",
            resource="inbox_thread",detail=f"{data.template_name}:{contact.phone}",
        ),
    ])
    await db.commit();await db.refresh(item)
    if status!="sent":
        raise HTTPException(502,f"Falha ao enviar template: {error}")
    return {"id":str(item.id),"status":item.status,"template_name":data.template_name,"preview":preview}

@router.get("/finance/receivables")
async def receivables(p:Annotated[Principal,Depends(current_principal)],db:Db):
    rows=(await db.execute(select(Receivable,Contact).outerjoin(Contact,Contact.id==Receivable.contact_id).where(Receivable.organization_id==p.organization_id).order_by(Receivable.due_date))).all()
    out=[]
    for x,contact in rows:
        out.append({
            "id":str(x.id),
            "customer_name":x.customer_name,
            "description":x.description,
            "amount_cents":x.amount_cents,
            "due_date":x.due_date,
            "status":"overdue" if x.status=="pending" and x.due_date<date.today() else x.status,
            "paid_at":x.paid_at,
            "contact_id":str(x.contact_id) if x.contact_id else None,
            "phone":contact.phone if contact else None,
        })
    return out

@router.get("/finance/summary")
async def finance_summary(p:Annotated[Principal,Depends(current_principal)],db:Db):
    rows=(await db.scalars(select(Receivable).where(Receivable.organization_id==p.organization_id))).all()
    pending=sum(x.amount_cents for x in rows if x.status=="pending")
    overdue=sum(x.amount_cents for x in rows if x.status=="pending" and x.due_date<date.today())
    paid=sum(x.amount_cents for x in rows if x.status=="paid")
    wa=await db.scalar(select(Channel.id).where(and_(Channel.organization_id==p.organization_id,Channel.active.is_(True),Channel.provider.in_(["meta","evolution"]))).limit(1))
    return {"pending_cents":pending,"overdue_cents":overdue,"paid_cents":paid,"total_count":len(rows),"whatsapp_ready":bool(wa)}

async def _ensure_finance_agent(org_id:uuid.UUID,user_id:uuid.UUID,db:AsyncSession)->Agent:
    agent=await db.scalar(select(Agent).where(and_(Agent.organization_id==org_id,Agent.agent_type=="finance")).order_by(Agent.created_at.asc()))
    if agent:
        if agent.status!="active":agent.status="active"
        return agent
    preset=next((x for x in llm.AGENT_PRESETS if x["id"]=="finance"),None)
    agent=Agent(
        organization_id=org_id,
        name=preset["name"] if preset else "Cobrança",
        agent_type="finance",
        status="active",
        instructions=preset["instructions"] if preset else "Acompanhe cobranças com linguagem profissional. Não invente valores.",
    )
    db.add(agent);await db.flush()
    db.add(AuditLog(organization_id=org_id,user_id=user_id,action="agent.created",resource="agent",detail="preset:finance"))
    return agent

def _normalize_phone(raw:str)->str:
    digits="".join(ch for ch in raw if ch.isdigit())
    if len(digits)<8:raise HTTPException(422,"Telefone inválido — use DDI+DDD+número (ex.: 5511999999999)")
    return digits

async def _upsert_contact_by_phone(org_id:uuid.UUID,name:str,phone:str,db:AsyncSession)->Contact:
    phone=_normalize_phone(phone)
    contact=await db.scalar(select(Contact).where(and_(Contact.organization_id==org_id,Contact.phone==phone)))
    if contact:
        if name and contact.name!=name:contact.name=name[:160]
        return contact
    contact=Contact(organization_id=org_id,name=name[:160],phone=phone)
    db.add(contact);await db.flush()
    return contact

async def _pick_whatsapp_channel(org_id:uuid.UUID,db:AsyncSession)->Channel:
    meta=await db.scalar(select(Channel).where(and_(Channel.organization_id==org_id,Channel.active.is_(True),Channel.provider=="meta")).order_by(Channel.created_at.desc()))
    if meta:return meta
    evo=await db.scalar(select(Channel).where(and_(Channel.organization_id==org_id,Channel.active.is_(True),Channel.provider=="evolution")).order_by(Channel.created_at.desc()))
    if evo:return evo
    raise HTTPException(409,"Nenhum WhatsApp pronto. Conecte Meta oficial ou Evolution em WhatsApp.")

async def _dispatch_whatsapp(channel:Channel,phone:str,text:str)->None:
    if channel.provider=="evolution":
        if not channel.instance_name:raise HTTPException(409,"Canal Evolution sem instância")
        await evolution.send_text(channel.instance_name,phone,text)
        return
    if channel.provider=="meta":
        cfg=channel.config or {}
        phone_number_id=str(cfg.get("phone_number_id") or channel.instance_name or "")
        token_enc=cfg.get("access_token_encrypted")
        if not token_enc or not phone_number_id:raise HTTPException(409,"Canal Meta sem credenciais")
        await meta_whatsapp.send_text(phone_number_id,decrypt_secret(token_enc),phone,text)
        return
    raise HTTPException(409,"Este canal não envia mensagens (só recebe webhook)")

async def _record_outbound_whatsapp(org_id:uuid.UUID,channel:Channel,contact:Contact,text:str,status:str,db:AsyncSession)->InboxThread:
    thread=await db.scalar(select(InboxThread).where(and_(InboxThread.channel_id==channel.id,InboxThread.contact_id==contact.id)))
    if not thread:
        thread=InboxThread(organization_id=org_id,channel_id=channel.id,contact_id=contact.id)
        db.add(thread);await db.flush()
    thread.last_message_at=datetime.now(UTC)
    db.add(ChannelMessage(
        organization_id=org_id,
        channel_id=channel.id,
        thread_id=thread.id,
        external_message_id=f"finance_{secrets.token_hex(10)}",
        direction="outbound",
        content=text,
        status=status,
    ))
    return thread

def _finance_follow_tone(item:Receivable)->tuple[str,str]:
    """Retorna (tone_key, instrução de tom) conforme atraso."""
    days=(date.today()-item.due_date).days
    if days<0:
        return "reminder",f"Vence em {-days} dia(s). Tom cordial de lembrete prévio — sem pressão."
    if days==0:
        return "due_today","Vence hoje. Tom claro e amigável pedindo confirmação do pagamento."
    if days<=7:
        return "overdue_soft",f"Em atraso há {days} dia(s). Tom firme mas respeitoso; ofereça Pix ou contato."
    return "negotiate",f"Em atraso há {days} dia(s). Tom de negociação: proponha novo prazo curto ou parcelamento simbólico, sem inventar juros."

async def _generate_finance_follow_up(item:Receivable,agent:Agent,p:Principal,db:AsyncSession,force:bool=False)->dict:
    tone_key,tone_hint=_finance_follow_tone(item)
    day_key=date.today().isoformat()
    idem=f"finance-follow:{item.id}:{day_key}:{tone_key}"
    existing=await db.scalar(select(AgentTask).where(and_(AgentTask.organization_id==p.organization_id,AgentTask.idempotency_key==idem)))
    if existing and not force and existing.status=="completed" and existing.result_data:
        return {
            "task_id":str(existing.id),
            "receivable_id":str(item.id),
            "tone":tone_key,
            "message":(existing.result_data or {}).get("message"),
            "mode":(existing.result_data or {}).get("mode"),
            "reused":True,
        }
    amount=f"R$ {item.amount_cents/100:.2f}".replace(".",",")
    due=item.due_date.strftime("%d/%m/%Y")
    prompt=(
        f"Redija UMA mensagem curta (máx. 4 frases) em português brasileiro para cobrar/lembrar o cliente.\n"
        f"Cliente: {item.customer_name}\n"
        f"Referência: {item.description}\n"
        f"Valor: {amount}\n"
        f"Vencimento: {due}\n"
        f"Orientação de tom: {tone_hint}\n"
        f"Não invente taxas, boletos ou links. Não use jargão técnico. "
        f"Termine com um próximo passo claro (ex.: confirmar Pix ou responder esta mensagem)."
    )
    rows=(await db.execute(select(KnowledgeChunk,KnowledgeDocument.title).join(KnowledgeDocument,KnowledgeDocument.id==KnowledgeChunk.document_id).where(KnowledgeChunk.organization_id==p.organization_id))).all()
    sources=retrieve(f"cobrança {item.customer_name} {item.description}",list(rows),3)
    message,mode=await _org_llm_answer(p.organization_id,agent,prompt,sources,db)
    now=datetime.now(UTC)
    if existing:
        task=existing
        task.status="completed";task.agent_id=agent.id;task.completed_at=now;task.started_at=task.started_at or now
        task.result_data={"message":message,"mode":mode,"tone":tone_key,"amount_cents":item.amount_cents,"due_date":str(item.due_date)}
        task.error=None
    else:
        task=AgentTask(
            organization_id=p.organization_id,
            agent_id=agent.id,
            created_by=p.user_id,
            idempotency_key=idem,
            task_type="finance.follow_up",
            title=f"Follow-up: {item.customer_name}"[:180],
            priority="high" if tone_key in {"overdue_soft","negotiate"} else "normal",
            status="completed",
            input_data={"receivable_id":str(item.id),"customer_name":item.customer_name,"amount_cents":item.amount_cents,"due_date":str(item.due_date),"tone":tone_key},
            result_data={"message":message,"mode":mode,"tone":tone_key,"amount_cents":item.amount_cents,"due_date":str(item.due_date)},
            started_at=now,
            completed_at=now,
        )
        db.add(task)
    db.add(AuditLog(organization_id=p.organization_id,user_id=p.user_id,action="finance.follow_up_drafted",resource="receivable",detail=f"{item.customer_name}:{tone_key}"))
    await db.flush()
    return {"task_id":str(task.id),"receivable_id":str(item.id),"tone":tone_key,"message":message,"mode":mode,"reused":False}

@router.post("/finance/receivables",status_code=201)
async def create_receivable(data:ReceivableIn,p:Annotated[Principal,Depends(require_roles(Role.OWNER,Role.ADMIN,Role.MANAGER))],db:Db):
    await require_billing_access(p.organization_id,db)
    contact_uuid=None
    if data.contact_id:
        contact_uuid=parse_uuid(data.contact_id,"Contact")
        if not await db.scalar(select(Contact.id).where(and_(Contact.id==contact_uuid,Contact.organization_id==p.organization_id))):raise HTTPException(404,"Contact not found")
    elif data.phone and data.phone.strip():
        contact=await _upsert_contact_by_phone(p.organization_id,data.customer_name,data.phone,db)
        contact_uuid=contact.id
    item=Receivable(
        organization_id=p.organization_id,
        created_by=p.user_id,
        contact_id=contact_uuid,
        customer_name=data.customer_name,
        description=data.description,
        amount_cents=data.amount_cents,
        due_date=data.due_date,
    )
    db.add(item);await db.flush()
    agent=await _ensure_finance_agent(p.organization_id,p.user_id,db)
    db.add_all([
        AgentTask(organization_id=p.organization_id,agent_id=agent.id,created_by=p.user_id,task_type="finance.follow_up",title=f"Acompanhar recebimento: {data.customer_name}",priority="normal",status="queued",input_data={"receivable_id":str(item.id),"amount_cents":data.amount_cents,"due_date":str(data.due_date)}),
        AuditLog(organization_id=p.organization_id,user_id=p.user_id,action="receivable.created",resource="receivable",detail=data.customer_name),
    ])
    await db.commit();await db.refresh(item)
    return {"id":str(item.id),"status":item.status,"contact_id":str(item.contact_id) if item.contact_id else None}

@router.post("/finance/receivables/{receivable_id}/follow-up",status_code=201)
async def receivable_follow_up(receivable_id:str,p:Annotated[Principal,Depends(require_roles(Role.OWNER,Role.ADMIN,Role.MANAGER,Role.OPERATOR))],db:Db):
    await require_billing_access(p.organization_id,db)
    item=await db.scalar(select(Receivable).where(and_(Receivable.id==parse_uuid(receivable_id,"Receivable"),Receivable.organization_id==p.organization_id)))
    if not item:raise HTTPException(404,"Receivable not found")
    if item.status=="paid":raise HTTPException(409,"Cobrança já está paga")
    agent=await _ensure_finance_agent(p.organization_id,p.user_id,db)
    result=await _generate_finance_follow_up(item,agent,p,db,force=True)
    await db.commit()
    return result

@router.post("/finance/receivables/{receivable_id}/follow-up/send",status_code=201)
async def send_receivable_follow_up(receivable_id:str,data:FinanceSendIn,p:Annotated[Principal,Depends(require_roles(Role.OWNER,Role.ADMIN,Role.MANAGER,Role.OPERATOR))],db:Db):
    """Gera (se preciso) e envia o lembrete pelo WhatsApp Meta/Evolution."""
    await require_billing_access(p.organization_id,db)
    item=await db.scalar(select(Receivable).where(and_(Receivable.id==parse_uuid(receivable_id,"Receivable"),Receivable.organization_id==p.organization_id)))
    if not item:raise HTTPException(404,"Receivable not found")
    if item.status=="paid":raise HTTPException(409,"Cobrança já está paga")
    contact=None
    if item.contact_id:
        contact=await db.scalar(select(Contact).where(and_(Contact.id==item.contact_id,Contact.organization_id==p.organization_id)))
    phone_raw=(data.phone or (contact.phone if contact else "") or "").strip()
    if not phone_raw:
        raise HTTPException(422,"Informe o WhatsApp do cliente (DDI+DDD+número) para enviar.")
    contact=await _upsert_contact_by_phone(p.organization_id,item.customer_name,phone_raw,db)
    item.contact_id=contact.id
    agent=await _ensure_finance_agent(p.organization_id,p.user_id,db)
    if data.message and data.message.strip():
        draft={"message":data.message.strip(),"tone":_finance_follow_tone(item)[0],"mode":"manual","task_id":None,"receivable_id":str(item.id),"reused":False}
    else:
        draft=await _generate_finance_follow_up(item,agent,p,db,force=False)
    text=str(draft.get("message") or "").strip()
    if len(text)<5:raise HTTPException(422,"Mensagem de follow-up vazia")
    channel=await _pick_whatsapp_channel(p.organization_id,db)
    status="sent";error=None
    try:
        await _dispatch_whatsapp(channel,contact.phone,text)
    except HTTPException:
        raise
    except Exception as exc:
        status="failed";error=str(exc)[:300]
    thread=await _record_outbound_whatsapp(p.organization_id,channel,contact,text,status,db)
    db.add(AuditLog(
        organization_id=p.organization_id,user_id=p.user_id,
        action="finance.follow_up_sent" if status=="sent" else "finance.follow_up_failed",
        resource="receivable",
        detail=f"{item.customer_name}:{channel.provider}:{contact.phone}",
    ))
    await db.commit()
    if status!="sent":
        raise HTTPException(502,f"Falha ao enviar no WhatsApp ({channel.provider}): {error}")
    return {
        **draft,
        "sent":True,
        "provider":channel.provider,
        "phone":contact.phone,
        "channel_id":str(channel.id),
        "thread_id":str(thread.id),
        "inbox_path":"/app/inbox",
    }

@router.post("/finance/follow-ups/run")
async def run_finance_follow_ups(p:Annotated[Principal,Depends(require_roles(Role.OWNER,Role.ADMIN,Role.MANAGER))],db:Db):
    """Gera rascunhos de cobrança para títulos vencidos ou que vencem em até 3 dias."""
    await require_billing_access(p.organization_id,db)
    agent=await _ensure_finance_agent(p.organization_id,p.user_id,db)
    horizon=date.today()+timedelta(days=3)
    rows=(await db.scalars(select(Receivable).where(and_(Receivable.organization_id==p.organization_id,Receivable.status=="pending",Receivable.due_date<=horizon)).order_by(Receivable.due_date.asc()))).all()
    drafted=[];skipped=0
    for item in rows[:20]:
        try:
            result=await _generate_finance_follow_up(item,agent,p,db,force=False)
            drafted.append(result)
        except Exception:
            skipped+=1
    await db.commit()
    return {"drafted":len(drafted),"skipped":skipped,"items":drafted}

@router.get("/finance/follow-ups")
async def list_finance_follow_ups(p:Annotated[Principal,Depends(current_principal)],db:Db):
    rows=(await db.scalars(select(AgentTask).where(and_(AgentTask.organization_id==p.organization_id,AgentTask.task_type=="finance.follow_up",AgentTask.status=="completed")).order_by(AgentTask.completed_at.desc()).limit(30))).all()
    out=[]
    for t in rows:
        rd=t.result_data or {}
        inp=t.input_data or {}
        if not rd.get("message"):continue
        out.append({
            "id":str(t.id),
            "title":t.title,
            "tone":rd.get("tone") or inp.get("tone"),
            "message":rd.get("message"),
            "mode":rd.get("mode"),
            "receivable_id":inp.get("receivable_id"),
            "customer_name":inp.get("customer_name"),
            "amount_cents":rd.get("amount_cents") or inp.get("amount_cents"),
            "due_date":rd.get("due_date") or inp.get("due_date"),
            "created_at":(t.completed_at or t.created_at).isoformat() if (t.completed_at or t.created_at) else None,
        })
    return out

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

@router.post("/marketing/campaigns/{campaign_id}/request-spend",status_code=201)
async def campaign_request_spend(campaign_id:str,data:CampaignSpendRequestIn,p:Annotated[Principal,Depends(require_roles(Role.OWNER,Role.ADMIN,Role.MANAGER))],db:Db):
    """Pede verba de anúncio a partir de uma campanha google_ads/meta_ads (usa teto de governança)."""
    await require_billing_access(p.organization_id,db)
    item=await db.scalar(select(MarketingCampaign).where(and_(MarketingCampaign.id==parse_uuid(campaign_id,"Campaign"),MarketingCampaign.organization_id==p.organization_id)))
    if not item:raise HTTPException(404,"Campaign not found")
    if item.channel not in {"google_ads","meta_ads"}:
        raise HTTPException(409,"Só campanhas de Ads (Google/Meta) pedem verba por aqui")
    gov=await _get_or_create_governance(p.organization_id,p.user_id,db)
    remaining=max(0,gov.monthly_ad_ceiling_cents-gov.spent_cents)
    needs_approval=data.amount_cents>remaining
    status="pending" if needs_approval else "approved"
    desc=(data.description or f"Verba para campanha: {item.name}")[:240]
    req=MarketingSpendRequest(
        organization_id=p.organization_id,created_by=p.user_id,
        channel=item.channel,description=desc,amount_cents=data.amount_cents,status=status,
    )
    if status=="approved":
        gov.spent_cents=int(gov.spent_cents)+data.amount_cents
        req.reviewed_by=p.user_id;req.reviewed_at=datetime.now(UTC)
    db.add(req)
    db.add(AuditLog(organization_id=p.organization_id,user_id=p.user_id,action="marketing.spend_requested",resource="marketing_spend",detail=f"{status}:{data.amount_cents}:{item.id}"))
    await db.commit();await db.refresh(req)
    return {
        "id":str(req.id),
        "status":req.status,
        "needs_owner_approval":needs_approval,
        "remaining_cents":max(0,gov.monthly_ad_ceiling_cents-gov.spent_cents),
        "campaign_id":str(item.id),
        "governance_path":"/app/marketing",
    }

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
        "1. Título | canal(social|email|whatsapp|google_ads) | público | texto com CTA\n"
        "2. ...\n3. ...\n4. ...\n"
        "Se houver orçamento mensal > 0 na descoberta, inclua no máximo 1 peça google_ads (texto de anúncio de busca: título + descrição + CTA). "
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
                        ch=_normalize_campaign_channel(bits[1])
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

@router.post("/marketing/playbook/posts/{post_index}/regenerate")
async def regenerate_marketing_post(post_index:int,p:Annotated[Principal,Depends(require_roles(Role.OWNER,Role.ADMIN,Role.MANAGER))],db:Db):
    """Reescreve uma única peça com IA, mantendo as demais."""
    await require_billing_access(p.organization_id,db)
    if post_index<0:raise HTTPException(422,"Índice inválido")
    item=await _get_or_create_playbook(p,db)
    posts=list(item.posts or [])
    if post_index>=len(posts):raise HTTPException(404,"Peça não encontrada")
    if not item.diagnosis or not item.discovery:raise HTTPException(409,"Diagnóstico e descoberta são obrigatórios")
    current=posts[post_index] if isinstance(posts[post_index],dict) else {}
    agent=await _ensure_marketing_agent(p.organization_id,p.user_id,db)
    item.agent_id=agent.id
    rows=(await db.execute(select(KnowledgeChunk,KnowledgeDocument.title).join(KnowledgeDocument,KnowledgeDocument.id==KnowledgeChunk.document_id).where(KnowledgeChunk.organization_id==p.organization_id))).all()
    sources=retrieve(f"peça marketing {current.get('title','')}",list(rows),4) if rows else []
    ch=str(current.get("channel") or "social")
    question=(
        "Reescreva UMA peça de marketing em português brasileiro. "
        "Mantenha o canal e o público, melhore clareza e CTA qualificável.\n"
        "Responda em UMA linha no formato:\n"
        "Título | canal | público | texto com CTA\n"
        f"Canal desejado: {ch}\n"
        f"Peça atual: {current}\n\n"
        f"DIAGNÓSTICO:\n{item.diagnosis}\n\nDESCOBERTA:\n{item.discovery}"
    )
    answer,mode=await _org_llm_answer(p.organization_id,agent,question,sources,db)
    updated={
        "title":str(current.get("title") or "Peça")[:180],
        "channel":_normalize_campaign_channel(ch),
        "audience":str(current.get("audience") or "público-alvo")[:240],
        "content":str(current.get("content") or "")[:12000],
    }
    line=next((ln.strip() for ln in answer.splitlines() if "|" in ln),answer.strip())
    if "|" in line:
        bits=[b.strip() for b in line.split("|")]
        if len(bits)>=4:
            updated={
                "title":bits[0][:180] or updated["title"],
                "channel":_normalize_campaign_channel(bits[1] or ch),
                "audience":bits[2][:240] or updated["audience"],
                "content":"|".join(bits[3:])[:12000] or updated["content"],
            }
        elif mode.startswith("byok") and answer.strip():
            updated["content"]=answer.strip()[:12000]
    elif mode.startswith("byok") and answer.strip():
        updated["content"]=answer.strip()[:12000]
    posts[post_index]=updated
    item.posts=posts
    item.updated_at=datetime.now(UTC)
    db.add(AuditLog(organization_id=p.organization_id,user_id=p.user_id,action="marketing.post_regenerated",resource="marketing_playbook",detail=f"{post_index}:{updated['title']}"))
    await db.commit();await db.refresh(item)
    return {"index":post_index,"post":updated,"playbook":_playbook_out(item),"mode":mode}

@router.post("/marketing/playbook/materialize")
async def materialize_marketing_posts(p:Annotated[Principal,Depends(require_roles(Role.OWNER,Role.ADMIN,Role.MANAGER))],db:Db):
    await require_billing_access(p.organization_id,db)
    item=await _get_or_create_playbook(p,db)
    if not item.posts:raise HTTPException(409,"Gere o plano antes de criar campanhas")
    created=[]
    for post in item.posts:
        ch=_normalize_campaign_channel(post.get("channel") or "social")
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

def _normalize_campaign_channel(raw:str)->str:
    ch=(raw or "social").lower().strip()
    if ch in {"google_ads","meta_ads","whatsapp","email","social"}:return ch
    if "google" in ch:return "google_ads"
    if ("meta" in ch or "facebook" in ch) and ("ads" in ch or "anúncio" in ch or "anuncio" in ch):return "meta_ads"
    if "ads" in ch or "anúncio" in ch or "anuncio" in ch:return "google_ads"
    if "whatsapp" in ch:return "whatsapp"
    if "email" in ch or "e-mail" in ch:return "email"
    return "social"

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
        source_title=data.source_title[:180],
        source_channel=data.source_channel,
        source_campaign_id=campaign_uuid,
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

def _inbox_status_label(detail:str)->str:
    map_={ "open":"IA","human":"humano","closed":"encerrada" }
    parts=detail.split(":")
    if len(parts)>=3:
        return f"{map_.get(parts[-2],parts[-2])} → {map_.get(parts[-1],parts[-1])}"
    if len(parts)==1:
        return map_.get(parts[0],parts[0])
    return detail

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
        "opportunity.stage_changed":("Etapa do CRM atualizada",d.replace(":"," → ") if d else "Kanban"),
        "opportunity.updated":("Oportunidade editada no CRM",d or "Dados atualizados"),
        "opportunity.deleted":("Oportunidade removida do CRM",d or "Removida"),
        "agent.created":("Agente adicionado à equipe",d or "Novo agente"),
        "agent.status_changed":("Status de agente atualizado",d.replace(":"," → ") if d else "Alteração de status"),
        "agent.queried":("Consulta a um agente",d or "Pergunta respondida"),
        "auth.password_reset_requested":("Recuperação de senha solicitada",d or "Pedido"),
        "auth.password_reset":("Senha redefinida",d or "Nova senha"),
        "team.password_reset":("Senha temporária gerada na Equipe",d or "Membro"),
        "knowledge.ingested":("Conteúdo publicado na base",d.split(":")[0] if d else "Novo documento"),
        "settings.llm_updated":("Inteligência (IA) conectada",d or "Chave atualizada"),
        "settings.brand_kit_updated":("Kit de marca atualizado",d or "Identidade da empresa"),
        "receivable.created":("Cobrança lançada",d or "Novo recebível"),
        "receivable.paid":("Pagamento recebido",money_hint or d or "Recebimento confirmado"),
        "finance.follow_up_drafted":("Lembrete de cobrança preparado",d or "Follow-up"),
        "finance.follow_up_sent":("Lembrete enviado no WhatsApp",d or "Cobrança"),
        "finance.follow_up_failed":("Falha ao enviar cobrança no WhatsApp",d or "Cobrança"),
        "campaign.created":("Campanha criada",d or "Nova campanha"),
        "campaign.status_changed":("Campanha atualizada",d.replace(":"," → ") if d else "Status alterado"),
        "message.sent":("Mensagem enviada no WhatsApp",d or "Envio"),
        "message.received":("Mensagem recebida no WhatsApp",d or "Entrada"),
        "inbox.thread_status":("Conversa WhatsApp atualizada",_inbox_status_label(d) if d else "Status"),
        "message.template_sent":("Template WhatsApp enviado",d or "Meta"),
        "message.template_failed":("Falha ao enviar template WhatsApp",d or "Meta"),
        "marketing.diagnosis_saved":("Marketing: diagnóstico salvo","Playbook Essencial"),
        "marketing.discovery_saved":("Marketing: descoberta salva","Playbook Essencial"),
        "marketing.plan_generated":("Plano de Marketing gerado",d or "Plano Essencial"),
        "marketing.posts_materialized":("Peças publicadas como campanhas",f"{d} peça(s)" if d else "Campanhas criadas"),
        "marketing.post_regenerated":("Peça de marketing reescrita com IA",d or "Regeneração"),
        "marketing.lead_handed_off":("Interesse virando oportunidade",d or "Handoff comercial"),
        "marketing.crisis_escalated":("Crise de marketing escalada",d or "Atenção necessária"),
        "marketing.governance_updated":("Governança de marketing atualizada","Teto e regras"),
        "marketing.spend_requested":("Pedido de verba de anúncio",d or "Aguardando aprovação"),
        "marketing.spend_reviewed":("Verba de anúncio revisada",d or "Decisão registrada"),
        "marketing.engagement_logged":("Engajamento registrado",d or "Métrica"),
        "marketing.package_upgraded":("Pacote de Marketing atualizado",d or "Upgrade"),
        "channel.meta_connected":("WhatsApp oficial (Meta) conectado",d or "Cloud API"),
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

@router.post("/team/members/{membership_id}/reset-password")
async def reset_team_member_password(membership_id:str,p:Annotated[Principal,Depends(require_roles(Role.OWNER,Role.ADMIN))],db:Db):
    """Admin gera senha temporária (mostrada uma vez) para o membro."""
    await require_billing_access(p.organization_id,db)
    item=await db.scalar(select(Membership).where(and_(Membership.id==parse_uuid(membership_id,"Membership"),Membership.organization_id==p.organization_id)))
    if not item:raise HTTPException(404,"Membership not found")
    if item.role==Role.OWNER and p.role!=Role.OWNER:raise HTTPException(403,"Only owners can reset owner passwords")
    user=await db.scalar(select(User).where(User.id==item.user_id))
    if not user:raise HTTPException(404,"User not found")
    temp=secrets.token_urlsafe(10)
    user.password_hash=hash_password(temp)
    sessions=(await db.scalars(select(RefreshSession).where(and_(RefreshSession.user_id==user.id,RefreshSession.revoked_at.is_(None))))).all()
    now=datetime.now(UTC)
    for s in sessions:
        s.revoked_at=now
    db.add(AuditLog(organization_id=p.organization_id,user_id=p.user_id,action="team.password_reset",resource="membership",detail=user.email))
    await db.commit()
    return {"membership_id":str(item.id),"email":user.email,"temporary_password":temp,"message":"Senha temporária gerada. Copie agora — não será mostrada de novo."}

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
