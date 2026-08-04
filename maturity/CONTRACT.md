# Maturity contract — lab ↔ Bravestep `feat/reddit-channel`

**Owner:** me (account maturity / Half B)  
**Do not re-derive** — mirror these names into TS (`reddit_warmup`, `reddit_guardrails`, gate inference).  
**Bravestep repo:** locked for now — this sheet is the handoff when Tri opens the branch.

## 1. Phases (order)

| Phase | Code | Allowed (GTM plain) |
|---|---|---|
| setup | `setup` | Verify email, join targets, lurk — no promo |
| value | `value` | Helpful comments only |
| mentions | `mentions` | Disclosed product when natural |
| scaled | `scaled` | Value-native posts + careful links under flood ceiling |

**Rule:** Gate = *where* you can post · Phase = *what* you may say — never mix.

## 2. Transition blockers (machine codes)

| Code prefix / value | Meaning |
|---|---|
| `verified_email` | Email not verified |
| `join_subs:<a,b>` | Missing joined targets |
| `shadowban:clean\|shadowbanned\|unknown` | Health |
| `removals_7d:<n>` | Removals in trailing 7d |
| `account_age:<have><need>` | Below max age gate of targets |
| `per_sub_karma:<sub>` | ≤0 karma in that sub |
| `mention_days:<n><14` | Mentions phase exit |
| `spam_filter_14d:<n>` | Spam filter hits |
| `rate_limit_errors:<n>` | Rate-limit pain |

Founder-facing strings: `plain_english_blockers()` in `domain/phases.py`.

## 3. Guardrail violations (7)

| Code | Blocks submit when |
|---|---|
| `repost` | Same canonical link in history |
| `dup_comment` | Near-dup body |
| `shortener` | bit.ly / t.co / … |
| `flood` | Over hour/day rate |
| `missing_disclosure` | Promo without disclosure pattern |
| `astroturf` | Multi-account herd signal |
| `shadowban` | Account shadowbanned |

Hard rule: **HITL only** — check runs before human submit; never auto-post / auto-vote.

## 4. TFA audit codes (high = do not ship to real founder)

| Code | Severity |
|---|---|
| `bought_aged_account` | high |
| `hired_upvotes` | high |
| `friend_support_comments` | high |
| `multi_account_herd` | high |
| `plagiarized_comments` | high |
| `abnormal_engagement` | med/high |
| `formulaic_username` | med |
| `dormant_then_burst` | med/high |
| `cold_product_mention` | med |

Any **high** → `ok: false` → block campaign-shaped output.

## 5. Gate estimate JSON (P5 survivors)

```json
{
  "subreddit": "startups",
  "karma_gate": 48,
  "gate_kind": "unknown|total_karma|sub_karma",
  "source": "rule_text|active|passive|estimate",
  "sample_size": 5,
  "notes": "…",
  "avoid": false
}
```

- Product samples prefer **SociaVault** `/new`-style.  
- Erik SQLite = research corpus; post score may be weak karma proxy — must stay in `notes`.  
- Tiny `sample_size` → `source: estimate` — do not hard-gate founders.

## 6. HTTP surfaces (lab `:8100`)

| Method | Path | Role |
|---|---|---|
| GET | `/health` | `no_auto_post`, `no_auto_vote`, `hitl_only` |
| POST | `/v1/transition` | FSM |
| POST | `/v1/guardrails/check` | Pre-submit |
| POST | `/v1/tfa/audit` | Pre-campaign |
| POST | `/v1/gates/infer` | `source=erik\|sociavault` |
| GET | `/v1/farmability/{sub}` | Avoid karma farms |
| POST | `/v1/observe` | Observe-only health tick |
| GET/POST | `/v1/oauth/*` | Needs Chris secrets |

## 7. GTM allow-to-ship rule (product)

Reddit lane may surface to a real founder only if **all** are true:

1. Phase allows the action type  
2. Guardrails `block: false`  
3. TFA `ok: true`  
4. Gate confidence acceptable (not noisy estimate for hard gate)  
5. Human submit (HITL)

## 8. Waiting on (not our repo)

| Need | Who |
|---|---|
| Merge listening+maturity PR | Erik |
| OAuth + encryption secrets | Chris |
| Open Bravestep / apply migrations | Tri / Chris |

Until then: keep this contract + tests green; do not touch Bravestep.
