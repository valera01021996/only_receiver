# only_receiver

Фоновый сервис для приёма SMS-сообщений через Gammu SMS Gateway. Каждые 2 минуты сканирует inbox-директорию Gammu, парсит SMS-файлы, валидирует номера по белому списку и сохраняет события в PostgreSQL.

## Схема работы

```
┌──────────────────────┐
│  Gammu SMS Gateway   │
│  (GSM-модем)         │
└─────────┬────────────┘
          │ записывает SMS-файлы
          ▼
┌──────────────────────┐
│  /var/spool/gammu/   │
│  inbox/              │
│  (файловая система)  │
└─────────┬────────────┘
          │ читает файлы каждые 2 мин
          ▼
┌──────────────────────┐       ┌─────────────┐
│  Celery Worker       │◄──────│  Redis       │
│  + Celery Beat       │       │  (брокер)    │
│                      │       └─────────────┘
│  process_sms_inbox() │
│  - парсит имя файла  │
│  - проверяет номер   │
│  - читает текст SMS  │
│  - генерирует post_id│
└─────────┬────────────┘
          │ INSERT
          ▼
┌──────────────────────┐
│  PostgreSQL          │
│  таблица:            │
│  alerts_events       │
│  (post_id, status,   │
│   sms_text,          │
│   created_at)        │
└──────────────────────┘
```

## Переменные окружения

| Переменная | По умолчанию | Описание |
|---|---|---|
| `CELERY_BROKER_URL` | `redis://localhost:6379/0` | URL Redis-брокера для Celery |
| `CELERY_RESULT_BACKEND` | значение `CELERY_BROKER_URL` | Backend для результатов задач |
| `APP_TZ` | `Asia/Tashkent` | Часовой пояс приложения |
| `INBOX_DIR` | `/var/spool/gammu/inbox` | Директория inbox Gammu |
| `ALLOWED_PHONES` | `""` | Разрешённые номера через запятую |
| `DB_HOST` | `localhost` | Хост PostgreSQL |
| `DB_PORT` | `5432` | Порт PostgreSQL |
| `DB_NAME` | `postgres` | Имя базы данных |
| `DB_USER` | `postgres` | Пользователь БД |
| `DB_PASSWORD` | `""` | Пароль БД |
| `UTC_OFFSET_HOURS` | `5` | Смещение UTC в часах |

## Зависимости

- **Python 3**
- **Redis** — брокер сообщений для Celery
- **PostgreSQL** — хранение SMS-событий
- **Gammu SMS Gateway** — приём SMS через GSM-модем

Python-пакеты (основные):

| Пакет | Версия | Назначение |
|---|---|---|
| celery | 5.6.0 | Очередь задач и планировщик |
| redis | 6.4.0 | Клиент Redis |
| psycopg2 | 2.9.11 | Драйвер PostgreSQL |
| python-dotenv | 1.2.1 | Загрузка `.env` файлов |

## Как запустить

### 1. Установить зависимости

```bash
pip install -r requirements.txt
```

### 2. Настроить переменные окружения

Создать файл `.env` в корне проекта:

```env
CELERY_BROKER_URL=redis://localhost:6379/0
DB_HOST=localhost
DB_PORT=5432
DB_NAME=mydb
DB_USER=myuser
DB_PASSWORD=secret
ALLOWED_PHONES=+998901234567,+998907654321
INBOX_DIR=/var/spool/gammu/inbox
```

### 3. Убедиться, что сервисы запущены

- Redis доступен по `CELERY_BROKER_URL`
- PostgreSQL доступен, таблица `alerts_events` создана
- Gammu пишет SMS-файлы в `INBOX_DIR`

### 4. Запустить worker + beat

```bash
celery -A celery_app worker --beat --loglevel=info
```

Или раздельно:

```bash
# Worker (обработка задач)
celery -A celery_app worker --loglevel=info

# Beat (планировщик, каждые 2 минуты)
celery -A celery_app beat --loglevel=info
```
