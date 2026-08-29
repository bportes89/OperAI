from datetime import date, timedelta
import uuid
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import get_settings
from app.models import Organization, OrganizationOnboarding, OrganizationSubscription, SaaSPlan

ALLOWED_STATUSES = {"trialing", "active", "paid"}


async def require_billing_access(org_id: uuid.UUID, db: AsyncSession) -> OrganizationSubscription:
    sub = await db.scalar(
        select(OrganizationSubscription).where(OrganizationSubscription.organization_id == org_id)
    )
    if not sub:
        raise HTTPException(402, detail={"access": False, "reason": "subscription_missing"})
    status = (sub.status or "").lower()
    if status == "trialing" and sub.trial_ends_at and sub.trial_ends_at < date.today():
        sub.status = "expired"
        await db.commit()
        raise HTTPException(402, detail={"access": False, "reason": "trial_expired"})
    if status in {"past_due", "canceled", "cancelled", "expired"}:
        raise HTTPException(402, detail={"access": False, "reason": status})
    if status not in ALLOWED_STATUSES:
        raise HTTPException(402, detail={"access": False, "reason": status or "inactive"})
    return sub


async def ensure_subscription_on_register(
    org: Organization,
    db: AsyncSession,
    plan_slug: str = "start",
) -> OrganizationSubscription:
    plan = await db.scalar(select(SaaSPlan).where(SaaSPlan.slug == plan_slug, SaaSPlan.active.is_(True)))
    if not plan:
        plan = await db.scalar(select(SaaSPlan).where(SaaSPlan.slug == "start"))
    if not plan:
        raise HTTPException(500, "SaaS start plan is not configured")
    today = date.today()
    trial_days = get_settings().trial_days
    trial_end = today + timedelta(days=trial_days)
    sub = OrganizationSubscription(
        organization_id=org.id,
        plan_id=plan.id,
        status="trialing",
        current_period_start=today,
        current_period_end=trial_end,
        trial_ends_at=trial_end,
        cancel_at_period_end=False,
    )
    db.add(sub)
    existing_onboarding = await db.scalar(
        select(OrganizationOnboarding).where(OrganizationOnboarding.organization_id == org.id)
    )
    if not existing_onboarding:
        db.add(OrganizationOnboarding(organization_id=org.id, step="welcome", checklist={}))
    await db.flush()
    return sub


def subscription_access_payload(sub: OrganizationSubscription | None, plan: SaaSPlan | None = None) -> dict:
    if not sub:
        return {"access": False, "reason": "subscription_missing", "status": None, "trial_ends_at": None, "plan": None}
    status = (sub.status or "").lower()
    reason = None
    access = True
    if status == "trialing" and sub.trial_ends_at and sub.trial_ends_at < date.today():
        access = False
        reason = "trial_expired"
        status = "expired"
    elif status in {"past_due", "canceled", "cancelled", "expired"}:
        access = False
        reason = status
    elif status not in ALLOWED_STATUSES:
        access = False
        reason = status or "inactive"
    plan_payload = None
    if plan:
        plan_payload = {
            "id": str(plan.id),
            "slug": plan.slug,
            "name": plan.name,
            "price_cents": plan.monthly_price_cents,
            "monthly_price_cents": plan.monthly_price_cents,
            "currency": "BRL",
            "limits": plan.limits or {},
            "features": plan.features if isinstance(plan.features, list) else (
                list(plan.features.keys()) if isinstance(plan.features, dict) else []
            ),
        }
    return {
        "access": access,
        "reason": reason,
        "status": status,
        "plan_slug": plan.slug if plan else None,
        "trial_ends_at": sub.trial_ends_at,
        "current_period_end": sub.current_period_end,
        "cancel_at_period_end": sub.cancel_at_period_end,
        "asaas_subscription_id": sub.asaas_subscription_id,
        "plan": plan_payload,
        "subscription_id": str(sub.id),
    }
