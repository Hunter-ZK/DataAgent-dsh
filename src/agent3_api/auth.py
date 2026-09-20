from __future__ import annotations

import hmac
from dataclasses import dataclass
from typing import Mapping, Protocol

from agent3.contracts.authz import AuthzContext, DataScope


class IdentityResolver(Protocol):
    def resolve(self, headers: Mapping[str, str]) -> AuthzContext: ...


def parse_data_scopes(raw: str) -> tuple[DataScope, ...]:
    scopes: list[DataScope] = []
    for group in raw.split(";"):
        group = group.strip()
        if not group:
            continue
        if "=" not in group:
            raise PermissionError("invalid data-scope value")
        dimension, raw_values = group.split("=", 1)
        values = tuple(item.strip() for item in raw_values.split("|") if item.strip())
        if not dimension.strip() or not values:
            raise PermissionError("invalid data-scope value")
        scopes.append(DataScope(dimension.strip(), values))
    return tuple(scopes)


class TrustedProxyIdentityResolver:
    """Production identity adapter for an upstream SSO/reverse-proxy boundary.

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

        roles = tuple(item.strip() for item in normalized.get("x-roles", "").split(",") if item.strip())
        scopes = parse_data_scopes(normalized.get("x-data-scopes", ""))
        attributes: dict[str, str] = {}
        if normalized.get("x-scope-version"):
            attributes["scope_version"] = normalized["x-scope-version"]
        attributes["auth_mode"] = "trusted-proxy"
        return AuthzContext(
            principal=principal,
            roles=roles,
            data_scopes=scopes,
            purpose=self._purpose,
            attributes=attributes,
        )


@dataclass(frozen=True, slots=True)
class LocalDevIdentityResolver:
    """Explicit local-acceptance identity. Never use this in deployed environments.

    Network safety is enforced by the composition root: when this resolver is
    selected, agent3-api may only bind to a loopback host. Browser headers are
    intentionally ignored so local testing does not train the frontend to
    self-assert production identity.
    """

    principal: str = "local-pilot"
    roles: tuple[str, ...] = ("analyst", "pilot-region-user")
    data_scopes: tuple[DataScope, ...] = (DataScope("region_code", ("4403",)),)
    scope_version: str = "local-1"
    purpose: str = "local-acceptance"

    def __post_init__(self) -> None:
        if not self.principal.strip():
            raise ValueError("local dev principal must not be empty")

    def resolve(self, headers: Mapping[str, str]) -> AuthzContext:
        _ = headers
        return AuthzContext(
            principal=self.principal,
            roles=self.roles,
            data_scopes=self.data_scopes,
            purpose=self.purpose,
            attributes={"scope_version": self.scope_version, "auth_mode": "local-dev"},
        )
