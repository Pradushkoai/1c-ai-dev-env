# Backup Strategy (P2.7)

> Стратегия резервного копирования репозитория.
> P2.7 (план v2 Solo Edition).

## Обзор

Solo-dev с репозиторием только на GitHub = единая точка отказа.
P2.7 добавляет多层 backup стратегию:

1. **GitLab mirror** — автоматический mirror push при каждом push в main
2. **Git bundle backups** — ежедневные backups всей истории репозитория
3. **S3 storage** — опционально для долгосрочного хранения
4. **Restore drill** — ежеквартальная проверка восстановления

## Компоненты

### 1. GitLab Mirror

**Workflow:** `.github/workflows/backup-mirror.yml` (job `mirror-to-gitlab`)

При каждом push в `main` — автоматический `git push --mirror` в GitLab.

**Настройка:**
1. Создайте empty repo на GitLab: `gitlab.com/username/1c-ai-dev-env`
2. Добавьте GitHub secrets:
   - `GITLAB_TOKEN` — Personal access token для GitLab (scope: write_repository)
   - `GITLAB_REPO` — `gitlab.com/username/1c-ai-dev-env.git`

**Проверка:**
```bash
# Локально проверить mirror
git remote -v  # должен показать origin (GitHub) и gitlab (если настроен локально)
git push --mirror gitlab  # ручной mirror push
```

### 2. Git Bundle Backups

**Workflow:** `.github/workflows/backup-mirror.yml` (job `git-bundle-backup`)

Ежедневно в 02:00 UTC — создаёт `git bundle` со всей историей репозитория.

```bash
# Создание bundle
git bundle create 1c-ai-dev-env-backup-YYYYMMDD.bundle --all

# Проверка bundle
git bundle verify 1c-ai-dev-env-backup-YYYYMMDD.bundle

# Восстановление из bundle
git clone 1c-ai-dev-env-backup-YYYYMMDD.bundle restored-repo
```

**Хранение:**
- GitHub Actions artifacts (30 дней retention)
- Опционально: S3-compatible storage (Backblaze B2, MinIO, etc.)

### 3. S3 Storage (опционально)

Для долгосрочного хранения backups (более 30 дней).

**Настройка S3 secrets:**
- `S3_ENDPOINT` — endpoint URL (например, `s3.us-west-000.backblazeb2.com`)
- `S3_ACCESS_KEY` — access key
- `S3_SECRET_KEY` — secret key
- `S3_BUCKET` — bucket name

**Retention policy:** backups старше 30 дней удаляются автоматически.

### 4. Restore Drill

**Workflow:** `.github/workflows/backup-mirror.yml` (job `restore-drill`)

Ежеквартально (1-го января, апреля, июля, октября) — проверка восстановления:
1. Скачивает последний bundle
2. Восстанавливает репозиторий
3. Проверяет целостность (`git fsck --full`)

Если restore drill падает — backup невалиден, нужно investigated.

## Процедура восстановления

### Из GitLab mirror

```bash
# 1. Клонировать из GitLab
git clone https://gitlab.com/username/1c-ai-dev-env.git restored-repo
cd restored-repo

# 2. Добавить GitHub как origin
git remote set-url origin https://github.com/Pradushkoai/1c-ai-dev-env.git

# 3. Проверить целостность
git log --oneline -10
git fsck --full

# 4. Push обратно в GitHub (если GitHub был очищен)
git push origin main
```

### Из git bundle

```bash
# 1. Скачать bundle файл (из GitHub Actions artifacts или S3)
# 2. Восстановить репозиторий
git clone 1c-ai-dev-env-backup-YYYYMMDD.bundle restored-repo
cd restored-repo

# 3. Проверить целостность
git log --oneline -10
git fsck --full

# 4. Добавить remote и push
git remote set-url origin https://github.com/Pradushkoai/1c-ai-dev-env.git
git push origin main
```

## Метрики

| Метрика | Цель | Как измерять |
|---------|------|--------------|
| Mirror uptime | 100% (при каждом push) | GitHub Actions → mirror-to-gitlab job |
| Bundle backup | Daily | GitHub Actions → git-bundle-backup job |
| Restore drill | Quarterly | GitHub Actions → restore-drill job |
| Backup age | <24 hours | Дата последнего bundle файла |
| Recovery time | <30 минут | Время восстановления из bundle |

## Roadmap

- **P2.7 (этот документ):** GitLab mirror + git bundle + tests ✅
- **Future:** Self-hosted Gitea как третий уровень
- **Future:** Backup verification dashboard (Grafana)
- **Future:** Cross-region S3 replication
