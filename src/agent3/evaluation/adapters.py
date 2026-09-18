from __future__ import annotations

from typing import Callable, Protocol
from agent3.evaluation.models import EvalTask, RunResult


class EvaluationAdapter(Protocol):
    name: str
    def run(self, task: EvalTask) -> RunResult: ...


class DirectAdapter:
    name = "direct"
    def __init__(self, generate: Callable[[EvalTask], RunResult]) -> None:
        self._generate = generate
    def run(self, task: EvalTask) -> RunResult:
        return self._generate(task)


class BaselineAdapter:
    name = "baseline"
    def __init__(self, generate: Callable[[EvalTask], RunResult]) -> None:
        self._generate = generate
    def run(self, task: EvalTask) -> RunResult:
        return self._generate(task)
