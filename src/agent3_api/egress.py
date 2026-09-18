from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class TextEgressDecision:
    allowed: bool
    reason: str


class TextEgressGate(Protocol):
    def evaluate(self, text: str, *, purpose: str) -> TextEgressDecision: ...


class ConservativeTextEgressGate:
    """Minimal Stage-A text guard before DeepSeek Official API exposure.

    It detects several high-signal sensitive patterns but is intentionally not
    described as a complete enterprise DLP solution. Stage B must replace or
    augment it with organization-approved classification before real financial
    user prompts are allowed to leave the network.
    """

    _credential = re.compile(r"(?i)(?:bearer\s+[A-Za-z0-9._~+/-]{12,}|sk-[A-Za-z0-9_-]{12,}|password\s*[:=])")
    _cn_id = re.compile(r"(?<!\d)\d{17}[0-9Xx](?!\d)")
    _mobile = re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")
    _long_account = re.compile(r"(?<!\d)\d{16,19}(?!\d)")

    def evaluate(self, text: str, *, purpose: str) -> TextEgressDecision:
        _ = purpose
        if self._credential.search(text):
            return TextEgressDecision(False, "credential-like content is not model-visible")
        if self._cn_id.search(text):
            return TextEgressDecision(False, "identity-number-like content is not model-visible")
        if self._mobile.search(text):
            return TextEgressDecision(False, "mobile-number-like content is not model-visible")
        if self._long_account.search(text):
            return TextEgressDecision(False, "account-number-like content is not model-visible")
        return TextEgressDecision(True, "passed Stage-A conservative text egress checks")
