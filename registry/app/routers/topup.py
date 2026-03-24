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
SUCCESS_URL  = os.getenv("TOPUP_SUCCESS_URL", "https://colabbot.com/?topup=success")
CANCEL_URL   = os.getenv("TOPUP_CANCEL_URL",  "https://colabbot.com/?topup=cancelled")
CBT_PER_USD  = float(os.getenv("CBT_PER_USD", "10"))


# ---------------------------------------------------------------------------
# Founder Backer Packages
# ~70% off future regular pricing — see TOKENOMICS.md for rationale
# ---------------------------------------------------------------------------

PACKAGES = [
    {"id": "explorer",  "cbt": 500,   "usd_cents": 499,   "label": "Explorer",      "popular": False},
    {"id": "builder",   "cbt": 2000,  "usd_cents": 1499,  "label": "Builder",       "popular": True},
    {"id": "operator",  "cbt": 10000, "usd_cents": 4999,  "label": "Operator",      "popular": False},
    {"id": "founding",  "cbt": 50000, "usd_cents": 19999, "label": "Founding Node", "popular": False},
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
    agent_id: str | None = Field(
        default=None,
        description="Optional: existing agent ID to credit CBT to immediately. "
                    "If omitted, CBT is held as a pending balance until agent registers.",
    )


@router.post("/checkout", status_code=status.HTTP_201_CREATED)
def create_checkout(
    body: CheckoutRequest,
    db: Session = Depends(get_db),
):
    """
    Create a Stripe Checkout session. No authentication required — open to founders
    and backers who may not yet have a registered agent.
    """
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

    agent_id = body.agent_id or "pending"
    description = (
        f"{pkg['cbt']} CBT credited to agent {agent_id}"
        if agent_id != "pending"
        else f"{pkg['cbt']} CBT — will be credited when you register your agent"
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
                            "name": f"ColabToken (CBT) — {pkg['label']} Founder Pack",
                            "description": description,
                        },
                    },
                    "quantity": 1,
                }
            ],
            metadata={
                "agent_id": agent_id,
                "cbt_amount": str(pkg["cbt"]),
                "package_id": pkg["id"],
            },
            success_url=SUCCESS_URL + f"&agent={agent_id}&cbt={pkg['cbt']}",
            cancel_url=CANCEL_URL,
        )
    except stripe.StripeError as e:
        log.error("Stripe error for agent %s: %s", agent_id, e)
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

        if agent_id == "pending":
            # Founder backer without an agent yet — store as pending transaction.
            # CBT will be credited when the backer registers their agent and claims
            # the balance via POST /v1/topup/claim (to be implemented).
            tx = CBTTransaction(
                agent_id="pending",
                amount=cbt_amount,
                task_id=None,
                type="topup_pending",
                stripe_session_id=session.get("id"),
            )
            db.add(tx)
            db.commit()
            log.info("Pending top-up: %s CBT, session %s (no agent yet)", cbt_amount, session.get("id"))
            return {"ok": True}

        agent = db.query(Agent).filter(Agent.agent_id == agent_id).first()
        if not agent:
            # Agent ID provided but not found — store as pending so CBT is not lost
            tx = CBTTransaction(
                agent_id=agent_id,
                amount=cbt_amount,
                task_id=None,
                type="topup_pending",
                stripe_session_id=session.get("id"),
            )
            db.add(tx)
            db.commit()
            log.warning("Webhook: agent %s not found, stored as pending top-up", agent_id)
            return {"ok": True}

        agent.cbt_balance += cbt_amount
        tx = CBTTransaction(
            agent_id=agent_id,
            amount=cbt_amount,
            task_id=None,
            type="topup",
            stripe_session_id=session.get("id"),
        )
        db.add(tx)
        db.commit()
        log.info("Topped up %s CBT for agent %s (session %s)", cbt_amount, agent_id, session.get("id"))

    return {"ok": True}
