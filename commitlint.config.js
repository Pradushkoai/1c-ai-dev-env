# Commitlint — проверка conventional commits
# https://commitlint.js.org/
#
# Установка:
#   npm install --save-dev @commitlint/cli @commitlint/config-conventional
#   # или через npx (без установки):
#   npx @commitlint/cli --edit
#
# Commitlint запускается через pre-commit hook (см. .pre-commit-config.yaml)
# и в CI (см. .github/workflows/ci.yml lint job).
#
# Правила:
# - type(scope): description
# - type: feat, fix, refactor, docs, test, ci, chore, perf, build, style
# - scope: опционален (p0, p1, p2, p3, epf, dsl, cfe, и т.д.)
# - description: 10-72 символа, строчные буквы, без точки в конце

extends: ['@commitlint/config-conventional']

rules:
  # Тип коммита
  type-enum:
    - 2
    - always
    - [
        'feat',
        'fix',
        'refactor',
        'docs',
        'test',
        'ci',
        'chore',
        'perf',
        'build',
        'style',
        'revert',
      ]
  type-case:
    - 2
    - always
    - lower-case
  type-empty:
    - 2
    - never

  # Scope (опционален)
  scope-case:
    - 0
    - always
    - lower-case
  scope-empty:
    - 0
    - never

  # Subject (описание)
  subject-case:
    - 0
    - always
    - lower-case
  subject-empty:
    - 2
    - never
  subject-full-stop:
    - 2
    - never
    - '.'
  subject-max-length:
    - 1
    - always
    - 72
  subject-min-length:
    - 1
    - always
    - 10

  # Body (опционален)
  body-empty:
    - 0
    - never

  # Footer
  footer-empty:
    - 0
    - never

  # Полная длина
  header-max-length:
    - 2
    - always
    - 100
