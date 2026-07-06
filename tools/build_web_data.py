import csv
import json
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"
WEB = ROOT / "web"


def read_csv(name):
    with (PROCESSED / name).open("r", encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def read_json(name, fallback):
    path = PROCESSED / name
    if not path.exists():
        return fallback
    return json.loads(path.read_text(encoding="utf-8"))


def main():
    matches = read_csv("matches.csv")
    standings = read_csv("standings.csv")
    venues = read_csv("venues.csv")
    zhibo8 = read_csv("zhibo8_schedule.csv")
    crosscheck = read_csv("schedule_crosscheck_zhibo8.csv")
    analysis = read_csv("match_analysis.csv")
    knockout = read_json(
        "knockout_simulation.json",
        {"note": "", "third_place": [], "round32": [], "path": []},
    )

    zhibo8_by_id = {row["zhibo8_match_id"]: row for row in zhibo8}
    crosscheck_by_match = {row["match_number"]: row for row in crosscheck if row.get("match_number")}
    analysis_by_match = {row["match_number"]: row for row in analysis if row.get("match_number")}

    for match in matches:
        check = crosscheck_by_match.get(match["match_number"], {})
        match["crosscheck"] = check
        match["zhibo8"] = zhibo8_by_id.get(check.get("zhibo8_match_id", ""), {})
        match["analysis"] = analysis_by_match.get(match["match_number"], {})
        if match.get("stage") != "group-stage" and check.get("check_status") == "OK":
            match["display_home_team"] = check.get("zhibo8_home_team") or match.get("home_team", "")
            match["display_away_team"] = check.get("zhibo8_away_team") or match.get("away_team", "")
        else:
            match["display_home_team"] = match.get("home_team", "")
            match["display_away_team"] = match.get("away_team", "")

    standings_by_group = defaultdict(list)
    for row in standings:
        standings_by_group[row["group"]].append(row)

    payload = {
        "meta": {
            "title": "2026 世界杯观赛数据库",
            "match_count": len(matches),
            "team_count": 48,
            "venue_count": len(venues),
            "crosscheck_ok": sum(1 for row in crosscheck if row.get("check_status") == "OK"),
            "sources": [
                "TheStatsAPI fixtures",
                "ESPN scoreboard / standings",
                "直播吧 / 球迷宝数据",
            ],
        },
        "matches": matches,
        "standings": dict(standings_by_group),
        "knockout_simulation": knockout,
        "venues": venues,
    }

    WEB.mkdir(parents=True, exist_ok=True)
    (WEB / "data.js").write_text(
        "window.WC26_DATA = "
        + json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        + ";\n",
        encoding="utf-8",
    )
    print(json.dumps(payload["meta"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
