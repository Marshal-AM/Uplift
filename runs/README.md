# Uplift — final end-to-end test (2026-10-07)

Every Task below was created from the merchant's Sokosumi account (preprod, personal workspace), paid in Sokosumi credits through Masumi escrow on Cardano preprod, run by the Uplift coworker, checked by the Chainlink CRE workflow `uplift-clearing`, and — where it changes the store — approved in Sokosumi and published by Chainlink. Each folder holds the exact brief, every Task event with timestamps, the payment receipt, the cost, the Chainlink verdicts and the full deliverables (manifest, artifacts, verification bundle). Problems found during the test and how they were fixed: [ISSUES.md](ISSUES.md).

## Nora (lead) — orchestrated runs on the glass bottle (`glass-cork-bottle`)

Nora plans with a price ceiling, runs the specialists directly (each specialist's agent, verified by Chainlink), then charges once for the specialists whose work passed.

| Run | Task | Status | Credits | Payment | Elapsed | Chainlink |
|---|---|---|---|---|---|---|
| [00-nora-glass-bottle](00-nora-glass-bottle/README.md) | Polish my glass bottle page | COMPLETED | 7.25 | PURCHASED · on-chain ResultSubmitted | 846 s | PASS 95, PASS 100, PASS 82.6, PASS 93, PASS 89, FAIL 0, FAIL 0, PASS 95, PASS 95 |
| [14-nora-full-team](14-nora-full-team/README.md) | Content and compliance for my glass bottle | COMPLETED | 16.0 | PURCHASED · on-chain ResultSubmitted | 928 s | PASS 95, PASS 100, PASS 99, PASS 91.1, PASS 98, PASS 90.1, PASS 76.5, PASS 83.8, PASS 100, PASS 100, PASS 99, PASS 95 |

## The 12 specialists — individual Tasks on the travel tumbler (`travel-tumbler`)

A new merchant listing (title "Travel Tumbler TT-400", one photo, one-line description). Each specialist got one relevant Task, as a merchant would assign it. Declined attempts are kept as evidence; their re-runs follow them. A declined Task was charged when it started, but no result was submitted for it, so its escrow returns to the buyer after the deadline (Masumi refund path). Store-search ranks before and after: [tumbler/RANKS.md](tumbler/RANKS.md).

| Run | Task | Status | Credits | Payment | Elapsed | Chainlink |
|---|---|---|---|---|---|---|
| [01-quinn-before](tumbler/01-quinn-before/README.md) | Audit my travel tumbler listing | COMPLETED | 0.5 | PURCHASED · on-chain ResultSubmitted | 138 s | PASS 95 |
| [02-kai](tumbler/02-kai/README.md) | Keyword research for my travel tumbler | COMPLETED | 1.25 | PURCHASED · on-chain ResultSubmitted | 138 s | PASS 100 |
| [03-rafael](tumbler/03-rafael/README.md) | Competitor scan for my travel tumbler | COMPLETED | 1.25 | PURCHASED · on-chain ResultSubmitted | 140 s | PASS 86.4 |
| [04-priya](tumbler/04-priya/README.md) | What do shoppers dislike about rival travel tumblers? | COMPLETED | 1.5 | PURCHASED · on-chain ResultSubmitted | 373 s | PASS 92 |
| [05a-marcus-declined](tumbler/05a-marcus-declined/README.md) | Launch pricing and promos for my travel tumbler | APPROVAL_REQUIRED | 1.25 | PURCHASED · on-chain FundsLocked | 270 s | PASS 99 |
| [05b-marcus](tumbler/05b-marcus/README.md) | Launch promos for my travel tumbler (new codes) | COMPLETED | 1.25 | PURCHASED · on-chain ResultSubmitted | 193 s | PASS 99 |
| [06-sasha](tumbler/06-sasha/README.md) | Google Ads plan for my travel tumbler | COMPLETED | 1.5 | PURCHASED · on-chain ResultSubmitted | 140 s | PASS 99 |
| [07-clara](tumbler/07-clara/README.md) | Rewrite my travel tumbler product page | COMPLETED | 2.0 | PURCHASED · on-chain ResultSubmitted | 186 s | PASS 91.4 |
| [08-iris](tumbler/08-iris/README.md) | Product photos for my travel tumbler | COMPLETED | 2.5 | PURCHASED · on-chain ResultSubmitted | 200 s | PASS 95 |
| [09a-oskar-declined](tumbler/09a-oskar-declined/README.md) | Catalog setup for my travel tumbler | APPROVAL_REQUIRED | 1.5 | PURCHASED · on-chain FundsLocked | 189 s | PASS 100 |
| [09b-oskar](tumbler/09b-oskar/README.md) | Catalog setup for my travel tumbler (retry) | COMPLETED | 1.5 | PURCHASED · on-chain ResultSubmitted | 248 s | PASS 100 |
| [10-leo](tumbler/10-leo/README.md) | FAQ and launch content for my travel tumbler | COMPLETED | 2.0 | PURCHASED · on-chain ResultSubmitted | 195 s | PASS 100 |
| [11-ruth](tumbler/11-ruth/README.md) | Compliance check of my travel tumbler page | COMPLETED | 0.25 | PURCHASED · on-chain ResultSubmitted | 215 s | PASS 95 |
| [12-yuki](tumbler/12-yuki/README.md) | German version of my travel tumbler page | COMPLETED | 1.0 | PURCHASED · on-chain ResultSubmitted | 262 s | PASS 99 |
| [13-quinn-after](tumbler/13-quinn-after/README.md) | Re-audit my travel tumbler listing | COMPLETED | 0.5 | PURCHASED · on-chain ResultSubmitted | 178 s | PASS 95 |
