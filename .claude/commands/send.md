---
description: Send matched leads CSV to Clay webhook for enrichment and Salesforce push
allowed-tools: Read, Write, Bash, Glob, AskUserQuestion
---

# Send Leads to Clay

Push the final capped leads CSV to Clay for downstream enrichment (work email, phone) and Salesforce push.

**Input:** `$ARGUMENTS` — optional path to a CSV file or campaign folder.

**Clay webhook URL (hardcoded):**
`https://api.clay.com/v3/sources/webhook/pull-in-data-from-a-webhook-e03f2137-6d54-40af-a702-83d656f03729`

---

## Phase 0: Intake

### Step 1: Determine target file

If `$ARGUMENTS` is a direct path to a `.csv` file — use that file. Skip to Phase 1.

If `$ARGUMENTS` is a campaign folder path — look for files inside it and go to Step 2.

If no argument provided:
1. List campaign folders: `ls ~/sitemapping/`
2. Use AskUserQuestion: **"Which campaign do you want to send leads for?"** — show the folder names as options.

### Step 2: Choose file within campaign folder

List the available output files in the campaign folder. Show only files that exist:
- `People List - Matched Leads (New) - Capped.csv` ← **recommended**
- `People List - Matched Leads (New) - ATL.csv` ← also accepted (legacy name)
- `People List - Matched Leads (New).csv` ← uncapped version

Use AskUserQuestion: **"Which file do you want to send to Clay?"**
- **"Capped list (recommended)"** — `People List - Matched Leads (New) - Capped.csv`
- **"Uncapped list"** — `People List - Matched Leads (New).csv`

---

## Phase 1: Preview

Read the chosen CSV (utf-8-sig encoding). Count the rows and columns.

Display a preview summary like:

```
File: People List - Matched Leads (New) - Capped.csv
Rows: 247 leads
Columns: 26 (all columns will be sent)

Sample (first 3 rows):
#1 John Doe — Plant Manager — Ford Motor Company — Phoenix, AZ → Phoenix Assembly Plant
#2 Jane Smith — Director, Engineering — Ford Motor Company — Chicago, IL → Chicago Stamping Plant
#3 ...

Destination: Clay webhook (Salesforce enrichment pipeline)
```

For each sample row, pull: `Full Name` (or `First Name` + `Last Name`), `Title`, `Account Name`, `City` + `State`, `Matched Location Name`.

Then ask:

Use AskUserQuestion: **"Send [N] rows to Clay?"**
- **"Yes, send now"**
- **"No, cancel"**

If "No" → print: "Send cancelled. Run `/send` again when ready." and exit.

---

## Phase 2: Send

Write the following Python script to `/tmp/clay_send.py`, then execute it with the CSV path as argument:

```python
import csv, json, urllib.request, time, sys

WEBHOOK_URL = "https://api.clay.com/v3/sources/webhook/pull-in-data-from-a-webhook-e03f2137-6d54-40af-a702-83d656f03729"
RATE_LIMIT = 8  # requests per second

with open(sys.argv[1], newline='', encoding='utf-8-sig') as f:
    reader = csv.DictReader(f)
    rows = list(reader)

total = len(rows)
sent, failed = 0, []
batch_start = time.time()
batch_count = 0

for i, row in enumerate(rows):
    payload = json.dumps(row).encode('utf-8')
    req = urllib.request.Request(
        WEBHOOK_URL,
        data=payload,
        headers={'Content-Type': 'application/json'}
    )
    try:
        urllib.request.urlopen(req, timeout=10)
        sent += 1
    except Exception as e:
        time.sleep(2)
        try:
            urllib.request.urlopen(req, timeout=10)
            sent += 1
        except Exception as e2:
            name = row.get('Full Name') or f"{row.get('First Name', '')} {row.get('Last Name', '')}".strip() or f"row {i+1}"
            account = row.get('Account Name', '')
            failed.append(f"{name} ({account})")

    batch_count += 1
    if batch_count >= RATE_LIMIT:
        elapsed = time.time() - batch_start
        if elapsed < 1.0:
            time.sleep(1.0 - elapsed)
        batch_start = time.time()
        batch_count = 0

    if (i + 1) % 10 == 0 or (i + 1) == total:
        pct = int((i + 1) / total * 100)
        print(f"Sending row {i+1} of {total}... ({pct}%)", flush=True)

print(f"DONE|{sent}|{';;'.join(failed)}")
```

Execute with:
```bash
python3 /tmp/clay_send.py "<path-to-csv>"
```

Stream the output live so the user sees progress as it runs.

Parse the final `DONE|<sent>|<failed>` line to extract counts.

---

## Phase 3: Summary

Print the final summary:

```
Send Complete!

Total rows:   247
Sent:         245
Failed:         2

Clay will now:
  1. Format Division/Site Name from matched location fields
  2. Enrich for work email + phone number (via Surfe/Kaspr)
  3. Push enriched records to Salesforce
```

If there were failures, list them:

```
Failed rows:
  - Jane Smith (Ford Motor Company) — retried and skipped
  - John Doe (Eaton Corporation) — retried and skipped
```

If all rows sent successfully:
```
All rows sent successfully.
```
