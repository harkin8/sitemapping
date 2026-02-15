"""Pipeline API — FastAPI service for the account targeting pipeline.

Endpoints:
  POST   /campaigns                     Create campaign with accounts
  POST   /campaigns/{id}/import-to-clay Push accounts to Clay webhook
  POST   /webhook/clay                  Receive enriched person from Clay
  GET    /campaigns/{id}/status          Campaign progress & stability check
  GET    /campaigns/{id}/export          Download enriched people as CSV
  GET    /health                         Health check
"""

import json
import logging
import re
from datetime import date
from threading import Thread

from fastapi import FastAPI, HTTPException
from fastapi.responses import PlainTextResponse, Response

from models import CampaignCreate, CampaignOut, CampaignStatus, ClayWebhookPayload
from db import get_db, init_db
from clay_client import import_accounts_to_clay
from csv_export import export_campaign_csv

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Pipeline API", version="1.0.0")

# In-memory stability tracker: campaign_id -> list of recent counts
_stability_history: dict[str, list[int]] = {}


@app.on_event("startup")
def startup():
    try:
        init_db()
        logger.info("Database initialized")
    except Exception as e:
        logger.error(f"Database init failed (will retry on first request): {e}")


@app.get("/health")
def health():
    """Health check — always returns ok so Railway doesn't kill the container.
    Database connectivity is checked separately by the endpoints that need it."""
    return {"status": "ok"}


# ---------- POST /campaigns ----------

@app.post("/campaigns", response_model=CampaignOut)
def create_campaign(body: CampaignCreate):
    """Create a new campaign and store its accounts."""
    # Generate campaign ID: YYYY-MM-DD_slugified-name
    slug = re.sub(r"[^a-z0-9]+", "-", body.name.lower()).strip("-")
    campaign_id = f"{date.today().isoformat()}_{slug}"

    with get_db() as conn:
        cur = conn.cursor()

        # Check if campaign already exists
        cur.execute("SELECT id FROM campaigns WHERE id = %s", (campaign_id,))
        if cur.fetchone():
            raise HTTPException(409, f"Campaign '{campaign_id}' already exists")

        cur.execute(
            "INSERT INTO campaigns (id, name, created_by) VALUES (%s, %s, %s)",
            (campaign_id, body.name, body.created_by),
        )

        for acct in body.accounts:
            cur.execute(
                "INSERT INTO campaign_accounts "
                "(campaign_id, account_name, domain, account_id) "
                "VALUES (%s, %s, %s, %s)",
                (campaign_id, acct.account_name, acct.domain, acct.account_id),
            )

    return CampaignOut(
        id=campaign_id,
        name=body.name,
        status="created",
        created_by=body.created_by,
        account_count=len(body.accounts),
    )


# ---------- POST /campaigns/{id}/import-to-clay ----------

@app.post("/campaigns/{campaign_id}/import-to-clay")
def import_to_clay(campaign_id: str):
    """Push pending accounts to Clay webhook (runs in background thread)."""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT id FROM campaigns WHERE id = %s", (campaign_id,))
        if not cur.fetchone():
            raise HTTPException(404, "Campaign not found")

    # Run import in background so the request returns fast
    def _run():
        try:
            result = import_accounts_to_clay(campaign_id)
            logger.info(f"Clay import done for {campaign_id}: {result}")
        except Exception as e:
            logger.error(f"Clay import failed for {campaign_id}: {e}")

    thread = Thread(target=_run, daemon=True)
    thread.start()

    return {"message": "Import started", "campaign_id": campaign_id}


# ---------- POST /webhook/clay ----------

