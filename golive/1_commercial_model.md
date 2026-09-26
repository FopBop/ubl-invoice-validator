# EN-16931 / Peppol Invoice Validator — Commercial Model
_Last updated 2026-09-26. Truthful as of this date: there are no paying customers yet._

## What this is
A standards-correct validator for European e-invoicing documents (EN 16931 semantic model,
Peppol BIS, XRechnung/CIUS). It checks a UBL/CII invoice against the EN 16931 business rules
and reports exactly which rules fail, with locations — the failure your accounting/EHF
integration actually trips on.

## Honest positioning
- The CORE validator is free and open-source (CLI + library). That is deliberate: the free
  tier is the proof, not the product.
- We do not claim SOC2, uptime guarantees, or customers. Anyone reading this can verify the
  rule engine themselves.
- We sell TIME, INTEGRATION, and ACCOUNTABILITY — not the rules themselves, which are public.

## Tiers

### Free — $0
- `ublcheck` CLI, run locally.
- Single-file validation, human-readable + JSON output.
- Self-serve. No account.
Why it exists: proves correctness; the honest baseline an incumbent cannot pretend away.

### Pro — $29 / month
For teams sending invoices programmatically who don't want to run a validator themselves.
- Hosted validation endpoint (POST an invoice, get the rule report).
- Bulk validation of an archive / batch.
- Email support, 2-business-day response.
- EU-hosted.
Why pay vs free: no server to run, no dependency to pin, no rule updates to track.

### Enterprise — from €2,400 / year (annual invoice)
For ERPs/accounting vendors embedding compliant validation.
- On-prem / private deployment.
- Custom CIUS rule packs and mapping assistance.
- Integration review for your sender/receiver pipeline.
- Named support contact.
Why pay: compliance is auditable; you need someone accountable, not a GitHub issue tracker.

## Pricing rationale (honest)
- Pro is priced against the cost of *not* running it: a single rejected invoice batch in a
  month costs more than $29 in labour.
- Enterprise is priced per-integration, not per-seat — the value is the integration, once.

## What we will NOT do
- No fake testimonials, no invented logos, no "trusted by N companies".
- No claim of features that don't exist yet.
- No lock-in: the free CLI always works.
