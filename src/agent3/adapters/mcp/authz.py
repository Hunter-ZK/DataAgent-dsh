from __future__ import annotations

from collections.abc import Callable
from agent3.contracts.authz import AuthzContext

AuthzProvider = Callable[[], AuthzContext]


def static_authz_provider(authz: AuthzContext) -> AuthzProvider:
    return lambda: authz
