"""CSV column mapping & generation for /mapping format.

Produces CSV matching the exact format of:
~/locations and contacts/People List.csv

Column order:
  "Find people" (empty)
  "Rows from: ..." (empty)
  "Account Name"
  "Account ID"
  "First Name"
  "Last Name"
  "Full Name."      (note trailing dot)
  "Job Title"
  "Persona"
  "Company Domain"
  "Domain"
  "LinkedIn Profile"
  "Enrich person"
  "Final Location"
"""

import csv
import io

from db import get_db

CSV_COLUMNS = [
    "Find people",
    "Rows from: Campaign Export",
    "Account Name",
    "Account ID",
    "First Name",
    "Last Name",
    "Full Name.",
    "Job Title",
    "Persona",
    "Persona Score",
    "Company Domain",
    "Domain",
    "LinkedIn Profile",
    "Enrich person",
    "Final Location",
]


def export_campaign_csv(campaign_id: str) -> str:
    """Generate CSV string for enriched people in a campaign."""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT account_name, account_id, first_name, last_name, "
            "full_name, job_title, persona, persona_score, company_domain, domain, "
            "linkedin_profile, enrich_person, final_location "
            "FROM enriched_people "
            "WHERE campaign_id = %s "
            "ORDER BY account_name, last_name, first_name",
            (campaign_id,),
        )
        rows = cur.fetchall()

    output = io.StringIO()
    writer = csv.writer(output, quoting=csv.QUOTE_ALL)
    writer.writerow(CSV_COLUMNS)

    for row in rows:
        writer.writerow([
            "",  # Find people
            "",  # Rows from
            row["account_name"] or "",
            row["account_id"] or "",
            row["first_name"] or "",
            row["last_name"] or "",
            row["full_name"] or "",
            row["job_title"] or "",
            row["persona"] or "",
            row["persona_score"] or "",
            row["company_domain"] or "",
            row["domain"] or row["company_domain"] or "",  # fallback
            row["linkedin_profile"] or "",
            row["enrich_person"] or row["full_name"] or "",  # fallback
            row["final_location"] or "",
        ])

    return output.getvalue()
