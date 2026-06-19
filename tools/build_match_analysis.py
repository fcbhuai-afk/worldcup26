import csv
import json
import math
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
PROCESSED = DATA / "processed"
CONTEXT_FILE = DATA / "pre_match_context.json"

TEAM_RATINGS = {
    "Argentina": 94, "France": 93, "Spain": 91, "England": 90,
    "Brazil": 89, "Portugal": 88, "Germany": 87, "Netherlands": 86,
    "Belgium": 84, "Uruguay": 83, "Croatia": 82, "Morocco": 81,
    "Colombia": 80, "Switzerland": 78, "United States": 77, "Japan": 77,
    "Austria": 76, "Mexico": 76, "Sweden": 75, "Norway": 75,
    "Korea Republic": 74, "Senegal": 74, "Ecuador": 73, "Turkiye": 73,
    "Cote d'Ivoire": 72, "Australia": 72, "Canada": 71, "Czechia": 71,
    "Paraguay": 70, "Scotland": 70, "IR Iran": 69, "Saudi Arabia": 68,
    "Egypt": 68, "Ghana": 67, "Algeria": 67, "Bosnia and Herzegovina": 66,
    "Tunisia": 66, "South Africa": 65, "Qatar": 64, "Congo DR": 64,
    "Uzbekistan": 63, "Iraq": 62, "Panama": 62, "Cabo Verde": 61,
    "Jordan": 60, "New Zealand": 60, "Curacao": 59, "Haiti": 58,
}

HOST_COUNTRY = {
    "mexico-city": "Mexico", "guadalajara": "Mexico", "monterrey": "Mexico",
    "toronto": "Canada", "vancouver": "Canada", "los-angeles": "United States",
    "san-francisco": "United States", "seattle": "United States",
    "houston": "United States", "dallas": "United States", "atlanta": "United States",
    "miami": "United States", "kansas-city": "United States", "boston": "United States",
    "new-york": "United States", "philadelphia": "United States",
}

ALTITUDE_BONUS = {"mexico-city": 2, "guadalajara": 1}

VENUE_TIMEZONES = {
    "mexico-city": "America/Mexico_City", "guadalajara": "America/Mexico_City",
    "monterrey": "America/Monterrey", "toronto": "America/Toronto",
    "vancouver": "America/Vancouver", "los-angeles": "America/Los_Angeles",
    "san-francisco": "America/Los_Angeles", "seattle": "America/Los_Angeles",
    "houston": "America/Chicago", "dallas": "America/Chicago",
    "atlanta": "America/New_York", "miami": "America/New_York",
    "kansas-city": "America/Chicago", "boston": "America/New_York",
    "new-york": "America/New_York", "philadelphia": "America/New_York",
}

# This is a modest heuristic, only activated after real temperature and humidity are present.
TEAM_HEAT_ADAPTATION = {
    "Mexico": 8, "South Africa": 8, "Brazil": 8, "Argentina": 7, "Uruguay": 7,
    "Colombia": 8, "Ecuador": 8, "Paraguay": 8, "Cote d'Ivoire": 9,
    "Senegal": 9, "Ghana": 9, "Morocco": 8, "Tunisia": 8, "Algeria": 8,
    "Egypt": 8, "Congo DR": 9, "Cabo Verde": 8, "Haiti": 9, "Panama": 9,
    "Curacao": 9, "Qatar": 9, "Saudi Arabia": 9, "IR Iran": 7, "Iraq": 9,
    "Australia": 7, "Japan": 6, "Korea Republic": 6, "United States": 6,
    "Canada": 4, "England": 4, "Scotland": 4, "Norway": 4, "Sweden": 4,
    "Germany": 5, "Netherlands": 5, "Belgium": 5, "France": 6, "Spain": 7,
    "Portugal": 7, "Croatia": 6, "Switzerland": 5, "Austria": 5,
    "Czechia": 5, "Bosnia and Herzegovina": 5, "Turkiye": 7,
    "New Zealand": 5, "Uzbekistan": 7, "Jordan": 9,
}


def read_csv(path):
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def write_csv(path, rows, fieldnames):
    with path.open("w", newline="", encoding="utf-8-sig") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def load_context():
    if not CONTEXT_FILE.exists():
        return {"matches": {}}
    try:
        return json.loads(CONTEXT_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"matches": {}}


