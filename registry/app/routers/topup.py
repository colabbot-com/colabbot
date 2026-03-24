"""
ColabBot Registry — CBT Top-up via Stripe
------------------------------------------
POST /v1/topup/checkout   → Create a Stripe Checkout session
POST /v1/topup/webhook    → Handle Stripe webhook (credits CBT on payment)
GET  /v1/topup/packages   → List available CBT packages (public)
"""

import json
import logging
import os

import stripe
from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..auth import get_current_agent
from ..database import get_db
from ..models import Agent, CBTTransaction

log = logging.getLogger("colabbot.topup")

router = APIRouter(prefix="/topup", tags=["topup"])

stripe.api_key = os.getenv("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")
CBT_PER_USD = float(os.getenv("CBT_PER_USD", "10"))          # 1 USD = 10 CBT
SUCCESS_URL = os.getenv("TOPUP_SUCCESS_URL", "https://colabbot.com/?topup=success")
CANCEL_URL  = os.getenv("TOPUP_CANCEL_URL",  "https://colabbot.com/?topup=cancelled")


# ---------------------------------------------------------------------------
# Packages
# ---------------------------------------------------------------------------

PACKAGES = [
    {"id": "starter",    "cbt": 100,   "usd_cents": 1000,  "label": "Starter",    "popular": False},
    {"id": "builder",    "cbt": 500,   "usd_cents": 4500,  "label": "Builder",    "popular": True},
    {"id": "pro",        "cbt": 1200,  "usd_cents": 9900,  "label": "Pro",        "popular": False},
    {"id": "enterprise", "cbt": 5000,  "usd_cents": 39900, "label": "Enterprise", "popular": False},
]


@router.get("/packages", status_code=status.HTTP_200_OK)
def list_packages():
    """Return available CBT top-up packages. Public endpoint, no auth required."""
    return {
        "cbt_per_usd": CBT_PER_USD,
        "packages": PACKAGES,
    }


# ---------------------------------------------------------------------------
# Create checkout session
# ---------------------------------------------------------------------------

class CheckoutRequest(BaseModel):
    package_id: str = Field(description="Package ID from GET /topup/packages")


@router.post("/checkout", status_code=status.HTTP_201_CREATED)
def create_checkout(
    body: CheckoutRequest,
    db: Session = Depends(get_db),
    current_agent: Agent = Depends(get_current_agent),
):
    if not stripe.api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Stripe is not configured on this instance.",
        )

    pkg = next((p for p in PACKAGES if p["id"] == body.package_id), None)
    if not pkg:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown package '{body.package_id}'. See GET /topup/packages.",
        )

    try:
        session = stripe.checkout.Session.create(
            mode="payment",
            line_items=[
                {
                    "price_data": {
                        "currency": "usd",
                        "unit_amount": pkg["usd_cents"],
                        "product_data": {
                            "name": f"ColabToken (CBT) — {pkg['label']} Pack",
                            "description": f"{pkg['cbt']} CBT credited to agent {current_agent.agent_id}",
                        },
                    },
                    "quantity": 1,
                }
            ],
            metadata={
                "agent_id": current_agent.agent_id,
                "cbt_amount": str(pkg["cbt"]),
                "package_id": pkg["id"],
            },
            success_url=SUCCESS_URL + f"&agent={current_agent.agent_id}&cbt={pkg['cbt']}",
            cancel_url=CANCEL_URL,
        )
    except stripe.StripeError as e:
        log.error("Stripe error for agent %s: %s", current_agent.agent_id, e)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))

    return {
        "checkout_url": session.url,
        "session_id": session.id,
        "cbt_amount": pkg["cbt"],
        "usd_amount": pkg["usd_cents"] / 100,
    }


# ---------------------------------------------------------------------------
# Stripe webhook
# ---------------------------------------------------------------------------

@router.post("/webhook", status_code=status.HTTP_200_OK)
async def stripe_webhook(
    request: Request,
    stripe_signature: str = Header(alias="stripe-signature", default=""),
    db: Session = Depends(get_db),
):
    payload = await request.body()

    # Verify signature in production; skip in dev if secret not set
    if STRIPE_WEBHOOK_SECRET:
        try:
            event = stripe.Webhook.construct_event(payload, stripe_signature, STRIPE_WEBHOOK_SECRET)
        except stripe.SignatureVerificationError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid Stripe signature.")
    else:
        event = json.loads(payload)

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        metadata = session.get("metadata", {})
        agent_id = metadata.get("agent_id")
        cbt_amount = float(metadata.get("cbt_amount", 0))

        if not agent_id or cbt_amount <= 0:
            log.warning("Webhook: missing metadata in session %s", session.get("id"))
            return {"ok": True}

        agent = db.query(Agent).filter(Agent.agent_id == agent_id).first()
        if not agent:
            log.warning("Webhook: agent %s not found", agent_id)
            return {"ok": True}

        agent.cbt_balance += cbt_amount
        tx = CBTTransaction(
            agent_id=agent_id,
            amount=cbt_amount,
            task_id=None,
            type="topup",
        )
        db.add(tx)
        db.commit()
        log.info("Topped up %s CBT for agent %s (session %s)", cbt_amount, agent_id, session.get("id"))

    return {"ok": True}
