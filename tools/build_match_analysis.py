import csv
import json
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"

TEAM_RATINGS = {
    "Argentina": 94,
    "France": 93,
    "Spain": 91,
    "England": 90,
    "Brazil": 89,
    "Portugal": 88,
    "Germany": 87,
    "Netherlands": 86,
    "Belgium": 84,
    "Uruguay": 83,
    "Croatia": 82,
    "Morocco": 81,
    "Colombia": 80,
    "Switzerland": 78,
    "United States": 77,
    "Japan": 77,
    "Austria": 76,
    "Sweden": 75,
    "Norway": 75,
    "Korea Republic": 74,
    "Senegal": 74,
    "Ecuador": 73,
    "Turkiye": 73,
    "Cote d'Ivoire": 72,
    "Australia": 72,
    "Canada": 71,
    "Czechia": 71,
    "Paraguay": 70,
    "Scotland": 70,
    "IR Iran": 69,
    "Saudi Arabia": 68,
    "Egypt": 68,
    "Ghana": 67,
    "Algeria": 67,
    "Bosnia and Herzegovina": 66,
    "Tunisia": 66,
    "South Africa": 65,
    "Qatar": 64,
    "Congo DR": 64,
    "Uzbekistan": 63,
    "Iraq": 62,
    "Panama": 62,
    "Cabo Verde": 61,
    "Jordan": 60,
    "New Zealand": 60,
    "Curacao": 59,
    "Haiti": 58,
    "Mexico": 76,
}

HOST_COUNTRY = {
    "mexico-city": "Mexico",
    "guadalajara": "Mexico",
    "monterrey": "Mexico",
    "toronto": "Canada",
    "vancouver": "Canada",
    "los-angeles": "United States",
    "san-francisco": "United States",
    "seattle": "United States",
    "houston": "United States",
    "dallas": "United States",
    "atlanta": "United States",
    "miami": "United States",
    "kansas-city": "United States",
    "boston": "United States",
    "new-york": "United States",
    "philadelphia": "United States",
}

ALTITUDE_BONUS = {
    "mexico-city": 2,
    "guadalajara": 1,
}

VENUE_TIMEZONES = {
    "mexico-city": "America/Mexico_City",
    "guadalajara": "America/Mexico_City",
    "monterrey": "America/Monterrey",
    "toronto": "America/Toronto",
    "vancouver": "America/Vancouver",
    "los-angeles": "America/Los_Angeles",
    "san-francisco": "America/Los_Angeles",
    "seattle": "America/Los_Angeles",
    "houston": "America/Chicago",
    "dallas": "America/Chicago",
    "atlanta": "America/New_York",
    "miami": "America/New_York",
    "kansas-city": "America/Chicago",
    "boston": "America/New_York",
    "new-york": "America/New_York",
    "philadelphia": "America/New_York",
}

VENUE_HEAT_PROFILE = {
    "miami": {"risk": 9, "note": "高温高湿"},
    "houston": {"risk": 9, "note": "高温高湿，消耗大"},
    "dallas": {"risk": 8, "note": "内陆高温风险"},
    "kansas-city": {"risk": 7, "note": "午后炎热风险"},
    "atlanta": {"risk": 7, "note": "湿热风险"},
    "philadelphia": {"risk": 6, "note": "午后热负荷"},
    "new-york": {"risk": 6, "note": "午后热负荷"},
    "boston": {"risk": 5, "note": "夏季午后热负荷"},
    "los-angeles": {"risk": 5, "note": "日照与干热"},
    "monterrey": {"risk": 8, "note": "墨西哥北部炎热"},
    "guadalajara": {"risk": 6, "note": "高原日照"},
    "mexico-city": {"risk": 5, "note": "高原日照"},
    "toronto": {"risk": 4, "note": "热负荷中等"},
    "vancouver": {"risk": 2, "note": "气候温和"},
    "seattle": {"risk": 3, "note": "气候相对温和"},
    "san-francisco": {"risk": 2, "note": "湾区气候温和"},
}

