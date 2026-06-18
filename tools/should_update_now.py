import csv
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MATCHES = ROOT / "data" / "processed" / "matches.csv"
WINDOW_MINUTES = 15
TARGET_OFFSETS = [
    ("开赛后2小时15分钟", timedelta(hours=2, minutes=15)),
    ("开赛后3小时", timedelta(hours=3)),
]


def parse_utc(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def load_matches():
    with MATCHES.open("r", encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def current_utc():
    override = os.environ.get("NOW_UTC", "").strip()
    if override:
        return parse_utc(override)
    return datetime.now(timezone.utc)


def should_run(now):
    window = timedelta(minutes=WINDOW_MINUTES)
    for match in load_matches():
        kickoff_value = match.get("kickoff_utc")
        if not kickoff_value:
            continue
        kickoff = parse_utc(kickoff_value)
        for label, offset in TARGET_OFFSETS:
            target = kickoff + offset
            age = now - target
            if timedelta(0) <= age < window:
                return True, (
                    f"命中更新窗口：#{match.get('match_number')} "
                    f"{match.get('home_team')} vs {match.get('away_team')}，{label}。"
                )
    return False, "当前时间没有命中任何比赛的自动更新窗口。"


def write_output(should_update, reason):
    output_path = os.environ.get("GITHUB_OUTPUT")
    if output_path:
        with open(output_path, "a", encoding="utf-8") as fh:
            fh.write(f"should_run={'true' if should_update else 'false'}\n")
            fh.write(f"reason={reason}\n")


def main():
    if os.environ.get("FORCE_UPDATE", "").lower() == "true":
        reason = "手动触发，跳过时间窗口判断。"
        write_output(True, reason)
        print(reason)
        return

    now = current_utc()
    should_update, reason = should_run(now)
    write_output(should_update, reason)
    print(f"now_utc={now.isoformat(timespec='seconds')}")
    print(reason)


if __name__ == "__main__":
    main()
