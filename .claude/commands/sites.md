---
description: Extract manufacturing/production facility locations for a company and save to CSV
argument-hint: [company-name]
allowed-tools: WebSearch, WebFetch, Write, Bash, Read, AskUserQuestion
---

# Company Manufacturing Locations Extractor

Extract all **manufacturing and production facility** locations for: **$ARGUMENTS**

**IMPORTANT: Exclude corporate offices, headquarters, sales offices, and administrative locations. Only extract facilities where products are manufactured, assembled, or distributed.**

## Step 0: Ask for Output Folder

**Before doing any research**, ask the user to provide a name for the folder where the location CSV files will be saved. Use AskUserQuestion to prompt them. The folder will be created under the home directory (`~/`). Store the user's response and use it as the output folder name for Step 4.

## Step 1: Research & Classify

Search for the company's manufacturing location data:
1. Search: `"$ARGUMENTS" manufacturing plant locations`
2. Search: `"$ARGUMENTS" production facility locations PDF`
3. Search: `"$ARGUMENTS" factory locations list`
4. Visit their official website's manufacturing/facilities/global presence page

Based on your research, classify into ONE of these three scenarios:

### Scenario A: All locations in one place
- A single PDF or webpage lists all manufacturing facilities with addresses
- Examples: A downloadable PDF with facility list, a text-based directory page, a tabbed regional list

### Scenario B: Interactive map only
- The company has a locations page, but it's an interactive map/tool
- You cannot extract addresses without clicking on each pin individually
- The data exists but is not in a scrapable format
- **Proceed to Step 2B to inspect if the map data is worth scraping**

### Scenario C: Locations not centralized
- No single source contains all manufacturing locations
- Data is scattered across news articles, individual facility pages, press releases
- Would require piecing together from multiple fragmented sources

### Scenario D: Partial data found (Hybrid)
- You found SOME verified locations from official sources (individual facility pages, press releases, EPA filings, etc.)
- But the company claims many more locations than you found
- The official locations page is blocked, requires interaction, or doesn't list all facilities
- **This scenario combines verified locations with Google Places API to get comprehensive coverage**

---

## Step 2: Report Classification

**Tell the user which scenario applies:**

- **If Scenario A:** Say "**Scenario A: All locations in one place**" and proceed to Step 3
- **If Scenario B:** Say "**Scenario B: Interactive map found**" and proceed to Step 2B to inspect
- **If Scenario C:** Say "**Scenario C: Locations not centralized**" and **ASK THE USER** if they want to proceed with Places API search before continuing
- **If Scenario D:** Say "**Scenario D: Partial data found - X verified locations**" and proceed to Step 2D

---

## Step 2B: Inspect Interactive Map (Scenario B only)

When you find an interactive map, **inspect the page source** to determine if the underlying data is worth extracting.

### How to inspect:
1. Use WebFetch to get the full HTML of the map page
2. Look for embedded data in these locations:
   - JSON in `data-*` attributes (e.g., `data-locations`, `data-modal-target`)
   - JavaScript variables (e.g., `var locations = [...]`, `window.mapData`)
   - Embedded `<script type="application/json">` blocks
   - API endpoints being called (e.g., `/api/locations.json`)
   - Google Sheets or external data source URLs

### Evaluate the data:
**Worth scraping (facility-level data):**
- Contains multiple street addresses per country/region
- Has individual facility names with full addresses
- Contains 10+ unique locations with city/state/postal detail

**NOT worth scraping (country/region-level only):**
- Only one headquarters address per country
- Just country names without facility addresses
- Only regional office addresses, not manufacturing plants
- Very few locations (< 10) that are clearly just HQ/offices

### Report your findings:

**If worth scraping via static data:** Say "**Scenario B: Map data is scrapable**" and proceed to Step 3 to extract the embedded data.

**If data requires interaction (filters, pagination, clicks):** Say "**Scenario B: Requires headless browser**" and proceed to Step 2B-Headless.

