# The Broker Index — Sept 20 UX round: what's in this folder and how to ship it

Everything from the product spec (claude.ai/code/artifact/2403170b-796e-4061-a650-cbae5dd7eb54)
and the prototype canvas, built against the live Supabase project, for the GitHub Pages site.
Upload these files to the repo root (they replace `index.html`, `_shared.css`, `generate_pages.py` and add the rest).

## Ship order (GitHub Pages + Supabase — ≈20 minutes)

1. **Database** — Supabase → SQL Editor → New query → paste `migration-6-ux-round.sql` → Run, then the same
   for `migration-7-broker-owner.sql`. Do this *before* deploying. Both are safe to re-run.
2. **Upload to the repo** — on github.com open the repo → **Add file → Upload files** → drag in everything
   from this folder (including the `.github`, `scripts` and `supabase` folders and the hidden `.nojekyll`).
   Say yes to replacing `index.html`, `_shared.css`, `generate_pages.py`. Commit to `main`.
   GitHub Pages redeploys in about a minute.
3. **Regenerate broker/state pages** — Actions tab → run the existing page-generator workflow (or wait
   for its next scheduled run). New template: shared header, buyer-vs-seller block, review CTA, claim box.
4. **Review moderation (Supabase Edge Function)** — needs the Supabase CLI once, on any computer:
   ```
   npm i -g supabase
   supabase login
   supabase link --project-ref qnxmvzrotgnsgyafewbo
   supabase secrets set ANTHROPIC_API_KEY=sk-ant-...
   supabase functions deploy screen-review --no-verify-jwt
   ```
   Until this is deployed, every review is held as *pending* and you approve it in `/admin.html` —
   nothing publishes unscreened either way.
5. **Monthly broker email (GitHub Action)** — repo → Settings → Secrets and variables → Actions → add
   `SUPABASE_SERVICE_KEY` (Supabase → Project settings → API → service_role), `RESEND_API_KEY`, `DIGEST_FROM`.
   Runs the 1st of each month; test from the Actions tab → "Monthly broker digest" → Run workflow → enter one slug.
   Optional until brokers start claiming profiles.
6. **Google Search Console** — request re-indexing of `/` after deploy (new title, description, favicon,
   Organization/WebSite schema). The favicon in results can take days to weeks to refresh.

**The three `index (3).html`-style pages** in the live sitemap don't exist in the repo — they're gone from
the new sitemap automatically. If Google keeps showing them, remove them in Search Console → Removals.

## What changed, by spec item

