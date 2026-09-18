from __future__ import annotations

import hmac
from typing import Mapping, Protocol

from agent3.contracts.authz import AuthzContext, DataScope


class IdentityResolver(Protocol):
    def resolve(self, headers: Mapping[str, str]) -> AuthzContext: ...


class TrustedProxyIdentityResolver:
    """Identity adapter for an upstream SSO/reverse-proxy boundary.

    The browser cannot self-assert identity: the proxy must strip incoming
    identity headers, authenticate the user, then inject these headers together
    with the shared proxy token.
    """

    def __init__(self, shared_secret: str, *, purpose: str = "platform-api") -> None:
        if not shared_secret:
            raise ValueError("trusted proxy shared secret must not be empty")
        self._secret = shared_secret
        self._purpose = purpose

    def resolve(self, headers: Mapping[str, str]) -> AuthzContext:
        normalized = {str(key).lower(): str(value) for key, value in headers.items()}
        supplied = normalized.get("x-auth-proxy-token", "")
        if not hmac.compare_digest(supplied, self._secret):
            raise PermissionError("untrusted identity proxy")
        principal = normalized.get("x-principal", "").strip()
        if not principal:
            raise PermissionError("authenticated principal is missing")

        roles = tuple(
            item.strip()
            for item in normalized.get("x-roles", "").split(",")
            if item.strip()
        )
        scopes = self._parse_scopes(normalized.get("x-data-scopes", ""))
        attributes: dict[str, str] = {}
        if normalized.get("x-scope-version"):
            attributes["scope_version"] = normalized["x-scope-version"]
        return AuthzContext(
            principal=principal,
            roles=roles,
            data_scopes=scopes,
            purpose=self._purpose,
            attributes=attributes,
        )

    @staticmethod
    def _parse_scopes(raw: str) -> tuple[DataScope, ...]:
        scopes: list[DataScope] = []
        for group in raw.split(";"):
            group = group.strip()
            if not group:
                continue
            if "=" not in group:
                raise PermissionError("invalid data-scope header")
            dimension, raw_values = group.split("=", 1)
            values = tuple(item.strip() for item in raw_values.split("|") if item.strip())
            scopes.append(DataScope(dimension.strip(), values))
        return tuple(scopes)
