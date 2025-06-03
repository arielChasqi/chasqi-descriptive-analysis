from datetime import datetime, timezone
from dateutil.parser import parse as parse_date

def is_event_stale(iso_date_str, buffer_minutes=0.5):
    if not iso_date_str:
        return False
    try:
        fecha = parse_date(iso_date_str)  # puede ser aware
        now = datetime.now(timezone.utc)  # 👈 hazlo aware también
        print(f"⌛ UTC ahora: {now.isoformat()}")
        diff = (now - fecha).total_seconds()
        print(f"🕒 Diferencia exacta: {diff:.2f} segundos")
        return diff > (buffer_minutes * 60)
    except Exception as e:
        print(f"❌ Error parseando fecha: {e}")
        return False