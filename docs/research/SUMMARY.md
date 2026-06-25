# Конкурентный анализ: ИИ-инструменты для 1С

> Исследование проведено 2026-06-23

## Проанализированные источники

### GitHub репозитории (9 шт)
- Platform Context Exporter (alkoleft) — экспорт .hbk в LLMs
- Desko77/claude-code-skills-1c — 94 скила для Claude Code
- SteelMorgan/1c-agent-based-dev-framework — модульный фреймворк
- DitriXNew/EDT-MCP — MCP сервер для 1C:EDT
- DitriXNew/MCP-DB-Client — HTTP API к базе 1С
- 1c-syntax/claude-code-bsl-lsp — BSL LS как LSP
- comol/ai_rules_1c — 28 правил + 13 агентов
- 1c-syntax/bsl-language-server — 187 диагностик
- 1c-syntax/bsl-parser — ANTLR4 грамматика

### Статьи (7 шт)
- Habr: «ИИ-кодинг для 1С: Предприятие»
- codeitdir.ru: «Я был не прав про ИИ в 1С»
- Shtruzel: «Cursor для 1С в 2026»
- Infostart: «Выбор модели для разработки в 1С»
- Infostart: «AI-агенты для 1С»
- Infostart: «Cursor IDE для 1С»
- Habr: «1C Metadata Viewer для Cursor»

### Внедрённые фичи
1. Learning loop (auto-skill creation) — из Hermes Agent
2. LSP post-write diff — из Hermes Agent
3. user-profile.md + soul.md — из Hermes Agent
4. Role-switching protocol — вдохновлено CrewAI
5. 94 скила Desko77 — JSON DSL для метаданных
6. 168 проверок EDT-MCP — code quality
7. BSL LS v1.0.1 — анализ .bsl кода

### НЕ внедрено (нам не подходит)
- Cron scheduling (нет фоновых процессов)
- External memory providers (своя система)
- Нейросетевой RAG (TF-IDF работает быстрее на CPU)

Сырые данные (29 JSON файлов) доступны в истории git.
