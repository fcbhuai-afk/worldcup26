import csv
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
PROCESSED = DATA / "processed"
CONTEXT_FILE = DATA / "pre_match_context.json"

LOOKAHEAD_HOURS = 12
VENUE_COORDINATES = {
    "mexico-city": (19.4326, -99.1332), "guadalajara": (20.6597, -103.3496),
    "monterrey": (25.6866, -100.3161), "toronto": (43.6532, -79.3832),
    "vancouver": (49.2827, -123.1207), "los-angeles": (34.0522, -118.2437),
    "san-francisco": (37.7749, -122.4194), "seattle": (47.6062, -122.3321),
    "houston": (29.7604, -95.3698), "dallas": (32.7767, -96.7970),
    "atlanta": (33.7490, -84.3880), "miami": (25.7617, -80.1918),
    "kansas-city": (39.0997, -94.5786), "boston": (42.3601, -71.0589),
    "new-york": (40.7128, -74.0060), "philadelphia": (39.9526, -75.1652),
}


def fetch_json(url):
    request = Request(url, headers={"User-Agent": "worldcup26-pre-match/1.0"})
    with urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def read_csv(name):
    with (PROCESSED / name).open("r", encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def load_context():
    if not CONTEXT_FILE.exists():
        return {"updated_at": "", "matches": {}}
    return json.loads(CONTEXT_FILE.read_text(encoding="utf-8"))


def parse_utc(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def weather_at(host_city, kickoff):
    coordinates = VENUE_COORDINATES.get(host_city)
    if not coordinates:
        return None
    latitude, longitude = coordinates
    query = urlencode({
        "latitude": latitude,
        "longitude": longitude,
        "hourly": "temperature_2m,relative_humidity_2m",
        "timezone": "UTC",
        "forecast_days": 16,
    })
    payload = fetch_json(f"https://api.open-meteo.com/v1/forecast?{query}")
    hourly = payload.get("hourly", {})
    times = hourly.get("time", [])
    target = kickoff.replace(minute=0, second=0, microsecond=0).strftime("%Y-%m-%dT%H:%M")
    try:
        index = times.index(target)
    except ValueError:
        return None
    return {
        "temperature_c": hourly.get("temperature_2m", [])[index],
        "humidity_pct": hourly.get("relative_humidity_2m", [])[index],
        "source": "Open-Meteo forecast",
        "observed_or_forecast": "forecast",
        "for_kickoff_utc": kickoff.isoformat().replace("+00:00", "Z"),
    }


def main():
    now = datetime.now(timezone.utc)
    matches = read_csv("matches.csv")
    checks = {row["match_number"]: row for row in read_csv("schedule_crosscheck_zhibo8.csv")}
    context = load_context()
    entries = context.setdefault("matches", {})
    updated = 0

    for match in matches:
        if match.get("status_state") not in {"pre", "in"}:
            continue
        kickoff = parse_utc(match["kickoff_utc"])
        if not timedelta(0) <= kickoff - now <= timedelta(hours=LOOKAHEAD_HOURS):
            continue

        entry = entries.setdefault(str(match["match_number"]), {})
        before = json.dumps(entry, ensure_ascii=False, sort_keys=True)
        weather = weather_at(match.get("host_city"), kickoff)
        if weather:
            entry["weather"] = weather
        check = checks.get(match["match_number"], {})
        source_links = [
            {
                "name": "FIFA Match Center",
                "url": "https://www.fifa.com/en/tournaments/mens/worldcup/canadamexicousa2026/match-center",
                "status": "官方页面可能要求浏览器验证，保留人工核验入口",
            },
            {"name": "ESPN", "url": match.get("espn_summary_url", ""), "status": "赛程与赛果"},
            {"name": "直播吧", "url": check.get("zhibo8_match_id", "") and f"https://www.zhibo8.cc/zhibo/zuqiu/2026/match{check['zhibo8_match_id']}v.htm", "status": "赛前资料核验"},
        ]
        entry["source_links"] = [item for item in source_links if item["url"]]
        entry.setdefault("evidence", [])
        entry.setdefault("adjustments", {"home": 0, "away": 0, "draw": 0})
        entry.setdefault("odds", {})
        entry.setdefault("underdog_defensive_evidence", False)
        candidate = json.dumps(entry, ensure_ascii=False, sort_keys=True)
        if candidate != before:
            entry["updated_at"] = now.isoformat(timespec="seconds")
            updated += 1

    if updated:
        context["updated_at"] = now.isoformat(timespec="seconds")
    CONTEXT_FILE.write_text(json.dumps(context, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"updated_matches": updated, "lookahead_hours": LOOKAHEAD_HOURS}, ensure_ascii=False))


if __name__ == "__main__":
    main()