**If NOT worth scraping:** Say "**Scenario B: Map not worth scraping**" and explain:
1. What the map page URL is
2. What data format you found (JSON attributes, JS variables, etc.)
3. Why it's not useful (country-level only, just HQ addresses, etc.)
4. How many entries exist vs. how many facilities the company claims to have

Then **ASK THE USER**: "The interactive map doesn't contain useful facility-level data. Would you like me to proceed with Scenario C (Google Places API search) to find locations?"

- If user says **yes** → Proceed to Step 2C
- If user says **no** or provides alternative instructions → Follow their guidance

---

## Step 2B-Headless: Headless Browser Extraction

Use this when the location data requires browser interaction (filtering, pagination, clicking) to access.

### When to use headless browser:
- Page has filter dropdowns that must be selected to show results
- Locations load dynamically via JavaScript after page load
- Pagination requires clicking "next" or "load more" buttons
- Data only appears after applying search/filter criteria
- Results are rendered client-side (not in initial HTML)

### Step 2B-Headless-1: Set up Playwright environment

```bash
mkdir -p /tmp/locations-scraper && cd /tmp/locations-scraper
npm init -y 2>/dev/null
npm install playwright 2>/dev/null
npx playwright install chromium 2>/dev/null
```

### Step 2B-Headless-2: Run Page Analyzer Script

**IMPORTANT:** Before writing the extraction script, run this analyzer to understand the page structure.

Create and run `/tmp/locations-scraper/analyze.js`:

