"""Clay webhook import logic with rate limiting."""

import os
import time
import json
import logging
from urllib.request import Request, urlopen
from urllib.error import URLError

from db import get_db

logger = logging.getLogger(__name__)

CLAY_WEBHOOK_URL = os.environ.get("CLAY_WEBHOOK_URL", "")
RATE_LIMIT_PER_SEC = 8


def import_accounts_to_clay(campaign_id: str) -> dict:
    """Push campaign accounts to Clay webhook. Rate-limited at ~8/sec.

    Returns summary dict with sent/failed counts.
    """
    if not CLAY_WEBHOOK_URL:
        raise ValueError("CLAY_WEBHOOK_URL environment variable not set")

    with get_db() as conn:
        cur = conn.cursor()

        # Get pending accounts
        cur.execute(
            "SELECT id, account_name, domain, account_id "
            "FROM campaign_accounts "
            "WHERE campaign_id = %s AND clay_import_status = 'pending' "
            "ORDER BY id",
            (campaign_id,),
        )
        accounts = cur.fetchall()

        if not accounts:
            return {"sent": 0, "failed": 0, "message": "No pending accounts"}

        # Update campaign status
        cur.execute(
            "UPDATE campaigns SET status = 'importing', updated_at = NOW() "
            "WHERE id = %s",
            (campaign_id,),
        )

        sent = 0
        failed = 0
        batch_start = time.time()
        batch_count = 0

        for account in accounts:
            # Rate limiting
            batch_count += 1
            if batch_count >= RATE_LIMIT_PER_SEC:
                elapsed = time.time() - batch_start
                if elapsed < 1.0:
                    time.sleep(1.0 - elapsed)
                batch_start = time.time()
                batch_count = 0

            payload = {
                "campaign_id": campaign_id,
                "account_name": account["account_name"],
                "domain": account["domain"] or "",
                "account_id": account["account_id"] or "",
            }

            try:
                data = json.dumps(payload).encode("utf-8")
                req = Request(
                    CLAY_WEBHOOK_URL,
                    data=data,
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                urlopen(req, timeout=10)

                cur.execute(
                    "UPDATE campaign_accounts SET clay_import_status = 'sent' "
                    "WHERE id = %s",
                    (account["id"],),
                )
                sent += 1

            except (URLError, Exception) as e:
                logger.error(f"Failed to send account {account['account_name']}: {e}")
                cur.execute(
                    "UPDATE campaign_accounts SET clay_import_status = 'failed' "
                    "WHERE id = %s",
                    (account["id"],),
                )
                failed += 1

        # Update campaign status to enriching
        cur.execute(
            "UPDATE campaigns SET status = 'enriching', updated_at = NOW() "
            "WHERE id = %s",
            (campaign_id,),
        )

    return {"sent": sent, "failed": failed}
