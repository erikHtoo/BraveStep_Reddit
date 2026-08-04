# Erik vs SociaVault bake-off

Ran: `2026-08-03T12:58:31.324444+00:00`
Subs: startups, saas · limit/sub: 10

| Provider | OK | Seconds | Items | Cost USD | Errors |
|---|---|---|---|---|---|
| erik_gates_from_sqlite | True | 0.008 | 16 | 0.0 | — |
| sociavault | True | 27.83 | 27 | — | — |

## Notes
### erik_gates_from_sqlite
- startups:P5≈0 n=9
- saas:P5≈1 n=7

### sociavault
- r/startups authors=6 in 2.93s (~1 credit)
- r/startups search_posts=7 in 11.43s (~1 credit)
- r/saas authors=7 in 3.07s (~1 credit)
- r/saas search_posts=7 in 10.40s (~1 credit)
- approx_credits_used≈4 (1 credit/req per docs)
- Fill $ from SociaVault plan after dashboard credit price check

## Decision frame for Chris
- **100% Erik** only if 403 rate low + SQLite pipeline stable + legal/ToS OK
- **100% SociaVault** if product needs reliable datacenter reads
- **Combine** (recommended default): SV for product listening; Erik for cheap research corpus