```javascript
const { chromium } = require('playwright');
const fs = require('fs');

async function analyzePage(url) {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();

  // Track API calls
  const apiCalls = [];
  page.on('response', async response => {
    const url = response.url();
    if (url.includes('api') || url.includes('location') || url.includes('search') ||
        url.includes('filter') || url.includes('.json')) {
      try {
        const contentType = response.headers()['content-type'] || '';
        if (contentType.includes('json')) {
          const data = await response.json().catch(() => null);
          apiCalls.push({ url, data: data ? JSON.stringify(data).slice(0, 500) : null });
        }
      } catch (e) {}
    }
  });

  await page.goto(url, { waitUntil: 'networkidle', timeout: 60000 });
  await page.waitForTimeout(3000);

  const analysis = await page.evaluate(() => {
    const result = {
      filters: [],
      locationCards: [],
      pagination: null,
      addressPatterns: [],
      phonePatterns: []
    };

    // Find filter elements (dropdowns, checkboxes, accordions)
    const filterSelectors = [
      'select', '[class*="filter"]', '[class*="dropdown"]', '[data-filter]',
      '[class*="accordion"]', '[class*="facet"]', '[role="listbox"]',
      '[class*="select"]', '[class*="Sort"]', '[class*="sort"]'
    ];
    filterSelectors.forEach(sel => {
      document.querySelectorAll(sel).forEach(el => {
        const text = el.textContent?.trim().slice(0, 100) || '';
        const classes = el.className || '';
        const id = el.id || '';
        if (text || classes || id) {
          result.filters.push({
            selector: sel,
            tag: el.tagName,
            id: id,
            classes: typeof classes === 'string' ? classes.slice(0, 200) : '',
            text: text.slice(0, 100),
            options: el.tagName === 'SELECT' ? [...el.options].map(o => o.text).slice(0, 10) : []
          });
        }
      });
    });

    // Find potential location card containers
    const cardSelectors = [
      '[class*="location"]', '[class*="result"]', '[class*="card"]',
      '[class*="item"]', '[class*="listing"]', '[class*="entry"]',
      'article', '[class*="address"]', '[class*="facility"]'
    ];
    cardSelectors.forEach(sel => {
      document.querySelectorAll(sel).forEach((el, i) => {
        if (i > 2) return; // Sample first 3
        const text = el.textContent?.trim() || '';
        // Check if it looks like an address (has numbers, street words, etc)
        const hasAddress = /\d+.*(?:street|st|ave|road|rd|drive|dr|blvd|way|lane|ln|parkway|pkwy|suite|ste)/i.test(text);
        const hasPhone = /[\+]?[\d\s\-\(\)]{10,}/.test(text);
        const hasCity = /(?:alabama|alaska|arizona|arkansas|california|colorado|connecticut|delaware|florida|georgia|hawaii|idaho|illinois|indiana|iowa|kansas|kentucky|louisiana|maine|maryland|massachusetts|michigan|minnesota|mississippi|missouri|montana|nebraska|nevada|new hampshire|new jersey|new mexico|new york|north carolina|north dakota|ohio|oklahoma|oregon|pennsylvania|rhode island|south carolina|south dakota|tennessee|texas|utah|vermont|virginia|washington|west virginia|wisconsin|wyoming|usa|united states|canada|uk|germany|austria|china|india|brazil)/i.test(text);

        if (hasAddress || (hasPhone && hasCity)) {
          result.locationCards.push({
            selector: sel,
            tag: el.tagName,
            classes: (el.className || '').toString().slice(0, 200),
            sampleText: text.slice(0, 300),
            childrenCount: el.children.length
          });
        }
      });
    });

    // Find pagination
    const paginationSelectors = [
      '[class*="pagination"]', '[class*="pager"]', '[aria-label*="page"]',
      '[class*="next"]', '[rel="next"]', 'a[href*="page="]',
      '[class*="load-more"]', '[class*="show-more"]', 'button:contains("more")'
    ];
    paginationSelectors.forEach(sel => {
      const el = document.querySelector(sel);
      if (el) {
        result.pagination = {
          selector: sel,
          tag: el.tagName,
          classes: (el.className || '').toString().slice(0, 200),
          text: el.textContent?.trim().slice(0, 100) || ''
        };
      }
    });

    // Count results indicator
    const countPattern = document.body.innerText.match(/(\d+)\s*(?:results?|locations?|facilities?|sites?)/i);
    result.totalCount = countPattern ? countPattern[1] : null;

    return result;
  });

  analysis.apiCalls = apiCalls;

  await browser.close();

  // Output analysis
  console.log('=== PAGE ANALYSIS ===\n');
  console.log('URL:', url);
  console.log('Total Count Found:', analysis.totalCount || 'Not found');

  console.log('\n=== FILTERS DETECTED ===');
  analysis.filters.slice(0, 10).forEach((f, i) => {
    console.log(`${i+1}. ${f.tag}${f.id ? '#'+f.id : ''} (${f.classes.slice(0,50)})`);
    console.log(`   Text: ${f.text.slice(0,80)}`);
    if (f.options.length) console.log(`   Options: ${f.options.join(', ')}`);
  });

  console.log('\n=== LOCATION CARDS DETECTED ===');
  analysis.locationCards.slice(0, 5).forEach((c, i) => {
    console.log(`${i+1}. ${c.tag} (${c.classes.slice(0,50)})`);
    console.log(`   Sample: ${c.sampleText.slice(0,150)}...`);
  });

  console.log('\n=== PAGINATION ===');
  if (analysis.pagination) {
    console.log(`Found: ${analysis.pagination.tag} (${analysis.pagination.classes.slice(0,50)})`);
    console.log(`Text: ${analysis.pagination.text}`);
  } else {
    console.log('No pagination detected (may be infinite scroll or single page)');
  }

  console.log('\n=== API CALLS INTERCEPTED ===');
  analysis.apiCalls.forEach((api, i) => {
    console.log(`${i+1}. ${api.url}`);
    if (api.data) console.log(`   Data preview: ${api.data.slice(0,200)}...`);
  });

  fs.writeFileSync('/tmp/locations-scraper/analysis.json', JSON.stringify(analysis, null, 2));
  console.log('\n\nFull analysis saved to /tmp/locations-scraper/analysis.json');
}

analyzePage('TARGET_URL_HERE').catch(console.error);
```

Run analyzer:
```bash
cd /tmp/locations-scraper && node analyze.js
```

### Step 2B-Headless-3: Choose Extraction Strategy

Based on the analyzer output, choose the best extraction approach:

**If API detected** → Use Step 2B-Headless-3a (API-first approach)
**If no API detected** → Use Step 2B-Headless-3b (DOM scraping approach)

---

### Step 2B-Headless-3a: API-First Extraction (When API Detected)

