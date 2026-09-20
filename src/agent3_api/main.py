from __future__ import annotations

import os
from pathlib import Path

from agent3.execution.postgres_backend import PostgresReadOnlyBackend
from agent3.policy.compiler import PolicyRegistry, SQLPolicyCompiler
from agent3.query.interpreter import DeterministicQuestionInterpreter
from agent3.services.factory import build_core_from_files
from agent3.services.query_engine import QueryEngineService
from agent3_api.app import create_platform_app
from agent3_api.auth import LocalDevIdentityResolver, TrustedProxyIdentityResolver, parse_data_scopes
from agent3_api.clarification import ClarificationStore
from agent3_api.conversation_store import InMemoryConversationStore
from agent3_api.egress import ConservativeTextEgressGate
from agent3_api.event_store import InMemoryConversationEventStore
from agent3_api.harness_runtime import HarnessRuntimeConfig, HarnessRuntimePool
from agent3_api.orchestrator import ConversationOrchestrator
from agent3_api.persistence import PostgresPlatformPersistence


ROOT = Path(__file__).resolve().parents[2]
_LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}


def _enabled(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "on"}


def _identity_from_env():
    if _enabled("AGENT3_DEV_AUTH"):
        host = os.environ.get("AGENT3_HOST", "127.0.0.1").strip().lower()
        if host not in _LOOPBACK_HOSTS:
            raise RuntimeError("AGENT3_DEV_AUTH may only be used with a loopback AGENT3_HOST")
        roles = tuple(
            item.strip()
            for item in os.environ.get("AGENT3_DEV_ROLES", "analyst,pilot-region-user").split(",")
            if item.strip()
        )
        scopes = parse_data_scopes(os.environ.get("AGENT3_DEV_DATA_SCOPES", "region_code=4403"))
        return LocalDevIdentityResolver(
            principal=os.environ.get("AGENT3_DEV_PRINCIPAL", "local-pilot").strip(),
            roles=roles,
            data_scopes=scopes,
            scope_version=os.environ.get("AGENT3_DEV_SCOPE_VERSION", "local-1").strip() or "local-1",
        )

    proxy_secret = os.environ.get("AGENT3_PROXY_SHARED_SECRET", "")
    if not proxy_secret:
        raise RuntimeError(
            "AGENT3_PROXY_SHARED_SECRET is required in production mode. "
            "For local acceptance only, use scripts/start_platform.ps1 which enables loopback-only AGENT3_DEV_AUTH."
        )
    return TrustedProxyIdentityResolver(proxy_secret)


def build_app_from_env():
    metadata_path = Path(os.environ.get("AGENT3_METADATA_YAML", ROOT / "metadata_models" / "loan.yaml"))
    semantic_path = Path(os.environ.get("AGENT3_SEMANTIC_YAML", ROOT / "semantic_models" / "loan.yaml"))
    policy_path = Path(os.environ.get("AGENT3_POLICY_YAML", ROOT / "policies" / "pilot.yaml"))
    core = build_core_from_files(metadata_yaml=metadata_path, semantic_yaml=semantic_path)
    interpreter = DeterministicQuestionInterpreter(core.semantics, core.metadata)
    policy = SQLPolicyCompiler(PolicyRegistry.from_yaml(policy_path))

    execution = None
    replica_dsn = os.environ.get("AGENT3_READ_REPLICA_DSN")
    if replica_dsn:
        execution = PostgresReadOnlyBackend(replica_dsn)
    query_engine = QueryEngineService(core=core, policy=policy, execution=execution)

    platform_dsn = os.environ.get("AGENT3_PLATFORM_POSTGRES_DSN")
    if platform_dsn:
        persistence = PostgresPlatformPersistence(platform_dsn)
        persistence.initialize()
        conversations = persistence.conversations
        events = persistence.events
        clarifications = persistence.clarifications
    else:
        conversations = InMemoryConversationStore()
        events = InMemoryConversationEventStore()
        clarifications = ClarificationStore()

    runtime_pool = HarnessRuntimePool(HarnessRuntimeConfig(
        root=Path(os.environ.get("AGENT3_DSH_HOME_ROOT", ROOT / ".runtime" / "dsh-home")),
        workspace_root=Path(os.environ.get("AGENT3_DSH_WORKSPACE_ROOT", ROOT / ".runtime" / "workspaces")),
        patch_file=ROOT / "dsh" / "sdk" / "query.patch.yml",
        provider=os.environ.get("AGENT3_DSH_PROVIDER", "deepseek-official"),
        model=os.environ.get("AGENT3_DSH_MODEL", "deepseek-v4-flash"),
    ))
    orchestrator = ConversationOrchestrator(
        core=core,
        interpreter=interpreter,
        conversations=conversations,
        events=events,
        clarifications=clarifications,
        runtime_pool=runtime_pool,
        egress_gate=ConservativeTextEgressGate(),
        query_engine=query_engine,
    )
    origins = tuple(item.strip() for item in os.environ.get("AGENT3_CORS_ORIGINS", "").split(",") if item.strip())
    return create_platform_app(
        orchestrator=orchestrator,
        conversations=conversations,
        events=events,
        identity=_identity_from_env(),
        cors_origins=origins,
    )


def run() -> None:
    try:
        import uvicorn
    except ImportError as exc:
        raise RuntimeError("install the platform extra to run agent3-api") from exc

    host = os.environ.get("AGENT3_HOST", "127.0.0.1")
    if _enabled("AGENT3_DEV_AUTH") and host.strip().lower() not in _LOOPBACK_HOSTS:
        raise RuntimeError("local acceptance mode refuses non-loopback API binding")
    uvicorn.run(build_app_from_env(), host=host, port=int(os.environ.get("AGENT3_PORT", "8080")))


if __name__ == "__main__":
    run()
