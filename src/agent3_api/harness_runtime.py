from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import Any, Callable


@dataclass(frozen=True, slots=True)
class HarnessRuntimeConfig:
    root: Path
    workspace_root: Path
    patch_file: Path
    provider: str = "deepseek-official"
    model: str = "deepseek-v4-flash"
    profile: str = "sdk"
    initialize_timeout_seconds: float = 30.0
    request_timeout_seconds: float = 180.0
    idle_ttl_seconds: float = 1800.0


class HarnessRuntimeUnavailable(RuntimeError):
    pass


class _RuntimeHandle:
    def __init__(self, principal_key: str, harness: Any) -> None:
        self.principal_key = principal_key
        self.harness = harness
        self.last_used = time.monotonic()

    def touch(self) -> None:
        self.last_used = time.monotonic()

    def close(self) -> None:
        self.harness.close()


class HarnessRuntimePool:
    """Pilot runtime pool: one dsh process per principal.

    This is an identity-binding strategy, not a security sandbox. Database
    credentials remain outside agent3-api/dsh and all data access must cross MCP.
    """

    def __init__(self, config: HarnessRuntimeConfig, *, harness_factory: Callable[..., Any] | None = None) -> None:
        self.config = config
        self._handles: dict[str, _RuntimeHandle] = {}
        self._lock = Lock()
        self._factory = harness_factory

    @staticmethod
    def _principal_key(principal: str) -> str:
        return hashlib.sha256(principal.encode("utf-8")).hexdigest()[:24]

    def _load_factory(self) -> Callable[..., Any]:
        if self._factory is not None:
            return self._factory
        try:
            from deepseek_harness import DeepSeekHarness
        except ImportError as exc:  # pragma: no cover - exercised in platform install
            raise HarnessRuntimeUnavailable(
                "deepseek-harness-sdk is not installed; install the platform extra"
            ) from exc
        return DeepSeekHarness

    def _create(self, principal: str) -> _RuntimeHandle:
        key = self._principal_key(principal)
        home = (self.config.root / key).resolve()
        workspace = (self.config.workspace_root / key).resolve()
        home.mkdir(parents=True, exist_ok=True)
        workspace.mkdir(parents=True, exist_ok=True)
        patch = self.config.patch_file.resolve()
        if not patch.exists():
            raise HarnessRuntimeUnavailable(f"SDK query patch does not exist: {patch}")
        factory = self._load_factory()
        harness = factory(
            dsh_home=str(home),
            cwd=str(workspace),
            runtime_cwd=str(Path.cwd().resolve()),
            profile=self.config.profile,
            patches=(str(patch),),
            provider=self.config.provider,
            model=self.config.model,
            initialize_timeout_seconds=self.config.initialize_timeout_seconds,
            request_timeout_seconds=self.config.request_timeout_seconds,
        )
        harness.start()
        return _RuntimeHandle(key, harness)

    def get(self, principal: str) -> _RuntimeHandle:
        key = self._principal_key(principal)
        with self._lock:
            handle = self._handles.get(key)
            if handle is None:
                handle = self._create(principal)
                self._handles[key] = handle
            handle.touch()
            return handle

    def run_turn(
        self,
        *,
        principal: str,
        session_id: str,
        prompt: str,
        on_notification: Callable[[Any], None] | None = None,
    ) -> Any:
        handle = self.get(principal)
        try:
            return handle.harness.run(
                prompt,
                session_id=session_id,
                on_notification=on_notification,
            )
        finally:
            handle.touch()

    def reap_idle(self) -> int:
        deadline = time.monotonic() - self.config.idle_ttl_seconds
        stale: list[_RuntimeHandle] = []
        with self._lock:
            for key, handle in list(self._handles.items()):
                if handle.last_used < deadline:
                    stale.append(self._handles.pop(key))
        for handle in stale:
            handle.close()
        return len(stale)

    def close(self) -> None:
        with self._lock:
            handles = list(self._handles.values())
            self._handles.clear()
        for handle in handles:
            handle.close()