When the analyzer detects JSON API calls (e.g., `/api/locations`, `/restSearch/`, `*.json`), use `page.evaluate(fetch())` to call the API directly from within the browser context. This inherits cookies and session state automatically.

```javascript
const { chromium } = require('playwright');
const fs = require('fs');

async function scrapeLocations() {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    userAgent: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
  });
  const page = await context.newPage();

  let allLocations = [];

  // Load page first to establish session/cookies
  await page.goto('TARGET_PAGE_URL', { waitUntil: 'networkidle', timeout: 60000 });
  await page.waitForTimeout(2000);

  // Dismiss cookie consent if present
  try {
    const cookieBtn = await page.$('button:has-text("Accept"), [class*="cookie"] button');
    if (cookieBtn) await cookieBtn.click();
  } catch (e) {}

  // Get total count from page
  const total = parseInt(await page.$eval('.TOTAL_SELECTOR', el => el.textContent).catch(() => '100')) || 100;

  // Fetch all via API using browser context (inherits cookies)
  for (let start = 0; start < total; start += 100) {
    console.log(`Fetching batch: start=${start}...`);
    const result = await page.evaluate(async (url) => {
      const res = await fetch(url);
      return res.json();
    }, `API_URL?start=${start}&rows=100`);

    // Adjust based on actual API response structure
    const docs = result.response?.docs || result.locations || result.results || result.data || [];
    docs.forEach(doc => {
      if (!allLocations.find(l => l.id === doc.id)) allLocations.push(doc);
    });
    await page.waitForTimeout(300);
  }

  await browser.close();

  // Map API fields to standard format and save
  const locations = allLocations.map(doc => ({
    company: 'COMPANY_NAME',
    location_name: doc.name || doc.title || '',
    street_address: doc.address || doc.street || '',
    city: doc.city || '',
    state_province: doc.state || doc.region || '',
    postal_code: doc.postal || doc.zip || '',
    country: doc.country || '',
    phone: doc.phone || '',
    email: doc.email || ''
  }));

  fs.writeFileSync('/tmp/locations-scraper/locations.json', JSON.stringify(locations, null, 2));
}

scrapeLocations().catch(console.error);
```

**Why API-first is preferred:**
- Structured JSON data (no DOM parsing)
- All fields included (phone, email, etc.)
- Clean pagination via API parameters
- More reliable than CSS selectors

After extraction, proceed to **Step 4** to create CSV output.

---

### Step 2B-Headless-3b: DOM Scraping (When No API Detected)

If no API was detected, create a customized extraction script. The script should:

1. **Use detected selectors** - Use the exact CSS classes/selectors found by the analyzer
2. **Handle the specific filter type** - Dropdowns, accordions, or checkboxes as detected
3. **Match pagination style** - Button clicks, URL parameters, or infinite scroll
4. **Intercept APIs if found** - Often the cleanest data source

**Example customized script structure:**