| Spec | Where |
|---|---|
| BUG-1 nav differs by page | `_shell.js` renders header + footer on every page from one list (`NAV`). Generated pages use it too. |
| BUG-2 session drop on back nav | `_app.js`: profile cached locally, painted immediately; username prompt only after a *successful* fetch returns null; `pageshow` re-checks silently. |
| NAV-1 new nav | Prospective Sellers · Prospective Buyers · Tools · Methodology · My List · **Find My Perfect Broker** (gold) · Sign in. Collapses to hamburger < 980px; CTA hidden in bar < 600px (it's in the menu and hero). |
| NAV-2 Tools hub | `tools.html` |
| NAV-3 footer | 4 columns + Privacy / Terms / moderation link, in `_shell.js` |
| QUIZ-1..5 | `find-my-perfect-broker.html` — indexable page with WebApplication schema; entry modal on homepage (first visit, 2.5s delay, dismiss persists) links to it. Matching: state (required) → industry specialty → quality where ≥ MIN reviews → priorities weighting. Intro requests → `introductions` table → `/admin.html` Introductions tab (mailto draft, mark sent). |
| PROF-1 real pages | Homepage cards link to `/broker-<slug>.html`; the modal is gone. |
| PROF-2 buyer vs seller | `_app.js renderBrokerLive()` — three score boxes + six paired bars + "biggest gap" line. Sides shown only above `MIN.side`. |
| PROF-3 no stars | No star glyphs rendered anywhere. Scores are 0–10 (`(1–5 avg) × 2`, Bayesian-shrunk). Stars remain the *input* control on the review form. |
| PROF-4 / REV-1 review CTA | Hero, header (mobile menu), broker page (top + bottom), account page, footer. |
| REV-2 form sequence | `write-a-review.html`: broker → Seller/Buyer (seller first) → stage → industry + deal size → six star rows → experience. All required, enforced client-side and by the DB trigger. |
| REV-3 broker not listed | "Can't find them? Add a broker" in the dropdown → inline name/firm/location → review saved as `pending` with a `listing_requests` row → admin "Create broker & publish" (one click, `admin_approve_listing_request()`), reviewer gets an in-app notification. |
| REV-4 moderation | Client regex (emails/phones/links) + `supabase/functions/screen-review` Edge Function (Claude) → `{ok:false, issues}` shown to the reviewer to fix. Function unreachable → `pending` for human review. |
| HOME-1 stat bar | Brokers · Registered buyers · Reviews via `site_stats()` RPC. Buyers/reviews hidden below `STAT_FLOOR` (25). `data-nosnippet` on the bar so Google stops quoting "372Brokers listed". |
| HOME-2 gate | Signed-out: broker query limited to 100 at the request (not hidden DOM); gate card at the end. Broker/state pages stay fully public for SEO (see open question OQ-6). |
| HOME-3 filter UX | Segmented "Everyone / Rated by sellers / Rated by buyers" with a one-line explainer that changes. |
| HOME-4 starred list | Gone from homepage; ★ on a card saves to My List (ranked). |
| ACCT-1..5 | `account.html` — public profile (`?u=username`), ranked My List with arrows + private notes + public/private toggle, shield badges **earned only**, no points anywhere, deal-activity dashboard (log interactions → KPIs, funnel, broker reply times). |
| Section 8 rankings | `brokerage-rankings.html` — firm score 70 / consistency 20 / coverage 10, state filter, `?firm=` opens the per-firm agent report (RPT-2 web version). Shows a "not enough data" panel until firms clear the minimum. |
| Broker dashboard | `broker-dashboard.html` — after a claim is approved the owner gets a notification and a "Manage your broker page" button on their account page. They can edit details/bio and manage up to 5 listings; reviews, scores, slug and ownership are locked by a DB trigger. Listings appear as a collapsed section *below* reviews on the public page with an Inquire form (`listing_inquiries`). |
| Section 9 claim | `claim.html` — search listing, work email, verification method, evidence → `broker_claims` → admin. Linked from the entry modal, footer, every unclaimed broker page. |
| RPT-1 monthly email | `scripts/monthly-broker-digest.js` run by `.github/workflows/monthly-digest.yml`, 1st of month. Skips brokers with no change and no new reviews; suppresses composite below minimum; one-click opt-out (`/account.html?digest=off`). |
| Metrics (section 11) | `_app.js` top: `MIN = {score:3, side:2, rank:5, firm:8, firmAgents:2}`. Raise to 5/3/8/15 when volume allows — one place. |
| Meta descriptions | Every page has a distinct, written description; homepage title/description rewritten; `og-image.png`. |
| Logo in search results | `favicon.ico` (multi-size) + `favicon.svg` + `apple-touch-icon.png` + `logo-512.png`, Organization + WebSite JSON-LD on the homepage. |

## Indexing of broker pages (Search Console "Affected pages" report)
Broker pages now carry their scores, parameter averages, the latest 20 reviews and `AggregateRating` /
`Review` structured data **in the static HTML** — the generator fetches reviews at build time, and `_app.js`
swaps in the weighted score after load. Google no longer needs to render JS to see what makes each page
unique, and rated brokers can show a rating snippet in results. Pages regenerate on every generator run,
so a newly published review reaches the static page on the next run (schedule it daily if it isn't).
Give Google 2–4 weeks after the rebuild before judging the index count; pages with reviews get indexed
first, and unrated pages with identical template text may stay "crawled – not indexed" until they have one.

## Admin moved
The admin tools left the homepage and live at `/admin.html` (link appears on your account page). Tabs:
Pending reviews · Broker requests · Claims · Verification · Introductions · Reports.

## Known limits / decisions to revisit
- **Gate is request-level, not RLS.** A determined user can hit the public API for the full list — but that data is already public through 840 indexable profile pages, so a DB-level gate would only hurt SEO. Flip `GATE` in `_app.js` if you want a different number.
- **Signed-out homepage fetches the first 100 by name**, then ranks within them. Ranking across *all* brokers for signed-out users needs a server-side score — do this when review volume justifies it.
- **Broker "specialty" is free text**, so the quiz's industry match is keyword-based (`IND_KEYS` in the quiz page). Cleaning specialties into a fixed list would sharpen it.
- **`methodology.html`, `about.html`, `articles.html`** are untouched and still have their old inline header. Add `<div id="site-header"></div>` / `<div id="site-footer"></div>` + the three script tags (copy from any new page) to give them the shared nav — 5 minutes each. `methodology.html` should gain a `#moderation` section (footer and review form link to it).
- **Privacy / Terms** are drafts. Get them read by someone qualified before you invite the public.
- **Google's snippet** will update on its own crawl; the description is now 155 chars and the stat bar is excluded from snippets.

## Files
```
_shared.css  _shell.js  _app.js  index.html
find-my-perfect-broker.html  write-a-review.html  account.html  tools.html
brokerage-rankings.html  claim.html  admin.html
prospective-sellers.html  prospective-buyers.html  privacy.html  terms.html
generate_pages.py  migration-6-ux-round.sql  migration-7-broker-owner.sql  broker-dashboard.html  .nojekyll
supabase/functions/screen-review/index.ts  scripts/monthly-broker-digest.js  .github/workflows/monthly-digest.yml
favicon.ico favicon.svg favicon.png favicon-16.png favicon-32.png apple-touch-icon.png icon-192.png logo-512.png og-image.png
```