def is_placeholder(team):
    markers = ["Group ", "Winner Match", "Loser Match", "third place", "runners-up", "winners"]
    return any(marker in team for marker in markers)


def clamp(value, low, high):
    return max(low, min(high, value))


def team_rating(team):
    if is_placeholder(team):
        return None
    return TEAM_RATINGS.get(team)


def local_kickoff_hour(match):
    tz_name = VENUE_TIMEZONES.get(match.get("host_city"))
    if not tz_name or not match.get("kickoff_utc"):
        return None
    return datetime.fromisoformat(match["kickoff_utc"].replace("Z", "+00:00")).astimezone(ZoneInfo(tz_name)).hour


def host_and_altitude_adjustment(match):
    value = 0
    host = HOST_COUNTRY.get(match.get("host_city"))
    if match.get("home_team") == host:
        value += 5
    if match.get("away_team") == host:
        value -= 5

    altitude_bonus = ALTITUDE_BONUS.get(match.get("host_city"), 0)
    acclimated = {"Mexico", "Ecuador", "Colombia", "Bolivia", "Peru"}
    if match.get("home_team") in acclimated:
        value += altitude_bonus
    if match.get("away_team") in acclimated:
        value -= altitude_bonus
    return value


def weather_adjustment(match, context):
    weather = context.get("weather") or {}
    temp = weather.get("temperature_c")
    humidity = weather.get("humidity_pct")
    if not isinstance(temp, (int, float)) or not isinstance(humidity, (int, float)):
        return 0, 0, "实时天气待补充"

    if temp >= 32 and humidity >= 60:
        pressure = 1.0
    elif temp >= 28 and humidity >= 60:
        pressure = 0.7
    elif temp >= 28:
        pressure = 0.45
    else:
        pressure = 0.0

    adaptation_delta = TEAM_HEAT_ADAPTATION.get(match["home_team"], 5) - TEAM_HEAT_ADAPTATION.get(match["away_team"], 5)
    lean_effect = clamp(adaptation_delta * pressure * 0.7, -5, 5)
    draw_effect = 0.05 if pressure >= 0.7 else 0.03 if pressure > 0 else 0.0
    note = f"{temp:.0f}C / 湿度{humidity:.0f}%（{weather.get('source', '赛前天气')}）"
    return lean_effect, draw_effect, note


def is_group_opener(match, matches):
    if match.get("stage") != "group-stage":
        return False
    team = {match["home_team"], match["away_team"]}
    earlier = [
        item for item in matches
        if item.get("stage") == "group-stage"
        and item.get("group") == match.get("group")
        and item.get("kickoff_utc", "") < match.get("kickoff_utc", "")
    ]
    seen = {item["home_team"] for item in earlier} | {item["away_team"] for item in earlier}
    return not team.issubset(seen)


def evidence_adjustment(context):
    evidence = context.get("evidence") or []
    adjustments = context.get("adjustments") or {}
    if not evidence:
        return 0, 0, "暂无已核实首发、伤停或赔率证据"
    home = float(adjustments.get("home", 0) or 0)
    away = float(adjustments.get("away", 0) or 0)
    draw = float(adjustments.get("draw", 0) or 0)
    descriptions = [item.get("summary", "") for item in evidence if item.get("summary")]
    return clamp(home - away, -12, 12), clamp(draw, -0.08, 0.08), "；".join(descriptions[:2]) or "已录入赛前证据"


def market_adjustment(context):
    odds = context.get("odds") or {}
    home, draw, away = odds.get("home"), odds.get("draw"), odds.get("away")
    if not all(isinstance(value, (int, float)) and value > 1 for value in (home, draw, away)):
        return 0, 0
    raw = [1 / home, 1 / draw, 1 / away]
    total = sum(raw)
    probs = [value / total for value in raw]
    lean_effect = clamp((probs[0] - probs[2]) * 20, -6, 6)
    draw_effect = clamp((probs[1] - 0.27) * 0.35, -0.05, 0.05)
    return lean_effect, draw_effect


def probabilities(lean, draw_probability):
    draw = clamp(draw_probability, 0.16, 0.45)
    home_share = 1 / (1 + math.exp(-lean / 28))
    home = int(round((1 - draw) * home_share * 100))
    draw_percent = int(round(draw * 100))
    away = 100 - home - draw_percent
    return home, draw_percent, away


