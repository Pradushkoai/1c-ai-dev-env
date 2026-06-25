# 📋 Резюме сессии

> Заполняется после install.sh. Прочитай этот файл первым в новой сессии.

## ⚡ Быстрый старт

### Шаг 0: Проверить окружение
```bash
python3 -m src.cli validate
```

### Шаг 1: Прочитать контекст
1. `runtime/session-resume.md` (этот файл)
2. `runtime/soul.md` — персона
3. `runtime/user-profile.md` — профиль пользователя
4. `runtime/role-switching-protocol.md` — протокол ролей

### 🎭 Role-Switching Protocol
| Тип | Роли |
|------|------|
| Сложная | 🧠 Архитектор → 👨‍💻 Программист → 🔍 Ревьюер → 📝 Документатор |
| Простая | 👨‍💻 Программист → 🔍 Ревьюер |

## 📊 Конфигурации

```bash
python3 -m src.cli config list
```

## 🧰 Команды

```bash
python3 -m src.cli config list
python3 -m src.cli config add --name <name> --zip <path> --title "Title"
python3 -m src.cli config build --name <name>
python3 -m src.cli search "запрос"
python3 -m src.cli bsl analyze <path>
python3 -m src.cli bsl baseline <path>
python3 -m src.cli bsl diff <path>
```