```javascript
const { chromium } = require('playwright');
const fs = require('fs');

async function scrapeLocations() {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();

  const allLocations = [];

  // If API interception is the best approach (detected from analyzer)
  page.on('response', async response => {
    if (response.url().includes('DETECTED_API_PATTERN')) {
      try {
        const data = await response.json();
        // Extract locations from API response structure
        if (data.locations || data.results || data.items) {
          const items = data.locations || data.results || data.items;
          items.forEach(item => {
            allLocations.push({
              name: item.name || item.title,
              address: item.address || item.street,
              city: item.city,
              state: item.state || item.region,
              postal: item.postal || item.zip,
              country: item.country,
              phone: item.phone || item.telephone
            });
          });
        }
      } catch (e) {}
    }
  });

  await page.goto('TARGET_URL', { waitUntil: 'networkidle' });
  await page.waitForTimeout(3000);

  // === FILTER HANDLING (customize based on analyzer output) ===

  // For dropdown filters:
  // await page.selectOption('DETECTED_SELECT_SELECTOR', 'Manufacturing');

  // For accordion/expandable filters:
  // await page.click('DETECTED_ACCORDION_SELECTOR');
  // await page.waitForTimeout(500);
  // await page.click('text=Manufacturing');

  // For checkbox filters:
  // await page.check('DETECTED_CHECKBOX_SELECTOR');

  await page.waitForTimeout(2000);

  // === PAGINATION HANDLING ===

  let pageNum = 1;
  let hasMore = true;

  while (hasMore) {
    console.log(`Processing page ${pageNum}...`);
    await page.waitForTimeout(1500);

    // Extract from DOM (if not using API interception)
    const pageLocations = await page.$$eval('DETECTED_CARD_SELECTOR', cards => {
      return cards.map(card => {
        // Use detected sub-selectors or parse text content
        const text = card.textContent || '';

        // Parse name (usually in h2, h3, or link)
        const nameEl = card.querySelector('h2, h3, a[class*="title"], [class*="name"]');
        const name = nameEl?.textContent?.trim() || '';

        // Parse address lines
        const addressEl = card.querySelector('[class*="address"], address, p');
        const addressText = addressEl?.textContent?.trim() || text;

        // Parse phone
        const phoneMatch = text.match(/[\+]?[\d\s\-\(\)\.]{10,}/);
        const phone = phoneMatch ? phoneMatch[0].trim() : '';

        return { name, address: addressText, phone };
      });
    });

    // Only add if not using API interception
    if (!allLocations.length) {
      allLocations.push(...pageLocations);
    }
    console.log(`Found ${pageLocations.length} on page ${pageNum}`);

    // Check for next page (customize based on detected pagination)
    const nextBtn = await page.$('DETECTED_PAGINATION_SELECTOR');
    if (nextBtn) {
      const isDisabled = await nextBtn.evaluate(el =>
        el.disabled || el.classList.contains('disabled') || el.getAttribute('aria-disabled') === 'true'
      );
      if (!isDisabled) {
        await nextBtn.click();
        await page.waitForTimeout(2000);
        pageNum++;
      } else {
        hasMore = false;
      }
    } else {
      // Try infinite scroll
      const prevCount = allLocations.length;
      await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
      await page.waitForTimeout(2000);
      if (allLocations.length === prevCount) {
        hasMore = false;
      }
    }

    if (pageNum > 50) hasMore = false; // Safety limit
  }

  await browser.close();

  // Deduplicate by address
  const seen = new Set();
  const unique = allLocations.filter(loc => {
    const key = (loc.address || '').toLowerCase().replace(/\s+/g, '');
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });

  fs.writeFileSync('/tmp/locations-scraper/locations.json', JSON.stringify(unique, null, 2));
  console.log(`\nExtracted ${unique.length} unique locations`);
  console.log('Saved to /tmp/locations-scraper/locations.json');
}

scrapeLocations().catch(console.error);
```

### Step 2B-Headless-4: Run and Verify

```bash
cd /tmp/locations-scraper && node scrape.js
```

After extraction:
1. Read `/tmp/locations-scraper/locations.json`
2. Parse raw addresses into structured fields (street, city, state, postal, country)
3. Apply filtering rules (exclude corporate offices, headquarters)
4. Deduplicate by address
5. Proceed to **Step 4** to create the CSV output

### Troubleshooting:

**Page blocks headless browser:**
```javascript
const browser = await chromium.launch({
  headless: true,
  args: ['--disable-blink-features=AutomationControlled']
});
const context = await browser.newContext({
  userAgent: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
});
```

**Content loads too slowly:**
```javascript
await page.waitForSelector('CARD_SELECTOR', { timeout: 30000 });
await page.waitForLoadState('networkidle');
```

**Need to handle cookie consent:**
```javascript
const cookieBtn = await page.$('button:has-text("Accept"), [class*="cookie"] button');
if (cookieBtn) await cookieBtn.click();
```

---

### If Scenario C: Use Google Places API

**Say: "Scenario C: Locations not centralized"**

Explain what you found:
1. What you searched for
2. Why locations aren't centralized (fragmented across divisions, no single list, etc.)
3. What partial data you found during research

