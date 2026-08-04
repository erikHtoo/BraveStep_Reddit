"""Maturity HTTP API — port 8100 (Erik listening API stays on 8000)."""

from __future__ import annotations

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from maturity.adapters.erik_corpus import farmability_from_erik, infer_gates_from_erik
from maturity.adapters.reddit_oauth import build_authorize_url, exchange_code, fetch_me
from maturity.adapters.token_store import StoredConnection, save_connection
from maturity.domain.farmability import is_blocked
from maturity.domain.guardrails import Draft, GuardrailResult, HistoryItem, RateState, check_action
from maturity.domain.phases import Phase, TransitionResult, WarmupSignals, ShadowbanStatus, evaluate_transition, plain_english_blockers
from maturity.domain.tfa_audit import CampaignContext, audit_campaign
from maturity.worker.observe import AccountState, observe_once

app = FastAPI(
    title="Bravestep Account Maturity API",
    version="0.1.0",
    description="Half B — account maturity. Observe/coach only. Never auto-post or auto-vote.",
)


class TransitionIn(BaseModel):
    phase: Phase
    verified_email: bool
    target_subs: list[str]
    joined_subs: list[str] = []
    per_sub_karma: dict[str, int] = Field(default_factory=dict)
    removals_7d: int = 0
    shadowban: ShadowbanStatus = ShadowbanStatus.UNKNOWN
    account_age_days: int = 0
    max_age_gate_days: int = 0
    mention_days: int = 0
    spam_filter_14d: int = 0
    rate_limit_errors: int = 0
    total_karma: int = 0


class HistoryIn(BaseModel):
    text: str
    canonical_link: str | None = None


class GuardrailIn(BaseModel):
    text: str
    canonical_link: str | None = None
    is_promo: bool = False
    account_ids_involved: list[str] = []
    history: list[HistoryIn] = []
    actions_last_hour: int = 0
    actions_last_day: int = 0
    shadowbanned: bool = False


class TfaIn(BaseModel):
    account_age_days: int
    days_since_last_activity_before_burst: int | None = None
    product_mention: bool = False
    hired_upvotes: bool = False
    friend_support_comments: bool = False
    bought_aged_account: bool = False
    formulaic_username: bool = False
    plagiarized_comments: bool = False
    abnormal_engagement: bool = False
    multi_account_herd: bool = False


class GatesIn(BaseModel):
    subreddits: list[str]
    source: str = "erik"  # erik | sociavault


class ObserveIn(BaseModel):
    case_id: str
    username: str = ""
    phase: Phase = Phase.SETUP
    target_subs: list[str]
    joined_subs: list[str] = []


class OAuthSaveIn(BaseModel):
    case_id: str
    code: str


@app.get("/health")
def health():
    return {
        "ok": True,
        "service": "maturity",
        "rules": ["no_auto_post", "no_auto_vote", "hitl_only"],
    }


@app.post("/v1/transition")
def transition(body: TransitionIn):
    signals = WarmupSignals(
        verified_email=body.verified_email,
        joined_target_subs=frozenset(body.joined_subs),
        target_subs=frozenset(body.target_subs),
        per_sub_karma=body.per_sub_karma,
        removals_7d=body.removals_7d,
        shadowban=body.shadowban,
        account_age_days=body.account_age_days,
        max_age_gate_days=body.max_age_gate_days,
        mention_days=body.mention_days,
        spam_filter_14d=body.spam_filter_14d,
        rate_limit_errors=body.rate_limit_errors,
        total_karma=body.total_karma,
    )
    result: TransitionResult = evaluate_transition(body.phase, signals)
    return {
        "phase": body.phase,
        "next": result.next,
        "advanced": result.advanced,
        "blocked_by": list(result.blocked_by),
        "blockers_plain": plain_english_blockers(result),
    }


