from datetime import datetime, timedelta

def is_event_stale(iso_date_str, buffer_minutes=2):
    if not iso_date_str:
        return False
    try:
        fecha = datetime.fromisoformat(iso_date_str.replace("Z", "+00:00"))
        return (datetime.utcnow() - fecha) > timedelta(minutes=buffer_minutes)
    except Exception:
        return False