@app.post("/webhook/clay")
def clay_webhook(payload: ClayWebhookPayload):
    """Receive enriched person data from Clay's HTTP Action column."""
    with get_db() as conn:
        cur = conn.cursor()

        # Verify campaign exists
        cur.execute("SELECT id FROM campaigns WHERE id = %s", (payload.campaign_id,))
        if not cur.fetchone():
            raise HTTPException(404, f"Campaign '{payload.campaign_id}' not found")

        cur.execute(
            "INSERT INTO enriched_people "
            "(campaign_id, account_name, account_id, first_name, last_name, "
            "full_name, job_title, persona, persona_score, company_domain, domain, "
            "linkedin_profile, enrich_person, final_location, raw_payload) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (
                payload.campaign_id,
                payload.account_name,
                payload.account_id,
                payload.first_name,
                payload.last_name,
                payload.full_name,
                payload.job_title,
                payload.persona,
                payload.persona_score,
                payload.company_domain,
                payload.domain,
                payload.linkedin_profile,
                payload.enrich_person,
                payload.final_location,
                json.dumps(payload.model_dump()),
            ),
        )

        # Update campaign status to enriching if not already
        cur.execute(
            "UPDATE campaigns SET status = 'enriching', updated_at = NOW() "
            "WHERE id = %s AND status != 'ready'",
            (payload.campaign_id,),
        )

    return {"status": "received"}


# ---------- GET /campaigns/{id}/status ----------

@app.get("/campaigns/{campaign_id}/status", response_model=CampaignStatus)
def campaign_status(campaign_id: str):
    """Return campaign progress. Tracks stability (3 polls with no change)."""
    with get_db() as conn:
        cur = conn.cursor()

        cur.execute(
            "SELECT id, name, status FROM campaigns WHERE id = %s",
            (campaign_id,),
        )
        campaign = cur.fetchone()
        if not campaign:
            raise HTTPException(404, "Campaign not found")

        cur.execute(
            "SELECT COUNT(*) as cnt FROM campaign_accounts WHERE campaign_id = %s",
            (campaign_id,),
        )
        account_count = cur.fetchone()["cnt"]

        cur.execute(
            "SELECT COUNT(*) as cnt FROM campaign_accounts "
            "WHERE campaign_id = %s AND clay_import_status = 'sent'",
            (campaign_id,),
        )
        accounts_sent = cur.fetchone()["cnt"]

        cur.execute(
            "SELECT COUNT(*) as cnt FROM enriched_people WHERE campaign_id = %s",
            (campaign_id,),
        )
        people_count = cur.fetchone()["cnt"]

        # Count how many unique accounts have at least 1 enriched person
        cur.execute(
            "SELECT COUNT(DISTINCT account_name) as cnt FROM enriched_people "
            "WHERE campaign_id = %s",
            (campaign_id,),
        )
        accounts_with_people = cur.fetchone()["cnt"]

    # Stability tracking
    history = _stability_history.setdefault(campaign_id, [])
    history.append(people_count)
    # Keep last 5 polls
    if len(history) > 5:
        history.pop(0)

    # Count is stable if last 3 polls are identical and > 0
    count_stable = (
        len(history) >= 3
        and people_count > 0
        and history[-1] == history[-2] == history[-3]
    )

    # All accounts covered: every sent account has at least 1 person
    all_accounts_covered = (
        accounts_sent > 0
        and accounts_with_people >= accounts_sent
    )

    # Ready when BOTH: all accounts have people AND count has stabilized
    stable = count_stable and all_accounts_covered

    # Auto-update status to ready when stable
    if stable and campaign["status"] == "enriching":
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute(
                "UPDATE campaigns SET status = 'ready', updated_at = NOW() "
                "WHERE id = %s",
                (campaign_id,),
            )
        campaign["status"] = "ready"

    return CampaignStatus(
        id=campaign_id,
        name=campaign["name"],
        status=campaign["status"],
        account_count=account_count,
        accounts_sent=accounts_sent,
        accounts_with_people=accounts_with_people,
        enriched_people_count=people_count,
        stable=stable,
    )


# ---------- GET /campaigns/{id}/export ----------

@app.get("/campaigns/{campaign_id}/export")
def export_campaign(campaign_id: str):
    """Download enriched people as CSV in /mapping format."""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT id FROM campaigns WHERE id = %s", (campaign_id,))
        if not cur.fetchone():
            raise HTTPException(404, "Campaign not found")

    csv_content = export_campaign_csv(campaign_id)

    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="People List.csv"'
        },
    )