@app.post("/v1/guardrails/check")
def guardrails_check(body: GuardrailIn) -> dict:
    draft = Draft(
        text=body.text,
        canonical_link=body.canonical_link,
        is_promo=body.is_promo,
        account_ids_involved=tuple(body.account_ids_involved),
    )
    rate = RateState(
        actions_last_hour=body.actions_last_hour,
        actions_last_day=body.actions_last_day,
        shadowbanned=body.shadowbanned,
    )
    history = [HistoryItem(text=h.text, canonical_link=h.canonical_link) for h in body.history]
    result: GuardrailResult = check_action(draft, history, rate)
    return {
        "block": result.block,
        "violations": [v.value for v in result.violations],
    }


@app.post("/v1/tfa/audit")
def tfa(body: TfaIn):
    result = audit_campaign(CampaignContext(**body.model_dump()))
    return {
        "ok": result.ok,
        "findings": [{"code": f.code, "severity": f.severity, "message": f.message} for f in result.findings],
    }


@app.post("/v1/gates/infer")
def gates(body: GatesIn):
    if body.source == "erik":
        try:
            estimates = infer_gates_from_erik(body.subreddits)
        except FileNotFoundError as e:
            raise HTTPException(400, str(e)) from e
        return {
            "estimates": [
                {
                    "subreddit": e.subreddit,
                    "karma_gate": e.karma_gate,
                    "gate_kind": e.gate_kind.value,
                    "source": e.source.value,
                    "sample_size": e.sample_size,
                    "notes": e.notes,
                    "avoid": is_blocked(e.subreddit),
                }
                for e in estimates
            ]
        }
    if body.source == "sociavault":
        from maturity.adapters.sociavault import SociaVaultError, subreddit_new_authors
        from maturity.domain.gates import infer_gate_from_survivors

        out = []
        for sub in body.subreddits:
            try:
                authors = subreddit_new_authors(sub)
                e = infer_gate_from_survivors(sub, authors)
                out.append(
                    {
                        "subreddit": e.subreddit,
                        "karma_gate": e.karma_gate,
                        "gate_kind": e.gate_kind.value,
                        "source": e.source.value,
                        "sample_size": e.sample_size,
                        "notes": e.notes,
                        "avoid": is_blocked(e.subreddit),
                    }
                )
            except SociaVaultError as err:
                out.append({"subreddit": sub, "error": str(err)})
        return {"estimates": out}
    raise HTTPException(400, "source must be erik|sociavault")


@app.get("/v1/farmability/{subreddit}")
def farmability(subreddit: str):
    try:
        s = farmability_from_erik(subreddit)
    except FileNotFoundError as e:
        raise HTTPException(400, str(e)) from e
    return {
        "subreddit": s.subreddit,
        "score": s.score,
        "avoid": s.avoid,
        "reasons": list(s.reasons),
    }


@app.get("/v1/oauth/start")
def oauth_start():
    try:
        url, state = build_authorize_url()
    except Exception as e:
        raise HTTPException(400, str(e)) from e
    return {"authorize_url": url, "state": state}


@app.post("/v1/oauth/exchange")
def oauth_exchange(body: OAuthSaveIn):
    try:
        tokens = exchange_code(body.code)
        me = fetch_me(tokens.access_token)
        path = save_connection(
            StoredConnection(
                case_id=body.case_id,
                username=me.name,
                access_token=tokens.access_token,
                refresh_token=tokens.refresh_token,
                scope=tokens.scope,
            )
        )
    except Exception as e:
        raise HTTPException(400, str(e)) from e
    return {"username": me.name, "verified_email": me.verified_email, "stored": str(path)}


@app.post("/v1/observe")
def observe(body: ObserveIn):
    state = AccountState(
        case_id=body.case_id,
        username=body.username,
        phase=body.phase,
        target_subs=frozenset(body.target_subs),
        joined_subs=frozenset(body.joined_subs or body.target_subs),
    )
    try:
        report = observe_once(state)
    except Exception as e:
        raise HTTPException(400, str(e)) from e
    return {
        "case_id": report.case_id,
        "username": report.username,
        "phase": report.phase.value,
        "next_phase": report.next_phase.value,
        "advanced": report.advanced,
        "blockers": report.blockers,
        "verified_email": report.verified_email,
        "per_sub_karma": report.per_sub_karma,
        "checked_at": report.checked_at,
        "note": "observe-only — never posts or votes",
    }
