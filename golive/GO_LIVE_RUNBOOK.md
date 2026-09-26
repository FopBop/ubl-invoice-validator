# GO-LIVE RUNBOOK — EN 16931 / Peppol Invoice Validator
_For the operator/creator. One page. Minimal actions to turn the finished product into a live, paid service._

**The flip, not a project:** the product side is DONE and verified. Go-live = fill one contact,
host one static page, point one domain. Nothing new gets built.

## Current state (truthful)
- Product: COMPLETE. CLI (`ublcheck.py`), HTTP surface (`serve.py`), browser page (`index.html`).
  Verified: `tests/valid.xml` → valid/exit 0; `tests/broken.xml` → `BR-03a, BR-04a, BR-05, BR-08a, PEPPOL-001`/exit 2.
- Commercial model: written — `1_commercial_model.md` — Free / Pro $29-mo / Enterprise from €2,400-yr.
- Buy-side page: written — `index.html` (deployable static HTML).
- Blocking gap: **no inbound channel**. No email, no hosted domain, no live payment link.
  Payment RECEIPT is already solved: wallet (USDC on Base) `0xc33B689AF03f6C7aE5f51c3E04F9038177c05975`
  can receive. The only missing piece is a surface that lets a buyer FIND and CONTACT us.

## Creator actions to go live (in order)

### 1. Fill the contact + payment path (5 min)
In `index.html`, in the footer, replace `[TO BE SET BY OPERATOR]` with ONE real inbound
path you will actually monitor (an email/mailto or a form endpoint). Next to it, publish the
**USDC-on-Base** address `0xc33B689AF03f6C7aE5f51c3E04F9038177c05975`, stating chain (`Base`)
and asset (`USDC`). Do not publish a contact you cannot service.

### 2. Host the page (10 min, $0)
Static, single-file, no build step.
- Simplest: any static host (GitHub Pages, Cloudflare Pages, Netlify drop) — upload
  `golive/index.html` as `index.html`. Push target already filed as a resource need.
- Self-host: `python3 serve.py` behind a proxy, or drop `index.html` on any static server.

### 3. Point a domain (optional, ~$10–15/yr — the only real cost)
Register a domain; add `A`/`CNAME` to the host from step 2. Static hosts give free HTTPS.
If self-hosting, terminate TLS before taking payment traffic.

### 4. Enable payment receipt
USDC on Base (chain id 8453) to the address above. Pro = pay, then provision the hosted
endpoint; Enterprise = pay, then begin on-prem handoff. No billing system needed for the first customers.

### 5. First-day check (5 min)
- Page renders at the new URL.
- (If self-hosting) `GET /health` → `{"ok":true}`.
- Send a small USDC test to confirm address + confirmation flow before quoting a customer.

## What I (the agent) do automatically once step 1–2 exist
- Serve the hosted validation endpoint for Pro customers (already buildable from `ublcheck.py`).
- Handle requests, return rule reports, track who has paid on-chain. No further product work to start earning.

## What I will NOT do
- No invented traffic, customers, testimonials, logos, or uptime SLAs.
- No cold outreach / spam (Law I & II).
- No spend without approval.

## Carry-forward honesty notes
- The engine is a documented **subset** of EN 16931 / Peppol BIS — a linter, not a certification body.
- Browser surface not machine-verified here; confirm once by hand.
- No paying customers yet. Revenue is aspirational, not reported.

## Why this is the highest-value pending action
Demand is real and quantified; payment receipt is solved; the product is done. The ONLY thing
between us and first revenue is one provisioned inbound channel. Everything else flips on the moment it exists.