TEAM_HEAT_ADAPTATION = {
    "Mexico": 8,
    "South Africa": 8,
    "Brazil": 8,
    "Argentina": 7,
    "Uruguay": 7,
    "Colombia": 8,
    "Ecuador": 8,
    "Paraguay": 8,
    "Cote d'Ivoire": 9,
    "Senegal": 9,
    "Ghana": 9,
    "Morocco": 8,
    "Tunisia": 8,
    "Algeria": 8,
    "Egypt": 8,
    "Congo DR": 9,
    "Cabo Verde": 8,
    "Haiti": 9,
    "Panama": 9,
    "Curacao": 9,
    "Qatar": 9,
    "Saudi Arabia": 9,
    "IR Iran": 7,
    "Iraq": 9,
    "Australia": 7,
    "Japan": 6,
    "Korea Republic": 6,
    "United States": 6,
    "Canada": 4,
    "England": 4,
    "Scotland": 4,
    "Norway": 4,
    "Sweden": 4,
    "Germany": 5,
    "Netherlands": 5,
    "Belgium": 5,
    "France": 6,
    "Spain": 7,
    "Portugal": 7,
    "Croatia": 6,
    "Switzerland": 5,
    "Austria": 5,
    "Czechia": 5,
    "Bosnia and Herzegovina": 5,
    "Turkiye": 7,
    "New Zealand": 5,
    "Uzbekistan": 7,
    "Jordan": 9,
}


def read_csv(path):
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def write_csv(path, rows, fieldnames):
    with path.open("w", newline="", encoding="utf-8-sig") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def is_placeholder(team):
    markers = ["Group ", "Winner Match", "Loser Match", "third place", "runners-up", "winners"]
    return any(marker in team for marker in markers)


def clamp(value, low=-100, high=100):
    return max(low, min(high, value))


def stage_profile(stage):
    knockout = stage != "group-stage"
    if knockout:
        return {
            "hard_strength": 30,
            "tactical_matchup": 20,
            "form_psychology": 16,
            "stability": 13,
            "fitness_injuries": 9,
            "set_pieces": 6,
            "randomness": 6,
        }
    return {
        "hard_strength": 35,
        "tactical_system": 17,
        "depth_rotation": 13,
        "stability": 12,
        "form_psychology": 8,
        "environment_schedule": 10,
        "randomness": 5,
    }


def team_rating(team):
    if is_placeholder(team):
        return None
    return TEAM_RATINGS.get(team)


def rating_delta(home, away):
    home_rating = team_rating(home)
    away_rating = team_rating(away)
    if home_rating is None or away_rating is None:
        return None, home_rating, away_rating
    return home_rating - away_rating, home_rating, away_rating


def host_adjustment(match):
    host = HOST_COUNTRY.get(match["host_city"])
    if not host:
        return 0
    if match["home_team"] == host:
        return 5
    if match["away_team"] == host:
        return -5
    return 0


def environment_adjustment(match):
    bonus = ALTITUDE_BONUS.get(match["host_city"], 0)
    if not bonus:
        return 0
    acclimated = {"Mexico", "Ecuador", "Colombia", "Bolivia", "Peru"}
    value = 0
    if match["home_team"] in acclimated:
        value += bonus
    if match["away_team"] in acclimated:
        value -= bonus
    return value


def local_kickoff_hour(match):
    tz_name = VENUE_TIMEZONES.get(match["host_city"])
    if not tz_name or not match.get("kickoff_utc"):
        return None
    value = match["kickoff_utc"].replace("Z", "+00:00")
    return datetime.fromisoformat(value).astimezone(ZoneInfo(tz_name)).hour


def heat_pressure(match):
    hour = local_kickoff_hour(match)
    profile = VENUE_HEAT_PROFILE.get(match["host_city"], {"risk": 0, "note": ""})
    if hour is None:
        return 0, "当地开球时间待补充"

    if 12 <= hour <= 17:
        time_factor = 1.0
    elif 10 <= hour < 12 or 18 <= hour <= 19:
        time_factor = 0.45
    else:
        time_factor = 0.0

    pressure = round(profile["risk"] * time_factor, 1)
    if pressure >= 7:
        level = "高"
    elif pressure >= 4:
        level = "中"
    elif pressure > 0:
        level = "低"
    else:
        level = "低"

    note = f"{level}热负荷：当地{hour:02d}:00开球，{profile['note'] or '气温影响有限'}"
    return pressure, note


