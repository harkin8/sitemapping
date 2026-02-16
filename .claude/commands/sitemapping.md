---
description: End-to-end account targeting pipeline — from accounts to Capped List
allowed-tools: Read, Write, Bash, WebSearch, WebFetch, Glob, Grep, AskUserQuestion
---

# End-to-End Account Targeting Pipeline

Orchestrate the full flow: accounts → facility locations → Clay enrichment → people-to-location mapping → Capped List.

**Input:** `$ARGUMENTS`

- If `--resume <campaign-id>` is present, skip to **Resume Mode** at the bottom.
- Otherwise, start at Phase 0.

**API Base URL:** `https://pipeline-api-production-a54c.up.railway.app` — use this for all API calls below.

---

## Phase 0: Intake

### Step 1: Ask how many accounts

Use AskUserQuestion:
- **"How many accounts do you want to map?"**
  - **1 account** — "I'll enter the details manually"
  - **Multiple accounts** — "I'll upload a CSV"

### Step 2a: Single account (if 1)

Ask the user to provide:
- **Account Name** (e.g., "Ford Motor Company")
- **Company Domain** (e.g., "ford.com")
- **Account ID** (e.g., "001Ua00000MMNe4IAH")

Store as a single-item account list.

### Step 2b: Multiple accounts (if CSV)

Ask the user to provide the path to their CSV. Read it — expect columns: `Account Name`, `Domain` (or `Company Domain`), `Account ID`. Parse all rows.

### Step 3: Ask for campaign name

Use AskUserQuestion: "What should we name this campaign?" Suggest a default based on the account name (single) or CSV filename (multiple). This is just for organizing the output folder.

### Step 4: Verify API

1. `curl -s $PIPELINE_API_URL/health` — if it fails, stop and tell the user.
2. Create campaign directory: `~/sitemapping/<campaign-name>/account locations/`

---

## Phase 1: Create Campaign & Extract Locations

### 1a. Create campaign on Railway API

```bash
curl -s -X POST "$PIPELINE_API_URL/campaigns" \
  -H "Content-Type: application/json" \
  -d '{"name":"<campaign-name>","created_by":"harkin","accounts":[...]}'
```

Store the returned `campaign_id`. Tell the user: "Campaign created: `<campaign-id>`"

### 1b. Load the /sites methodology

**Before processing any accounts**, read the full /sites skill instructions into context:

```
Read ~/.claude/commands/sites.md
```

This file contains the complete methodology: scenario definitions (A/B/C/D), the Serper Places API key and query format, headless browser scraping instructions, CSV column spec, filtering rules, and verification steps. **You must follow these instructions exactly for every account.** Skip Step 0 of /sites (asking for output folder) since the campaign folder already exists.

**Re-read trigger:** After every 8 accounts, re-read `~/.claude/commands/sites.md` to refresh the methodology in context.

### 1c. Run /sites as a queue

Process each account one at a time, in order. For each account:

1. **Check if already done** — look for `~/sitemapping/<campaign-name>/account locations/<account-name-slug>-locations.csv`. If it exists, say "Already have locations for <account>. Skipping." and move to the next.

2. **Announce the current account** — say:
   ```
   [2/15] Now extracting locations for: <Account Name>
   (<domain>)
   ```

3. **Run the /sites skill** — follow the instructions from `sites.md` exactly for this account:
   - Research & classify into Scenario A, B, C, or D (Step 1 of /sites)
   - **Tell the user which scenario applies** (Step 2 of /sites)
   - Extract locations using the scenario-specific method (Serper Places API for C/D, scraping for B, direct extraction for A)
   - Save CSV to `~/sitemapping/<campaign-name>/account locations/<account-name-slug>-locations.csv` using the full CSV format from /sites Step 4

4. **After saving**, announce completion:
   ```
   Completed <Account Name>: X locations extracted
   Queue: Y of Z accounts done
   ```

5. **Context limit awareness** — after completing each account, check how many accounts remain. If you've processed 5+ accounts in this session, warn the user:
   ```
   Heads up: I've processed X accounts in this session. If context gets long,
   I'll save progress and you can resume with:
   /sitemapping --resume <campaign-id>
   ```
   The system automatically compresses old messages, but for very large runs (15+ accounts), recommend the user resume in a fresh session after every 8-10 accounts to keep things fast.

6. **Move to next account** in the queue.

### 1d. Verify all locations

After the queue is complete, list all location CSVs:
```bash
ls ~/sitemapping/<campaign-name>/account locations/
```

Report: "All X accounts processed. Y location CSVs created."

If any are missing, ask if the user wants to retry or skip them.

---

## Phase 2: Import to Clay

Push accounts to Clay for LinkedIn + Surfe enrichment:

```bash
curl -s -X POST "$PIPELINE_API_URL/campaigns/<campaign-id>/import-to-clay"
```

