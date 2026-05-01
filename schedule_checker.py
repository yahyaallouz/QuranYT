"""
Schedule Checker — randomized posting schedule for QuranYT.
Generates 2-3 deterministic-random posting times per day and checks
whether the current moment is close enough to one of them.
"""

import hashlib
import random
import datetime

# ────────────────────────────────────────────────────────────────────────────
#  Configuration
# ────────────────────────────────────────────────────────────────────────────

MIN_POSTS_PER_DAY = 2
MAX_POSTS_PER_DAY = 3
WINDOW_START_HOUR = 8   # 08:00 UTC
WINDOW_END_HOUR = 22    # 22:00 UTC
MIN_GAP_MINUTES = 150   # 2.5 hours
TOLERANCE_MINUTES = 45  # ±45 min match window


def _date_seed(date_str):
    """Deterministic seed from a date string like '2026-05-02'."""
    return int(hashlib.md5(date_str.encode()).hexdigest(), 16)


def get_posting_times_for_date(date_str):
    """
    Generate 2-3 posting times for a given date.
    Uses date-based seed for deterministic but date-unique results.
    Returns list of datetime.time objects (UTC).
    """
    seed = _date_seed(date_str)
    rng = random.Random(seed)

    num_posts = rng.choice([MIN_POSTS_PER_DAY, MAX_POSTS_PER_DAY])
    total_minutes = (WINDOW_END_HOUR - WINDOW_START_HOUR) * 60  # 840 min

    # Generate times with spacing constraints
    for _ in range(200):  # max attempts
        raw_minutes = sorted(rng.sample(range(total_minutes), k=num_posts))

        # Check spacing
        ok = True
        for i in range(1, len(raw_minutes)):
            if raw_minutes[i] - raw_minutes[i - 1] < MIN_GAP_MINUTES:
                ok = False
                break
        if ok:
            break
    else:
        # Fallback: evenly spaced
        gap = total_minutes // (num_posts + 1)
        raw_minutes = [gap * (i + 1) for i in range(num_posts)]

    # Add jitter (±15 min) to avoid round times
    times = []
    for m in raw_minutes:
        jitter = rng.randint(-15, 15)
        m = max(0, min(total_minutes - 1, m + jitter))
        hour = WINDOW_START_HOUR + m // 60
        minute = m % 60
        times.append(datetime.time(hour=hour, minute=minute))

    return times


def _shift_from_yesterday(today_str, times):
    """
    Check if today's times are too close to yesterday's.
    If any time matches within 30 min of yesterday's, shift it slightly.
    """
    yesterday = (datetime.date.fromisoformat(today_str) - datetime.timedelta(days=1)).isoformat()
    yesterday_times = get_posting_times_for_date(yesterday)

    shifted = []
    for t in times:
        t_min = t.hour * 60 + t.minute
        for yt in yesterday_times:
            yt_min = yt.hour * 60 + yt.minute
            if abs(t_min - yt_min) < 30:
                # Shift by 20-40 min
                shift = random.randint(20, 40) * random.choice([1, -1])
                t_min = max(WINDOW_START_HOUR * 60, min(WINDOW_END_HOUR * 60 - 1, t_min + shift))
                t = datetime.time(hour=t_min // 60, minute=t_min % 60)
                break
        shifted.append(t)
    return shifted


def should_post_now(tolerance_minutes=TOLERANCE_MINUTES, now=None):
    """
    Check if the current UTC time is within tolerance of a posting time.
    Returns True if we should post now.
    """
    if now is None:
        now = datetime.datetime.utcnow()

    today_str = now.date().isoformat()
    times = get_posting_times_for_date(today_str)
    times = _shift_from_yesterday(today_str, times)

    now_minutes = now.hour * 60 + now.minute

    for t in times:
        t_minutes = t.hour * 60 + t.minute
        if abs(now_minutes - t_minutes) <= tolerance_minutes:
            print(f"[schedule] ✓ Current time {now.strftime('%H:%M')} matches posting slot {t.strftime('%H:%M')} (±{tolerance_minutes}min)")
            return True

    print(f"[schedule] ✗ Current time {now.strftime('%H:%M')} doesn't match any slot: {[t.strftime('%H:%M') for t in times]}")
    return False


if __name__ == "__main__":
    # Quick test: show today's and tomorrow's times
    today = datetime.date.today().isoformat()
    print(f"Today ({today}): {[t.strftime('%H:%M') for t in get_posting_times_for_date(today)]}")
    tomorrow = (datetime.date.today() + datetime.timedelta(days=1)).isoformat()
    print(f"Tomorrow ({tomorrow}): {[t.strftime('%H:%M') for t in get_posting_times_for_date(tomorrow)]}")
    print(f"Should post now? {should_post_now()}")
