from datetime import datetime, timedelta
import pytz
from dateutil.relativedelta import relativedelta

# Zona horaria de Ecuador
TIMEZONE = pytz.timezone("America/Guayaquil")

# 🧠 Mapas de días (Luxon usaba nombres completos)
LUXON_DAY_NAMES = {
    'Monday': 0,
    'Tuesday': 1,
    'Wednesday': 2,
    'Thursday': 3,
    'Friday': 4,
    'Saturday': 5,
    'Sunday': 6
}

def calculate_evaluation_range(filter_range, excluded_days):
    now = datetime.now(TIMEZONE)
    start = None
    end = None

    def is_workday(date):
        day_name = date.strftime('%A')  # e.g., 'Monday'
        return day_name not in excluded_days

    def get_previous_workday(from_date, count):
        date = from_date
        found = 0
        while found < count:
            date -= timedelta(days=1)
            if is_workday(date):
                found += 1
        return date

    if filter_range == "dia_anterior":
        start = get_previous_workday(now, 1).replace(hour=0, minute=0, second=0, microsecond=0)

    elif filter_range == "ultimos_3_dias_laborales":
        start = get_previous_workday(now, 3).replace(hour=0, minute=0, second=0, microsecond=0)

    elif filter_range == "ultimos_5_dias_laborales":
        start = get_previous_workday(now, 5).replace(hour=0, minute=0, second=0, microsecond=0)

    elif filter_range == "ultima_semana":
        start = get_previous_workday(now, 5).replace(hour=0, minute=0, second=0, microsecond=0)

    elif filter_range == "ultimas_2_semana":
        start = get_previous_workday(now, 10).replace(hour=0, minute=0, second=0, microsecond=0)

    elif filter_range == "ultimo_mes":
        prev_month = now - relativedelta(months=1)
        start = prev_month.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        end = (now.replace(day=1) - timedelta(days=1)).replace(hour=23, minute=59, second=59)

    elif filter_range == "ultimo_trimestre":
        current_month = now.month
        current_quarter = (current_month - 1) // 3
        start_month = (current_quarter - 1) * 3 + 1
        if start_month <= 0:
            start_year = now.year - 1
            start_month += 12
        else:
            start_year = now.year
        start = datetime(start_year, start_month, 1, tzinfo=TIMEZONE)
        end = (start + relativedelta(months=3) - timedelta(days=1)).replace(hour=23, minute=59, second=59)

    elif filter_range == "ultimo_semestre":
        if now.month >= 7:
            start = datetime(now.year, 1, 1, tzinfo=TIMEZONE)
            end = datetime(now.year, 6, 30, 23, 59, 59, tzinfo=TIMEZONE)
        else:
            start = datetime(now.year - 1, 7, 1, tzinfo=TIMEZONE)
            end = datetime(now.year - 1, 12, 31, 23, 59, 59, tzinfo=TIMEZONE)

    elif filter_range == "ultimo_anio":
        start = datetime(now.year - 1, 1, 1, tzinfo=TIMEZONE)
        end = datetime(now.year - 1, 12, 31, 23, 59, 59, tzinfo=TIMEZONE)

    else:
        raise ValueError("Invalid selectedFilter")

    # Si no hay end definido, usar el final del día actual
    if end is None:
        end = now.replace(hour=23, minute=59, second=59)

    return {
        "start": start.astimezone(pytz.utc),
        "end": end.astimezone(pytz.utc)
    }