import os
from celery import Celery
from celery.schedules import crontab
from dotenv import load_dotenv

load_dotenv()

BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
BACKEND_URL = os.getenv("CELERY_RESULT_BACKEND", BROKER_URL)
APP_TZ = os.getenv("APP_TZ", "Asia/Tashkent")

app = Celery(
    "sms_worker",
    broker=BROKER_URL,
    backend=BACKEND_URL,
    include=['tasks'],
)

# часовой пояс приложения
app.conf.timezone = APP_TZ


# планировщик задач (Celery Beat)
app.conf.beat_schedule = {
    "process-sms-inbox-every-3m": {
        "task": "tasks.process_sms_inbox",
        "schedule": crontab(minute="*/3"),  # каждые 3 минуты
    },
}
