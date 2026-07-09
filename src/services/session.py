"""
session.py — Stateful session для MCP tools (R2).

R2 (2026-07-09): SessionState хранит состояние между tool calls.
Решает проблему stateless tools: LLM повторно собирает контекст,
забывает что уже проверял, не может resume после context overflow.

Session хранится в runtime/session-state.json (персистентный между calls).
Ключевые поля:
  - plan: Plan (intent, target_context, required_sources)
  - gathered_context: TaskContext (cached, не пересобирается)
  - generated_artifacts: list[GeneratedArtifact]
  - validation_history: list[ValidationResult]
  - tool_call_history: list[ToolCall]
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ToolCall:
    """Запись об одном tool call в сессии."""

    tool_name: str
    timestamp: float
    arguments_summary: str  # короткая сводка аргументов (не полный dump)
    success: bool = True
    duration_ms: float = 0.0


@dataclass
class SessionState:
    """Состояние сессии LLM-агента.

    Персистентное между tool calls — позволяет tools знать,
    что LLM уже делал, и не делать повторную работу.
    """

    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: float = field(default_factory=time.time)
    last_activity: float = field(default_factory=time.time)

    # Plan (intent classification result)
    plan: dict[str, Any] | None = None

    # Cached gathered context (чтобы не пересобирать)
    gathered_context: dict[str, Any] | None = None
    gathered_at: float = 0.0

    # Generated artifacts (BSL code, queries, etc.)
    generated_artifacts: list[dict[str, Any]] = field(default_factory=list)

    # Validation history
    validation_history: list[dict[str, Any]] = field(default_factory=list)

    # Tool call history (последние 20)
    tool_call_history: list[dict[str, Any]] = field(default_factory=list)

    def touch(self) -> None:
        """Обновить last_activity."""
        self.last_activity = time.time()

    def add_tool_call(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        success: bool = True,
        duration_ms: float = 0.0,
    ) -> None:
        """Добавить запись о tool call."""
        # Короткая сводка аргументов (не полный dump — экономим память)
        args_summary = ", ".join(
            f"{k}={str(v)[:50]}" for k, v in arguments.items() if k != "code"
        )
        self.tool_call_history.append(
            {
                "tool_name": tool_name,
                "timestamp": time.time(),
                "arguments_summary": args_summary,
                "success": success,
                "duration_ms": duration_ms,
            }
        )
        # Храним только последние 20 calls
        if len(self.tool_call_history) > 20:
            self.tool_call_history = self.tool_call_history[-20:]
        self.touch()

    def has_called(self, tool_name: str) -> bool:
        """Проверить, был ли уже вызван tool в этой сессии."""
        return any(tc["tool_name"] == tool_name for tc in self.tool_call_history)

    def set_plan(self, plan: dict[str, Any]) -> None:
        """Установить plan (intent classification result)."""
        self.plan = plan
        self.touch()

    def set_gathered_context(self, ctx: dict[str, Any]) -> None:
        """Кэшировать собранный контекст."""
        self.gathered_context = ctx
        self.gathered_at = time.time()
        self.touch()

    def add_artifact(self, artifact: dict[str, Any]) -> str:
        """Добавить сгенерированный artifact, вернуть artifact_id."""
        artifact_id = f"artifact_{len(self.generated_artifacts) + 1}"
        artifact["artifact_id"] = artifact_id
        artifact["created_at"] = time.time()
        self.generated_artifacts.append(artifact)
        self.touch()
        return artifact_id

    def get_artifact(self, artifact_id: str) -> dict[str, Any] | None:
        """Получить artifact по ID."""
        for a in self.generated_artifacts:
            if a.get("artifact_id") == artifact_id:
                return a
        return None

    def add_validation(self, validation: dict[str, Any]) -> None:
        """Добавить результат валидации."""
        validation["validated_at"] = time.time()
        self.validation_history.append(validation)
        self.touch()

    def to_dict(self) -> dict[str, Any]:
        """Сериализовать в dict (для JSON)."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SessionState":
        """Десериализовать из dict."""
        # Фильтруем только известные поля
        known_fields = {
            "session_id", "created_at", "last_activity", "plan",
            "gathered_context", "gathered_at", "generated_artifacts",
            "validation_history", "tool_call_history",
        }
        filtered = {k: v for k, v in data.items() if k in known_fields}
        return cls(**filtered)


class SessionManager:
    """Менеджер сессий — загрузка/сохранение/кэш."""

    def __init__(self, runtime_dir: Path) -> None:
        self._runtime_dir = runtime_dir
        self._session_file = runtime_dir / "session-state.json"
        self._current: SessionState | None = None

    def _load(self) -> SessionState:
        """Загрузить сессию из файла или создать новую."""
        if self._current is not None:
            return self._current

        if self._session_file.exists():
            try:
                data = json.loads(self._session_file.read_text(encoding="utf-8"))
                self._current = SessionState.from_dict(data)
                logger.debug("Session loaded: %s", self._current.session_id)
                return self._current
            except (json.JSONDecodeError, OSError, TypeError) as e:
                logger.warning("Failed to load session, creating new: %s", e)

        self._current = SessionState()
        logger.debug("New session created: %s", self._current.session_id)
        return self._current

    def save(self) -> None:
        """Сохранить текущую сессию в файл."""
        if self._current is None:
            return

        try:
            self._runtime_dir.mkdir(parents=True, exist_ok=True)
            self._session_file.write_text(
                json.dumps(self._current.to_dict(), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except OSError as e:
            logger.warning("Failed to save session: %s", e)

    def get_session(self) -> SessionState:
        """Получить текущую сессию."""
        return self._load()

    def reset(self) -> SessionState:
        """Сбросить сессию (создать новую)."""
        self._current = SessionState()
        self.save()
        return self._current