def heat_adaptation_adjustment(match):
    pressure, note = heat_pressure(match)
    if pressure <= 0:
        return 0, note

    home_adapt = TEAM_HEAT_ADAPTATION.get(match["home_team"], 5)
    away_adapt = TEAM_HEAT_ADAPTATION.get(match["away_team"], 5)
    adaptation_delta = home_adapt - away_adapt
    value = adaptation_delta * pressure * 0.42
    value = clamp(value, -12, 12)
    if abs(value) < 0.4:
        value = 0
    return value, note


def compute_lean(match):
    delta, home_rating, away_rating = rating_delta(match["home_team"], match["away_team"])
    if delta is None:
        return {
            "lean_score": 0,
            "lean_label": "待定",
            "confidence": "低",
            "home_rating": home_rating or "",
            "away_rating": away_rating or "",
            "model_summary": "淘汰赛对阵或球队尚未确定，暂设为 0。",
            "environment_note": "球队尚未确定，暂不计算热负荷适应差异。",
            "factor_breakdown": json.dumps([], ensure_ascii=False),
        }

    profile = stage_profile(match["stage"])
    stage_is_knockout = match["stage"] != "group-stage"

    hard = delta * (profile["hard_strength"] / 35) * 1.7
    stability = delta * (profile.get("stability", 0) / 35) * 0.55
    tactical = delta * (profile.get("tactical_matchup", profile.get("tactical_system", 0)) / 35) * 0.5
    depth = delta * (profile.get("depth_rotation", profile.get("fitness_injuries", 0)) / 35) * 0.45
    host = host_adjustment(match)
    env = environment_adjustment(match)
    heat, heat_note = heat_adaptation_adjustment(match)

    if stage_is_knockout:
        raw = hard + tactical + stability + depth + host * 0.6 + heat * 0.8
    else:
        raw = hard + tactical + stability + depth + host + env + heat

    lean = int(round(clamp(raw, -96, 96)))
    abs_lean = abs(lean)
    if abs_lean >= 55:
        confidence = "高"
    elif abs_lean >= 25:
        confidence = "中"
    else:
        confidence = "低"

    if lean > 10:
        label = f"倾向 {match['home_team']}"
    elif lean < -10:
        label = f"倾向 {match['away_team']}"
    else:
        label = "接近均势"

    factors = [
        {"factor": "硬实力差", "value": round(hard, 1)},
        {"factor": "战术/稳定性", "value": round(tactical + stability, 1)},
        {"factor": "阵容体能", "value": round(depth, 1)},
        {"factor": "主场/海拔", "value": round(host + env, 1)},
        {"factor": "高温/适应", "value": round(heat, 1)},
    ]
    summary = (
        f"{match['home_team']} {home_rating} vs {match['away_team']} {away_rating}；"
        f"模型按{'淘汰赛' if stage_is_knockout else '小组赛'}权重折算；{heat_note}。"
    )
    return {
        "lean_score": lean,
        "lean_label": label,
        "confidence": confidence,
        "home_rating": home_rating,
        "away_rating": away_rating,
        "model_summary": summary,
        "environment_note": heat_note,
        "factor_breakdown": json.dumps(factors, ensure_ascii=False),
    }


def main():
    matches = read_csv(PROCESSED / "matches.csv")
    rows = []
    for match in matches:
        analysis = compute_lean(match)
        rows.append(
            {
                "match_number": match["match_number"],
                "home_team": match["home_team"],
                "away_team": match["away_team"],
                **analysis,
            }
        )

    write_csv(
        PROCESSED / "match_analysis.csv",
        rows,
        [
            "match_number",
            "home_team",
            "away_team",
            "lean_score",
            "lean_label",
            "confidence",
            "home_rating",
            "away_rating",
            "model_summary",
            "environment_note",
            "factor_breakdown",
        ],
    )
    print(json.dumps({"matches": len(rows), "output": str(PROCESSED / "match_analysis.csv")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
