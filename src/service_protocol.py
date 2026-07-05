"""
service_protocol.py — Protocol для всех сервисов в src/services/.

F1.2 (2026-07-05): Вводит строгий интерфейс для всех сервисов.
Каждый сервис должен реализовывать ServiceProtocol для mock-тестирования
и документирования контракта.

Использование:
    from src.service_protocol import ServiceProtocol

    class MyService(ServiceProtocol):
        @property
        def name(self) -> str:
            return "my_service"

        def initialize(self) -> None:
            ...

        def is_available(self) -> bool:
            return True
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

# F1.7: Импорт для @since декоратора
try:
    from src.since import since as _since
except ImportError:
    def _since(v: str):
        def d(o):
            return o
        return d


@_since("6.0.0")
@runtime_checkable
class ServiceProtocol(Protocol):
    """
    Protocol для всех сервисов проекта.

    Каждый сервис должен:
    1. Иметь name — уникальное имя для логирования и метрик
    2. Иметь initialize() — инициализация (lazy, вызывается при первом использовании)
    3. Иметь is_available() — проверка готовности (например, BSL LS установлен)

    Это позволяет:
    - Mock-тестирование: создавать mock объекты, реализующие ServiceProtocol
    - Документирование контракта: что ожидает вызывающий код от сервиса
    - Dependency injection: передавать любой сервис, реализующий Protocol
    """

    @property
    def name(self) -> str:
        """Уникальное имя сервиса (для логирования и метрик)."""
        ...

    def initialize(self) -> None:
        """Инициализация сервиса (lazy, вызывается при первом использовании).

        Может включать: загрузку конфигурации, проверку зависимостей,
        создание подключений, и т.д.
        """
        ...

    def is_available(self) -> bool:
        """Проверка готовности сервиса к работе.

        Returns:
            True если сервис готов к использованию, False иначе.
        """
        ...