Then **ASK THE USER**: "Would you like me to proceed with a comprehensive Google Places API search to find locations? This will search all 50 US states, Canadian provinces, and any subsidiaries/divisions I can identify."

- If user says **yes** → Proceed to Step 2C
- If user says **no** or provides alternative instructions → Follow their guidance

---

## Step 2C: Extract via Google Places API (Scenario C only)

When locations are not centralized, use the Serper.dev Places API to find facilities.

### Step 2C-1: Research subsidiaries and divisions

**IMPORTANT:** Large companies often have facilities listed under subsidiary names. Research these first:

1. Search: `"$ARGUMENTS" subsidiaries acquired companies list`
2. Search: `"$ARGUMENTS" SEC 10-K exhibit 21 subsidiaries`
3. Look for acquired companies, joint ventures, and brand names
4. Note division names (e.g., "ADM Milling", "ADM Animal Nutrition")

**Create a list of search terms:**
- Main company name
- Subsidiary names
- Acquired company names
- Division/brand names

### Step 2C-2: Identify target states/countries

Try to narrow down where the company operates:
1. Search for `"$ARGUMENTS" 10-K SEC filing locations` or `"$ARGUMENTS" annual report facilities`
2. Look for states/countries mentioned in their filings or website
3. If no specific states found, search all 50 US states + Canadian provinces

### Step 2C-3: Query the Places API with Pagination

Use this API to search for locations:
```bash
curl --location 'https://google.serper.dev/places' \
--header 'X-API-KEY: 95c68f369eba6591fd054a1c6b664effca8bdc37' \
--header 'Content-Type: application/json' \
--data '{"q":"$ARGUMENTS [STATE]", "num": 20, "page": 1}'
```

**IMPORTANT: Use pagination to get more results:**
- The API supports `"page": 1`, `"page": 2`, `"page": 3`, etc.
- Different pages return different results

**Pagination rules:**
- If page 1 returns **10 or more results** → also search page 2
- If page 2 returns **10 or more results** → also search page 3
- If a page returns **fewer than 10 results** → stop (no more pages)
- Maximum: search up to page 3 per query (to avoid excessive API calls)

**Comprehensive search strategy:**

1. **Main company searches (with pagination):**
   - `"$ARGUMENTS"` (global)
   - `"$ARGUMENTS" [industry term]` (e.g., "grain elevator", "manufacturing")

2. **Subsidiary/division searches:**
   - Search each subsidiary name found in Step 2C-1
   - Example: "Collingwood Grain", "Wild Flavors ADM"

3. **State-specific searches (for large companies):**
   - `"$ARGUMENTS" [STATE] [industry]` for each relevant state
   - Example: "ADM Illinois grain", "ADM Iowa grain"
   - Search all 50 US states for comprehensive coverage

4. **Canadian provinces (always search):**
   - Ontario, Quebec, Alberta, British Columbia, Manitoba, Saskatchewan, New Brunswick, Nova Scotia, Newfoundland, Prince Edward Island

5. **Division-specific searches:**
   - `"$ARGUMENTS" [division type]`
   - Examples: "ADM ethanol plant", "ADM flour mill", "ADM river terminal"

### Step 2C-4: Verify each result

**CRITICAL: Not all results belong to the target company.** Verify each result:

**Auto-confirm if:**
- Website domain matches company's official domain (e.g., `andritz.com` for Andritz)
- Company name is an exact match AND category is relevant (Manufacturer, Factory, etc.)

**Needs verification if:**
- No website listed
- Website is different from company's official site
- Company name is similar but not exact

**To verify uncertain results:**
1. Search: `"[full address]" "$ARGUMENTS"`
2. Check if news articles, job postings, or official pages mention this location
3. If no confirmation found, mark as "unverified" in notes column or exclude

**Auto-reject if:**
- Website belongs to a completely different company
- Category is unrelated (e.g., "Pest control" for a steel company)
- Business name clearly doesn't match (e.g., "Apple Mobility LLC" when searching for Apple Inc)

### Step 2C-5: Filter results

