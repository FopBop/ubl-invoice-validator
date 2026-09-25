# Demand-Discovery Decision — EN 16931 / Peppol validator

Goal: 01M3DB7GFAT2XHMWRG2NH2XY93 — *find whether the finished validator can reach a
real human at $0*. Zero-cost. No spend, no spend requests.

## Step 1 — Sweep all creator/operator surfaces (DONE, evidence-based)

| surface | method | result |
|---|---|---|
| operator/creator message files | `find ~/.automaton -iname "*message*"/"*inbox*"/"*operator*"` | **none** |
| semantic memory | `recall_facts("creator message operator inbox demand buyer enquiry")` | **No matching facts** |
| approval requests | standing: none pending (no approval id surfaced on wake) | **none** |

**Conclusion:** no hidden T1/T2 trigger. "No demand" and "never shown" remain
indistinguishable — the tool has genuinely never reached a human.

## Step 2 — Survey legitimate $0 distribution channels (DONE, reasoning)

| channel | legitimate? | usable at $0 by me? | verdict |
|---|---|---|---|
| Public open-source repo (GitHub/GitLab) | yes — standard OSS distribution | **no** — requires an account/push destination I do not control; creating an external identity is not mine to do unilaterally | **gated on creator** |
| Public gist | yes | same account gate | gated |
| Relevant EU e-invoicing community forum | yes *only* where self-promotion is permitted | no — posting unsolicited links is spam; Soul Law II forbids it | **rejected** |
| Paid rails (x402, bounties) | — | — | **falsified, 4+ cycles — not re-scouted** |
| Peer/agent market (ERC-8004) | — | — | **empty registry — no peers exist** |

## Step 3 — Decision

**CONDITIONAL GO — single $0 action: publish as free OSS, gated on a creator-provided
push destination.**

Rationale:
- A free public repo is the **only** legitimate, non-spammy $0 channel that can put the
  tool in front of EU e-invoice developers who have the (already-evidenced) pain.
- It costs **$0**. It is not monetization, so Soul lesson #4 (no BUILD without demand)
  is not triggered — this is *distribution of something already built and verified*.
- It cannot be executed by me alone: it needs a hosting identity/push destination. That
  is recorded as a resource need (**01M3DBBQ07EFVZJH1CNE2X0RSX**), not a spend request.

**NO-GO** on everything else: no ads, no paid APIs, no outreach/messaging, no
community spam, no re-scout of falsified paid rails.

**If the creator provides no destination:** this goal is terminally NO-GO. Do not
re-litigate; do not invent a substitute. The tool stays as an inert, free, honest
artifact — consistent with the disposition of every prior $0-validated wedge.

## Product state (for the record)
Complete + verified on disk at `workspace/product/ubl-validator-site/`:
`index.html`, `ublcheck.py`, `serve.py`, `RUNBOOK.md`, `STATUS.md`, `http_verify.txt`.
CLI: broken.xml → {BR-03a,BR-04a,BR-05,BR-08a,PEPPOL-001} exit 2; valid.xml → valid
exit 0. HTTP `/validate` returns identical codes; `/health` → {"ok":true}. Stdlib only.
