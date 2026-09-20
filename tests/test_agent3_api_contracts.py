from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from agent3_api.context_builder import render_context_for_model
from agent3_api.contracts import AgentEvent, AgentEventType, ConversationContext
from agent3_api.event_store import InMemoryConversationEventStore
from agent3_api.events import translate_dsh_notification
from agent3_api.harness_runtime import HarnessRuntimeConfig, HarnessRuntimePool


def test_event_store_supports_last_event_id_replay() -> None:
    store = InMemoryConversationEventStore()
    first = store.append(AgentEvent(AgentEventType.THINKING, "c1", "m1", {"text": "a"}))
    second = store.append(AgentEvent(AgentEventType.DONE, "c1", "m1", {}))
    store.append(AgentEvent(AgentEventType.DONE, "other", "m2", {}))

    replay = store.after("c1", first.seq or 0)

    assert replay == (second,)


def test_context_builder_never_serializes_principal_or_scope_details() -> None:
    context = ConversationContext(
        conversation_id="c1",
        user_objective="解释贷款余额变化",
        confirmed_metrics=("loan_balance",),
        previous_results_summary="余额下降 3%",
        authz_summary="本会话数据范围已按权限限定",
    )

    rendered = render_context_for_model(context)

    assert "loan_balance" in rendered
    assert "本会话数据范围已按权限限定" in rendered
    assert "principal" not in rendered.lower()
    assert "region_code" not in rendered


def test_dsh_notification_is_translated_not_forwarded_raw() -> None:
    notification = SimpleNamespace(
        method="session.event",
        payload={"event": {"type": "tool/start", "data": {"tool": "mcp__agent3__validate_sql", "secret": "x"}}},
    )

    event = translate_dsh_notification(notification, conversation_id="c1", message_id="m1")

    assert event is not None
    assert event.event_type is AgentEventType.TOOL_START
    assert event.payload == {"tool": "mcp__agent3__validate_sql"}


class _FakeHarness:
    instances: list["_FakeHarness"] = []

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.started = False
        self.closed = False
        self.calls = []
        self.__class__.instances.append(self)

    def start(self):
        self.started = True

    def run(self, prompt, *, session_id, on_notification=None):
        self.calls.append((prompt, session_id))
        return SimpleNamespace(final_response="ok", finish_reason="completed")

    def close(self):
        self.closed = True


def test_runtime_pool_reuses_one_process_per_principal(tmp_path: Path) -> None:
    patch = tmp_path / "query.patch.yml"
    patch.write_text("[]\n", encoding="utf-8")
    config = HarnessRuntimeConfig(
        root=tmp_path / "homes",
        workspace_root=tmp_path / "workspaces",
        patch_file=patch,
    )
    _FakeHarness.instances.clear()
    pool = HarnessRuntimePool(config, harness_factory=_FakeHarness)

    first = pool.run_turn(principal="alice", session_id="s1", prompt="one")
    second = pool.run_turn(principal="alice", session_id="s2", prompt="two")
    pool.run_turn(principal="bob", session_id="s3", prompt="three")

    assert first.final_response == "ok"
    assert second.final_response == "ok"
    assert len(_FakeHarness.instances) == 2
    assert _FakeHarness.instances[0].kwargs["provider"] == "deepseek-official"
    assert _FakeHarness.instances[0].kwargs["model"] == "deepseek-v4-flash"
    assert "dsh_bin" not in _FakeHarness.instances[0].kwargs
    pool.close()
    assert all(instance.closed for instance in _FakeHarness.instances)


def test_runtime_pool_can_pin_an_explicit_runtime_binary(tmp_path: Path) -> None:
    patch = tmp_path / "query.patch.yml"
    patch.write_text("[]\n", encoding="utf-8")
    runtime = tmp_path / "dsh-runtime.exe"
    runtime.write_text("stub", encoding="utf-8")
    _FakeHarness.instances.clear()
    pool = HarnessRuntimePool(
        HarnessRuntimeConfig(
            root=tmp_path / "homes",
            workspace_root=tmp_path / "workspaces",
            patch_file=patch,
            dsh_bin=runtime,
        ),
        harness_factory=_FakeHarness,
    )

    pool.get("alice")

    assert _FakeHarness.instances[0].kwargs["dsh_bin"] == str(runtime.resolve())
    pool.close()