Tell the user:
```
Accounts sent to Clay for enrichment.
Clay will find LinkedIn profiles and enrich each person automatically.
This typically takes 15-45 minutes depending on account count.

I'll poll for completion. You can also close this and resume later:
/sitemapping --resume <campaign-id>
```

---

## Phase 3: Poll for Enrichment Completion

Poll the status endpoint every 60 seconds:

```bash
curl -s "$PIPELINE_API_URL/campaigns/<campaign-id>/status"
```

**Polling behavior:**
1. Print a status update each poll: `"Enrichment: X people so far (Y accounts sent to Clay)"`
2. When `stable` is `true` (count unchanged for 3 polls), proceed to Phase 4
3. If 60+ minutes with zero data, warn the user and ask: continue waiting or proceed with current data?

---

## Phase 4: Export People List & Summary

Download the enriched people as CSV:

```bash
curl -s "https://pipeline-api-production-a54c.up.railway.app/campaigns/<campaign-id>/export" \
  -o "$HOME/sitemapping/<campaign-name>/People List.csv"
```

### 4a. Show enrichment summary

Read the CSV and display a **people-per-account breakdown**:

```
Enrichment Complete! Here's what Clay found:

Account Name              People Found
─────────────────────────────────────
Ford Motor Company              47
Eaton                           31
Gerdau                          18
Ferrero                         12
JLL                              8
─────────────────────────────────────
Total                          116 people across 5 accounts
```

### 4b. Explain next steps

Tell the user:

```
Next steps:
1. Match each person's location to your facility location CSVs
2. Filter to only people near a known facility
3. Cap leads per location (you'll choose the limit)
4. Output the final Capped List
```

### 4c. Ask user preferences

Use AskUserQuestion for TWO questions:

**Question 1:** "How many leads max per location?"
- Options: "3", "5", "10", "No cap"

**Question 2:** "How should I prioritize leads when capping?"
- Options:
  - "Persona score (Recommended)" — sort by Clay's persona score (lower = better match), take the top N per location. This uses Clay's AI-generated relevance ranking.
  - "Senior titles first" — use seniority tiering: Director+/VP/C-suite first, then Plant Manager → Manager → others. Within each tier, sort by persona score.
  - "Both — score + seniority" — first filter to Director+ titles, then sort by persona score within that group. Backfill with non-Director if needed.
  - "No priority" — no ranking, just take leads as-is.

Store these preferences for Phase 5.

---

## Phase 5: Run /mapping

The /mapping skill expects:
1. **People List CSV** at `~/sitemapping/<campaign-name>/People List.csv`
2. **Location CSVs** at `~/sitemapping/<campaign-name>/account locations/`

Tell the user: "Running mapping pipeline now."

Execute the /mapping logic inline with the user's preferences from Phase 4c:

- **STEP 1:** Match people → locations → `People List - Enriched.csv`
- **STEP 2:** Filter to matched leads only → `People List - Matched Leads (New).csv`
- **STEP 3:** Cap at **user's chosen limit** per location → `People List - Matched Leads (New) - Capped.csv`
  - If user chose "No cap", skip step 3 and copy Matched Leads as the Capped List directly.
  - Apply the user's chosen prioritization:
    - **Persona score:** Sort by `Persona Score` column ascending (lower = better). Take top N.
    - **Senior titles first:** Apply seniority tiers (Director+/VP/C-suite → Plant Manager → Manager → others). Within each tier, sort by persona score. Take top N.
    - **Both:** Filter Director+ first, sort by persona score. Backfill from non-Director (sorted by score) if under the cap.
    - **No priority:** Take first N rows per location as-is.

All output files go to `~/sitemapping/<campaign-name>/`.

---

## Final Summary

```
Pipeline Complete!

Campaign:         <campaign-name> (<campaign-id>)
Accounts:         X
People enriched:  Y
Matched to sites: Z
Capped leads:     W (capped at <N>/location)

Output files:
  ~/sitemapping/<campaign-name>/People List.csv
  ~/sitemapping/<campaign-name>/People List - Enriched.csv
  ~/sitemapping/<campaign-name>/People List - Matched Leads (New).csv
  ~/sitemapping/<campaign-name>/People List - Matched Leads (New) - Capped.csv
  ~/sitemapping/<campaign-name>/account locations/*.csv

Resume command: /sitemapping --resume <campaign-id>
```

---

## Resume Mode

When `--resume <campaign-id>` is provided:

1. Get campaign status: `curl -s $PIPELINE_API_URL/campaigns/<campaign-id>/status`
2. Ask for campaign name (to find/create the local directory)
3. Based on status:
   - `created` → Check which accounts still need locations, resume the queue at Phase 1b
   - `importing` → Go to Phase 3 (poll)
   - `enriching` → Go to Phase 3 (poll)
   - `ready` → Go to Phase 4 (export)
   - `mapped` → Tell user it's done, show output paths