def compute_analysis(match, matches, contexts):
    home_rating = team_rating(match["home_team"])
    away_rating = team_rating(match["away_team"])
    context = contexts.get(str(match["match_number"]), {})
    if home_rating is None or away_rating is None:
        return {
            "lean_score": 0, "lean_label": "待定", "confidence": "低",
            "home_rating": home_rating or "", "away_rating": away_rating or "",
            "home_win_probability": 33, "draw_probability": 34, "away_win_probability": 33,
            "model_summary": "淘汰赛对阵或球队尚未确定。", "environment_note": "待定",
            "pre_match_status": "待球队确定", "pre_match_updated_at": "",
            "evidence_summary": "", "pre_match_sources": json.dumps([], ensure_ascii=False),
            "factor_breakdown": json.dumps([], ensure_ascii=False),
        }

    delta = home_rating - away_rating
    group_stage = match.get("stage") == "group-stage"
    hard = delta * (1.45 if group_stage else 1.3)
    host_altitude = host_and_altitude_adjustment(match)
    weather_lean, weather_draw, weather_note = weather_adjustment(match, context)
    evidence_lean, evidence_draw, evidence_note = evidence_adjustment(context)
    market_lean, market_draw = market_adjustment(context)

    raw_lean = hard + host_altitude + weather_lean + evidence_lean + market_lean
    lean_cap = 55 if group_stage else 65
    lean = int(round(clamp(raw_lean, -lean_cap, lean_cap)))

    base_draw = 0.26 if group_stage else 0.20
    opener_draw = 0.04 if group_stage and is_group_opener(match, matches) else 0
    defensive_draw = 0.04 if context.get("underdog_defensive_evidence") else 0
    draw_probability = base_draw + opener_draw + weather_draw + evidence_draw + market_draw + defensive_draw
    home_prob, draw_prob, away_prob = probabilities(lean, draw_probability)

    confidence = "高" if abs(lean) >= 45 else "中" if abs(lean) >= 25 else "低"
    label = f"倾向 {match['home_team']}" if lean > 10 else f"倾向 {match['away_team']}" if lean < -10 else "接近均势"
    status = "临场资料已更新" if context.get("evidence") else "等待赛前资料"
    updated_at = context.get("updated_at", "")

    factors = [
        {"factor": "硬实力差", "value": round(hard, 1)},
        {"factor": "主场/海拔", "value": round(host_altitude, 1)},
        {"factor": "实时天气适应", "value": round(weather_lean, 1)},
        {"factor": "已核实临场信息", "value": round(evidence_lean + market_lean, 1)},
        {"factor": "平局修正", "value": round((draw_probability - base_draw) * 100, 1)},
    ]
    summary = (
        f"静态硬实力 {home_rating}:{away_rating}；{weather_note}；{evidence_note}。"
        f"三结果概率为 {home_prob}% / {draw_prob}% / {away_prob}%。"
    )
    return {
        "lean_score": lean, "lean_label": label, "confidence": confidence,
        "home_rating": home_rating, "away_rating": away_rating,
        "home_win_probability": home_prob, "draw_probability": draw_prob,
        "away_win_probability": away_prob, "model_summary": summary,
        "environment_note": weather_note, "pre_match_status": status,
        "pre_match_updated_at": updated_at, "evidence_summary": evidence_note,
        "pre_match_sources": json.dumps(context.get("source_links") or [], ensure_ascii=False),
        "factor_breakdown": json.dumps(factors, ensure_ascii=False),
    }


def main():
    matches = read_csv(PROCESSED / "matches.csv")
    contexts = load_context().get("matches", {})
    rows = []
    for match in matches:
        rows.append({
            "match_number": match["match_number"], "home_team": match["home_team"],
            "away_team": match["away_team"], **compute_analysis(match, matches, contexts),
        })
    fields = [
        "match_number", "home_team", "away_team", "lean_score", "lean_label", "confidence",
        "home_rating", "away_rating", "home_win_probability", "draw_probability",
        "away_win_probability", "model_summary", "environment_note", "pre_match_status",
        "pre_match_updated_at", "evidence_summary", "pre_match_sources", "factor_breakdown",
    ]
    write_csv(PROCESSED / "match_analysis.csv", rows, fields)
    print(json.dumps({"matches": len(rows), "output": str(PROCESSED / "match_analysis.csv")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
