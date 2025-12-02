import os
from datetime import datetime, timezone, timedelta
import psycopg2
from celery_app import app

INBOX_DIR = os.getenv("INBOX_DIR", "/var/spool/gammu/inbox")


phones_env = os.getenv("ALLOWED_PHONES", "")
ALLOWED_PHONES = {p.strip() for p in phones_env.split(",") if p.strip()}

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", "5432")),
    "dbname": os.getenv("DB_NAME", "postgres"),
    "user": os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD", ""),
}

UTC_OFFSET_HOURS = int(os.getenv("UTC_OFFSET_HOURS", "5"))


def parse_from_filename(filename):
    """
    Ожидаем формат:
    INYYYYMMDD_HHMMSS_00_+998909192558_00.txt
    Берём 4-ю часть, отрезаем расширение.
    """
    parts = filename.split("_")
    if len(parts) < 4:
        return None

    idx = parts[1]
    phone_part = parts[3]  # что-то типа "+998909192558" или "+998909192558.txt"
    phone, _ = os.path.splitext(phone_part)
    return phone, idx


def build_post_id(phone: str, file_idx: str) -> str:
    """
    Формируем post_id вида:
    sms:+998500110711:17:39:53+05:00
    """
    # Часовой пояс Узбекистана (UTC+5)
    tz = timezone(timedelta(hours=5))
    now = datetime.now(tz)

    # Время с часовым поясом без двоеточия: 173953+0500 → нас интересует HH:MM:SS и +05:00
    time_part = now.strftime("%H:%M:%S")
    offset_raw = now.strftime("%z")  # например "+0500"
    offset = offset_raw[:-2] + ":" + offset_raw[-2:]  # "+05:00"

    return f"sms:{phone}:{time_part}{offset}:{file_idx}"

@app.task(name="tasks.process_sms_inbox")
def process_sms_inbox():
    folder = INBOX_DIR

    if not os.path.isdir(folder):
        print(f"[process_sms_inbox] folder not found: {INBOX_DIR}")
        return

    # Берём только обычные файлы в папке
    files = [
        f for f in os.listdir(folder)
        if os.path.isfile(os.path.join(folder, f))
    ]

    if not files:
        print(f"[process_sms_inbox] no files in {INBOX_DIR}")
        return

    print(f"[process_sms_inbox] found files in {INBOX_DIR}: {files}")

    conn = psycopg2.connect(**DB_CONFIG)
    conn.autocommit = False
    cur = conn.cursor()
    try:
        print(f"[process_sms_inbox] found files in {INBOX_DIR}: {files}")
        for name in files:
            full_path = os.path.join(folder, name)
            phone, file_idx = parse_from_filename(name)

            if not phone:
                print(f"[{name}] ❌ cannot parse phone from filename")
                continue


            if phone not in ALLOWED_PHONES:
                print(f"[{name}] ⛔ phone {phone} not in allowed phones")
                continue
                

            print(f"[{name}] ✅ phone {phone} is allowed, reading file…")

            try:
                with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read().strip()
            except Exception as e:
                print(f"   ⚠ error reading file: {e}")
                continue

            if not content:
                print("   ⚠ file is empty")
                continue

            post_id = build_post_id(phone, file_idx)

            try:
                cur.execute(
                    """
                    INSERT INTO alerts_events (post_id, status, sms_text)
                    VALUES (%s, %s, %s)
                    """,
                    (post_id, "new", content),
                )
                print(f"[{name}] ✔ wrote to DB, status='new'")
                os.remove(full_path)
                print(f"[{name}] ✔ removed file")
                # фикс: без commit данные не попадали в БД (autocommit=False)
                conn.commit()
            except Exception as e:
                print(f"[{name}] ❌ error writing to DB: {e}")
                conn.rollback()
                continue
    finally:
        cur.close()
        conn.close()

