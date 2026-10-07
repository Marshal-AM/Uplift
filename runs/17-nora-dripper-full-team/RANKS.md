# Store-search rank: Dripper D-02 (handle `ceramic-dripper`)

A new merchant listing ("Dripper D-02", one phone photo, a one-line description) in the Uplift Shopify development
store, competing with 25 rival coffee listings. Nora ran the full team on it (this folder's [README](README.md)).

## Product search, sorted by relevance: before and after the run

Measured automatically by the Uplift Worker at the start of the run and after it ended: Shopify Admin API
`products(query: <phrase>, sortKey: RELEVANCE)`, top 50, read with the store's own access token
(`POST https://uplift-d8k3b2rn.myshopify.com/admin/api/2026-10/graphql.json`). The phrases are the ones the merchant listed in the brief.

| Phrase | Before the run | After the run | Matching products |
|---|---|---|---|
| ceramic coffee dripper | not found | **#1** | 8 |
| pour over coffee maker | not found | **#1** | 5 |
| pour over coffee dripper | not found | **#1** | 13 |
| ceramic pour over | not found | **#1** | 5 |
| single cup pour over | not found | **not found** | 1 |
| coffee dripper cone | not found | **#1** | 14 |

**Before: found for 0 of 6 phrases. After: #1 for 5 of 6.** Title before: "Dripper D-02"; after:
"D-02 Coffee Drippers Ceramic Dripper 1-2 Cups".
