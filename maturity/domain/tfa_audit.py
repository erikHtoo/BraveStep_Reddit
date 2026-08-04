"""TFA self-audit — free red-team before any campaign-shaped output."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True)
class CampaignContext:
    account_age_days: int
    days_since_last_activity_before_burst: int | None
    product_mention: bool
    hired_upvotes: bool
    friend_support_comments: bool
    bought_aged_account: bool
    formulaic_username: bool
    plagiarized_comments: bool
    abnormal_engagement: bool
    multi_account_herd: bool


@dataclass(frozen=True)
class TfaFinding:
    code: str
    severity: str  # high | med
    message: str


@dataclass(frozen=True)
class TfaAuditResult:
    findings: tuple[TfaFinding, ...]
    pass_: bool

    @property
    def ok(self) -> bool:
        return self.pass_


def audit_campaign(ctx: CampaignContext) -> TfaAuditResult:
    """
    Ask: if this appeared on r/TheseFuckingAccounts, would there be evidence?
    Any high finding = do not ship to a real founder.
    """
    findings: list[TfaFinding] = []

    if ctx.bought_aged_account:
        findings.append(
            TfaFinding(
                "bought_aged_account",
                "high",
                "Bought/aged dormant accounts are TFA #1 tell — never product path.",
            )
        )

    if (
        ctx.days_since_last_activity_before_burst is not None
        and ctx.days_since_last_activity_before_burst >= 180
        and ctx.product_mention
    ):
        findings.append(
            TfaFinding(
                "age_activity_mismatch",
                "high",
                "Long dormancy then sudden product activity — classic spam lifecycle.",
            )
        )

    if ctx.hired_upvotes:
        findings.append(
            TfaFinding("hired_upvotes", "high", "Hired upvotes leave a statistical signature.")
        )

    if ctx.friend_support_comments:
        findings.append(
            TfaFinding(
                "friend_support",
                "high",
                "Friend/support comment rings are read as astroturf.",
            )
        )

    if ctx.multi_account_herd:
        findings.append(
            TfaFinding(
                "herd_alts",
                "high",
                "Cross-account herd behavior is treated as confession on TFA.",
            )
        )

    if ctx.formulaic_username:
        findings.append(
            TfaFinding("formulaic_username", "med", "Formulaic/cluster username pattern.")
        )

    if ctx.plagiarized_comments:
        findings.append(
            TfaFinding("plagiarized", "high", "Copied comments are a common TFA tell.")
        )

    if ctx.abnormal_engagement:
        findings.append(
            TfaFinding(
                "abnormal_engagement",
                "high",
                "Engagement far above sub baseline looks like vote bots.",
            )
        )

    high = any(f.severity == "high" for f in findings)
    return TfaAuditResult(tuple(findings), pass_=not high)
