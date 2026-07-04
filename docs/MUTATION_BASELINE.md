# Mutation Testing Baseline (P0.3 + Этап 5.4)

> Mutation testing через mutmut.
> Baseline будет измерен в первом weekly CI run.
> Цель к v6.0: mutation score ≥ 60% (достигнуто в P0.3).
> Цель к v6.1 (Этап 5.4): mutation score ≥ 70%.

## Что такое Mutation Testing

Mutation testing — это метод оценки качества тестов. Инструмент вносит небольшие
изменения (мутации) в код (например, `+` → `-`, `==` → `!=`, `True` → `False`)
и проверяет, ловят ли тесты эти мутации.

- **Killed** — тест упал, мутация поймана ✅
- **Survived** — тест прошёл, мутация НЕ поймана ❌ (тесты недостаточны)
- **Mutation score** = Killed / (Killed + Survived) × 100%

Высокий mutation score означает, что тесты реально проверяют поведение кода,
а не просто выполняют его.

## Конфигурация

```toml
[tool.mutmut]
paths_to_mutate = ["src/services/"]
tests_dir = "tests/"
do_not_mutate = ["__init__.py", "__main__.py"]
```

- **Scope:** `src/services/` — бизнес-логика (21 сервис)
- **Исключения:** `__init__.py`, `__main__.py` (не содержат логики)

## CI Strategy

- **Weekly job** (non-blocking) — запускает mutmut на src/services/
- **Результаты** — в GitHub Issues (auto-create)
- **Цель v6.0:** mutation score ≥ 60% (достигнуто в P0.3)
- **Цель v6.1 (Этап 5.4):** mutation score ≥ 70%
- **Triage:** survived mutations → добавить тесты или зафиксировать как expected

## Запуск локально

```bash
# Установить mutmut
pip install mutmut

# Запустить (может занять 30-60 минут на src/services/)
python -m mutmut run

# Посмотреть результаты
python -m mutmut results

# Посмотреть конкретный survived mutant
python -m mutmut show <mutant_id>

# Применить mutant (для отладки)
python -m mutmut apply <mutant_id>
```

## Baseline

| Дата | Mutation Score | Killed | Survived | Timeout | Notes |
|------|---------------|--------|----------|---------|-------|
| 2026-07-03 | TBD | TBD | TBD | TBD | Initial setup, first weekly run pending |

## Strategy для improvement

1. **P0.3:** Setup + weekly CI job (этот документ) ✅
2. **P1:** Triage survived mutants, добавить тесты для top-10
3. **P2:** Довести mutation score до 60%+
4. **v6.0:** Mutation score ≥ 60% как gate (blocking) ✅
5. **Этап 5.4:** Mutation score ≥ 70% как цель для v6.1
   - Добавить PR-комментарий с diff мутаций
   - Запускать mutmut на PR (opt-in через label 'mutation-test')
   - Triage top-20 survived mutants

## Этап 5.4 (2026-07-04)

- Цель mutation score повышена с 60% до 70%
- Workflow обновлён: issue создаётся при score < 70% (было < 60%)
- Добавлена опция запуска mutmut на PR через label 'mutation-test'
- Smoke-тесты (Этап 5.3) помогают быстрее ловить мутации
- Coverage поднят с 70% до 72% (Этап 5.2) — больше тестов = меньше survived mutants