From verified results, apply standard filtering:
- **KEEP**: category contains "Manufacturer", "Factory", "Production", "Industrial", "Warehouse", "Distribution"
- **EXCLUDE**: category contains "Corporate office", "Sales office", "Headquarters" (unless it's also a manufacturing site)
- **REVIEW**: categories like "Engineering consultant", "Company" - may or may not be manufacturing

### Step 2C-6: Deduplicate

Remove duplicates by address (same location may appear in multiple state searches).

Then proceed to **Step 4** to create the CSV output.

---

## Step 2D: Hybrid Extraction (Partial Data + Google Places API)

Use this when you've found some verified locations but need more comprehensive coverage.

### Step 2D-1: Collect and Store Verified Locations First

Before searching the Places API, compile all verified locations you've already found from:
- Official facility pages (individual location pages on company website)
- EPA/regulatory filings (TRI, RCRA, state environmental databases)
- Press releases announcing facility openings/expansions
- SEC filings (10-K, annual reports mentioning specific addresses)
- Third-party databases (Wastebits, industry directories)
- News articles with specific facility addresses

**For each verified location, record:**
- Full address with street, city, state, postal code
- Phone number (if found)
- Facility type (if explicitly stated)
- Detailed notes about the facility
- Source URL where you found it

**Store these in memory or a temporary structure** - you'll merge them with Places API results later.

### Step 2D-2: Identify Gaps in Coverage

Before running Places API searches, assess:
1. How many locations does the company claim to have? (Check "About Us", investor presentations)
2. How many verified locations did you find?
3. Which states/regions are NOT covered by your verified locations?
4. What facility types might be missing? (e.g., you found treatment plants but no service centers)

### Step 2D-3: Run Targeted Google Places API Searches

Run the same searches as Step 2C, but focus on:
1. **States/regions with no verified locations** - prioritize these
2. **Different search terms** that might surface different facility types:
   - `"$ARGUMENTS" [state]`
   - `"$ARGUMENTS" Environmental Services`
   - `"$ARGUMENTS" Water`
   - `"$ARGUMENTS" [industry-specific term]`
   - Any subsidiary/division names discovered

Use the same API call format:
```bash
curl --location 'https://google.serper.dev/places' \
--header 'X-API-KEY: 95c68f369eba6591fd054a1c6b664effca8bdc37' \
--header 'Content-Type: application/json' \
--data '{"q":"$ARGUMENTS [STATE]", "num": 20, "page": 1}'
```

### Step 2D-4: Merge Verified + API Results

**CRITICAL: Verified locations take priority over API results.**

When merging:

1. **Start with all verified locations** - these go into the final list first
2. **Add API results that DON'T duplicate verified locations**
   - Compare by normalized address (lowercase, remove extra spaces)
   - If an API result matches a verified location's address, SKIP IT (keep the verified version with richer details)
3. **For API results that are new locations:**
   - Add them to the final list
   - Mark source as "Google Places API" in the source_url column
   - Include the API's category in the notes if helpful

**Deduplication logic:**
```
For each API result:
  normalized_address = lowercase(address).replace(/\s+/g, ' ').trim()

  For each verified location:
    if normalized_address contains verified.street OR verified.street contains normalized_address:
      SKIP this API result (it's a duplicate)

  If no match found:
    ADD to final list
```

### Step 2D-5: Enrich API Results Where Possible

For API results that appear to be significant facilities (not just service offices):
1. Try to find more details via a quick web search
2. Look for facility-specific pages that might have:
   - Phone numbers
   - Facility type details
   - Products/services offered at that location

### Step 2D-6: Create Final Merged Output

The final CSV should:
1. Include ALL verified locations (with full details and specific source URLs)
2. Include non-duplicate API results (with "Google Places API" as source)
3. Be sorted logically (by state, then city, or by facility type)
4. Have consistent formatting across both data sources

**Example merged CSV structure:**
```csv
company,location_name,facility_type,street_address,city,state_province,postal_code,country,phone,products_manufactured,notes,source_url,extracted_date
Acme Corp,Phoenix Treatment Plant,Hazardous Waste Treatment,"123 Main St",Phoenix,AZ,85001,USA,(602) 555-1234,,"RCRA permitted, verified from EPA database",https://www.epa.gov/facility/123,2026-02-05
Acme Corp,Tucson Service Center,Service Center,"456 Oak Ave",Tucson,AZ,85701,USA,(520) 555-5678,,,Google Places API,2026-02-05
```

Then proceed to **Step 4** for final CSV creation.

---

## Step 3: Extract Location Data (Scenario A or Scrapable Scenario B only)

**Note: Scenario C uses Step 2C instead, then skips to Step 4.**

### For embedded map data (Scenario B):
If the map contains embedded JSON data (in `data-*` attributes, JavaScript variables, or API responses):
1. Extract all location entries from the embedded data
2. Parse the JSON/data structure to get individual facility records
3. Map the fields to the CSV format (address, city, state, etc.)

### For PDF sources:
Download and parse the PDF using pdfplumber:
```bash
curl -sL "PDF_URL_HERE" -o /tmp/company-locations.pdf
```

Then extract text:
```bash
python3 << 'EOF'
import pdfplumber

with pdfplumber.open('/tmp/company-locations.pdf') as pdf:
    for i, page in enumerate(pdf.pages):
        print(f"=== PAGE {i+1} ===")
        text = page.extract_text()
        if text:
            print(text)
        print()
EOF
```

### For HTML sources:
Use WebFetch to extract the page content.

---

### Filtering Rules

**DELETE entries that explicitly mention:**
- "Corporate" (corporate headquarters, corporate office)
- "Office" (sales office, administrative office, regional office)

**KEEP everything else** - if it doesn't explicitly say corporate/office, include it.

**DEDUPLICATE by address** - if multiple entries have the same street address, keep only one.

### Facility Type Rules

**Only set facility_type if explicitly stated in the source.** Examples:
- "Manufacturing", "MFG", "Production", "Assembly Plant" → Manufacturing
- "Warehouse" → Warehouse
- "Distribution Center", "PDC" → Distribution Center
- "Service Center", "Service Plus" → Service Center
- "Test", "R&D", "Technology Center" → R&D/Test Facility

**If facility type is not clear from the name, leave facility_type blank.**

### Fields to Extract

For each location, extract ALL available fields:
- Location/Facility Name
- Facility Type (only if explicitly stated - otherwise leave blank)
- Street Address
- City
- State/Province/Region
- Postal/ZIP Code
- Country
- Phone (if available)
- Products manufactured (if available)
- Any other metadata present (e.g., business unit code)

Be thorough - capture every location mentioned in the source (except corporate/office entries).

## Step 4: Create CSV Output

Ensure the output directory exists using the folder name the user provided in Step 0:
```bash
mkdir -p ~/<user-provided-folder-name>
```

Write the CSV to: `~/<user-provided-folder-name>/$ARGUMENTS-locations.csv`
(Replace spaces in company name with hyphens, lowercase)

CSV format:
```
company,location_name,facility_type,street_address,city,state_province,postal_code,country,phone,products_manufactured,notes,source_url,extracted_date
```

- Use proper CSV escaping (quote fields with commas)
- Include header row
- Add source_url and today's date (extracted_date)
- If a field is not available, leave it empty (not "N/A")

## Step 5: Report Results

After creating the CSV, report:
1. Number of locations extracted
2. Source URL used (or "Google Places API" for Scenario C)
3. Path to the CSV file
4. Any locations that had incomplete data
5. **For Scenario C only:**
   - How many states/provinces were searched
   - Subsidiaries/divisions searched (list the names)
   - How many results were verified vs unverified
   - Any results that were excluded and why
   - Coverage estimate (locations found vs. company's claimed facility count)
6. **For Scenario D (Hybrid) only:**
   - Total locations extracted (combined)
   - Breakdown: X from verified sources + Y from Google Places API
   - List of verified sources used (EPA, company facility pages, press releases, etc.)
   - States/provinces searched via API
   - Any subsidiaries/divisions searched
   - Deduplication stats (how many API results were duplicates of verified locations)
   - Coverage assessment vs. company's claimed facility count
