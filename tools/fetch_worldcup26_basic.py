import csv
import json
import sqlite3
import unicodedata
from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
RAW = DATA / "raw"
PROCESSED = DATA / "processed"

FIXTURES_JSON_URL = "https://www.thestatsapi.com/world-cup/data/fixtures.json"
FIXTURES_CSV_URL = "https://www.thestatsapi.com/world-cup/data/fixtures.csv"
ESPN_SCOREBOARD_URL = (
    "https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world/"
    "scoreboard?dates=20260611-20260719&limit=200"
)
ESPN_STANDINGS_URL = (
    "https://site.api.espn.com/apis/v2/sports/soccer/fifa.world/"
    "standings?season=2026"
)

BEIJING = timezone(timedelta(hours=8))

ALIASES = {
    "korea republic": "south korea",
    "turkiye": "turkiye",
    "turkiye": "turkiye",
    "türkiye": "turkiye",
    "cote d'ivoire": "cote divoire",
    "côte d'ivoire": "cote divoire",
    "cote divoire": "cote divoire",
    "ivory coast": "cote divoire",
    "curacao": "curacao",
    "curaçao": "curacao",
    "cabo verde": "cape verde",
    "cape verde": "cape verde",
    "congo dr": "congo dr",
    "dr congo": "congo dr",
    "bosnia and herzegovina": "bosnia herzegovina",
    "bosnia-herzegovina": "bosnia herzegovina",
    "ir iran": "iran",
}


def fetch_text(url):
    req = Request(url, headers={"User-Agent": "worldcup26-basic-data/1.0"})
    with urlopen(req, timeout=45) as response:
        return response.read().decode("utf-8")


def fetch_json(url):
    return json.loads(fetch_text(url))


def write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_text(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_csv(path, rows, fieldnames):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def normalize_name(name):
    if not name:
        return ""
    text = unicodedata.normalize("NFKD", name)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.lower().replace("&", "and")
    for ch in [".", ",", "-", "’", "`"]:
        text = text.replace(ch, " ")
    text = " ".join(text.replace("'", "").split())
    return ALIASES.get(text, text)


def parse_utc(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def canon_utc(value):
    return parse_utc(value).astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def iso_beijing(value):
    return parse_utc(value).astimezone(BEIJING).isoformat(timespec="minutes")


def stage_cn(stage):
    return {
        "group-stage": "小组赛",
        "round-of-32": "32强",
        "round-of-16": "16强",
        "quarter-finals": "四分之一决赛",
        "semi-finals": "半决赛",
        "third-place": "三四名决赛",
        "final": "决赛",
    }.get(stage, stage)


def group_from_note(note):
    if not note:
        return ""
    marker = "Group "
    if marker in note:
        return note.split(marker, 1)[1].strip()[:1]
    return ""


def build_espn_index(scoreboard):
    index = {}
    by_teamset = {}
    team_rows = {}
    event_rows = []

    for event in scoreboard.get("events", []):
        competition = event.get("competitions", [{}])[0]
        competitors = competition.get("competitors", [])
        by_side = {c.get("homeAway"): c for c in competitors}
        home = by_side.get("home", {})
        away = by_side.get("away", {})
        home_team = home.get("team", {})
        away_team = away.get("team", {})
        event_date = event.get("date", "")
        key = (
            canon_utc(event_date),
            frozenset(
                [
                    normalize_name(home_team.get("displayName") or home_team.get("name")),
                    normalize_name(away_team.get("displayName") or away_team.get("name")),
                ]
            ),
        )
        status_type = event.get("status", {}).get("type", {})
        links = event.get("links", [])
        summary_url = next((l.get("href") for l in links if "summary" in l.get("rel", [])), "")
        stats_url = next((l.get("href") for l in links if "stats" in l.get("rel", [])), "")
        row = {
            "espn_event_id": event.get("id", ""),
            "espn_uid": event.get("uid", ""),
            "espn_date_utc": event_date,
            "status_state": status_type.get("state", ""),
            "status_description": status_type.get("description", ""),
            "status_detail": status_type.get("detail", ""),
            "completed": status_type.get("completed", False),
            "home_score": home.get("score", ""),
            "away_score": away.get("score", ""),
            "attendance": competition.get("attendance", ""),
            "espn_home_team": home_team.get("displayName", ""),
            "espn_away_team": away_team.get("displayName", ""),
            "espn_home_team_id": home_team.get("id", ""),
            "espn_away_team_id": away_team.get("id", ""),
            "espn_summary_url": summary_url,
            "espn_stats_url": stats_url,
            "source": "ESPN scoreboard API",
        }
        index[key] = row
        by_teamset.setdefault(key[1], []).append(row)
        event_rows.append(row)

        for side in [home, away]:
            team = side.get("team", {})
            display = team.get("displayName") or team.get("name")
            if not display:
                continue
            team_rows[normalize_name(display)] = {
                "team": display,
                "espn_team_id": team.get("id", ""),
                "espn_uid": team.get("uid", ""),
                "abbreviation": team.get("abbreviation", ""),
                "short_name": team.get("shortDisplayName", ""),
                "logo": (team.get("logos") or [{}])[0].get("href", ""),
                "source": "ESPN scoreboard API",
            }

    return index, by_teamset, team_rows, event_rows


def extract_standings(standings):
    rows = []
    for child in standings.get("children", []):
        group_name = child.get("name", "")
        group_letter = group_name.replace("Group ", "").strip()
        entries = child.get("standings", {}).get("entries", [])
        for entry in entries:
            team = entry.get("team", {})
            note = entry.get("note", {})
            stats_map = {}
            for stat in entry.get("stats", []) or []:
                name = stat.get("name") or stat.get("abbreviation")
                if name:
                    stats_map[name] = stat.get("displayValue", stat.get("value", ""))
            rows.append(
                {
                    "group": group_letter,
                    "rank": note.get("rank", ""),
                    "team": team.get("displayName", ""),
                    "espn_team_id": team.get("id", ""),
                    "abbreviation": team.get("abbreviation", ""),
                    "played": stats_map.get("gamesPlayed", stats_map.get("GP", "")),
                    "wins": stats_map.get("wins", stats_map.get("W", "")),
                    "draws": stats_map.get("ties", stats_map.get("D", "")),
                    "losses": stats_map.get("losses", stats_map.get("L", "")),
                    "goals_for": stats_map.get("pointsFor", stats_map.get("F", "")),
                    "goals_against": stats_map.get("pointsAgainst", stats_map.get("A", "")),
                    "goal_difference": stats_map.get("pointDifferential", stats_map.get("GD", "")),
                    "points": stats_map.get("points", stats_map.get("P", "")),
                    "qualification_note": note.get("description", ""),
                    "source": "ESPN standings API",
                }
            )
    return rows


def main():
    RAW.mkdir(parents=True, exist_ok=True)
    PROCESSED.mkdir(parents=True, exist_ok=True)

    fixtures = fetch_json(FIXTURES_JSON_URL)
    fixtures_csv = fetch_text(FIXTURES_CSV_URL)
    scoreboard = fetch_json(ESPN_SCOREBOARD_URL)
    standings = fetch_json(ESPN_STANDINGS_URL)

    write_json(RAW / "thestatsapi_fixtures.json", fixtures)
    write_text(RAW / "thestatsapi_fixtures.csv", fixtures_csv)
    write_json(RAW / "espn_scoreboard_2026.json", scoreboard)
    write_json(RAW / "espn_standings_2026.json", standings)

    espn_index, espn_by_teamset, espn_teams, espn_events = build_espn_index(scoreboard)

    matches = []
    teams = {}
    groups = []

    for item in fixtures["fixtures"]:
        fixture_kickoff_utc = item["kickoffUtc"]
        kickoff_utc = fixture_kickoff_utc
        fixture_teams = [item.get("homeTeam", ""), item.get("awayTeam", "")]
        teamset = frozenset(normalize_name(t) for t in fixture_teams)
        key = (canon_utc(kickoff_utc), teamset)
        espn = espn_index.get(key, {})
        time_discrepancy_note = ""
        if not espn:
            fixture_dt = parse_utc(fixture_kickoff_utc)
            nearby = []
            for candidate in espn_by_teamset.get(teamset, []):
                candidate_dt = parse_utc(candidate["espn_date_utc"])
                if abs((candidate_dt - fixture_dt).total_seconds()) <= 7200:
                    nearby.append(candidate)
            if len(nearby) == 1:
                espn = nearby[0]
                kickoff_utc = canon_utc(espn["espn_date_utc"])
                time_discrepancy_note = (
                    f"Fixture source kickoff was {fixture_kickoff_utc}; "
                    f"ESPN/Zhibo8 aligned kickoff is {kickoff_utc}."
                )
        match = {
            "match_number": item.get("matchNumber"),
            "date_local": item.get("date"),
            "fixture_kickoff_utc": fixture_kickoff_utc,
            "kickoff_utc": kickoff_utc,
            "kickoff_beijing": iso_beijing(kickoff_utc),
            "stage": item.get("stage"),
            "stage_cn": stage_cn(item.get("stage")),
            "group": item.get("group") or "",
            "home_team": item.get("homeTeam"),
            "away_team": item.get("awayTeam"),
            "stadium": item.get("stadium"),
            "host_city": item.get("hostCity"),
            "status": espn.get("status_description", "Scheduled"),
            "status_state": espn.get("status_state", "pre"),
            "completed": espn.get("completed", False),
            "home_score": espn.get("home_score", ""),
            "away_score": espn.get("away_score", ""),
            "attendance": espn.get("attendance", ""),
            "espn_event_id": espn.get("espn_event_id", ""),
            "espn_summary_url": espn.get("espn_summary_url", ""),
            "espn_stats_url": espn.get("espn_stats_url", ""),
            "fixture_url": item.get("matchUrl", ""),
            "time_discrepancy_note": time_discrepancy_note,
            "source": "TheStatsAPI fixtures + ESPN scoreboard",
        }
        matches.append(match)

        if item.get("stage") == "group-stage":
            for side, team_name in [("home", item["homeTeam"]), ("away", item["awayTeam"])]:
                norm = normalize_name(team_name)
                meta = espn_teams.get(norm, {})
                teams[norm] = {
                    "team": team_name,
                    "group": item.get("group") or "",
                    "espn_team_id": meta.get("espn_team_id", ""),
                    "abbreviation": meta.get("abbreviation", ""),
                    "short_name": meta.get("short_name", ""),
                    "logo": meta.get("logo", ""),
                    "source": "TheStatsAPI fixtures + ESPN scoreboard",
                }
            groups.append(
                {
                    "group": item.get("group") or "",
                    "match_number": item.get("matchNumber"),
                    "home_team": item.get("homeTeam"),
                    "away_team": item.get("awayTeam"),
                    "kickoff_beijing": iso_beijing(kickoff_utc),
                }
            )

    venue_map = {}
    for match in matches:
        key = (match["stadium"], match["host_city"])
        venue = venue_map.setdefault(
            key,
            {
                "stadium": match["stadium"],
                "host_city": match["host_city"],
                "match_count": 0,
                "first_kickoff_beijing": match["kickoff_beijing"],
                "last_kickoff_beijing": match["kickoff_beijing"],
                "source": "TheStatsAPI fixtures",
            },
        )
        venue["match_count"] += 1
        venue["first_kickoff_beijing"] = min(venue["first_kickoff_beijing"], match["kickoff_beijing"])
        venue["last_kickoff_beijing"] = max(venue["last_kickoff_beijing"], match["kickoff_beijing"])

    standings_rows = extract_standings(standings)

    write_csv(
        PROCESSED / "matches.csv",
        matches,
        [
            "match_number",
            "date_local",
            "fixture_kickoff_utc",
            "kickoff_utc",
            "kickoff_beijing",
            "stage",
            "stage_cn",
            "group",
            "home_team",
            "away_team",
            "stadium",
            "host_city",
            "status",
            "status_state",
            "completed",
            "home_score",
            "away_score",
            "attendance",
            "espn_event_id",
            "espn_summary_url",
            "espn_stats_url",
            "fixture_url",
            "time_discrepancy_note",
            "source",
        ],
    )
    write_csv(
        PROCESSED / "teams.csv",
        sorted(teams.values(), key=lambda r: (r["group"], r["team"])),
        ["team", "group", "espn_team_id", "abbreviation", "short_name", "logo", "source"],
    )
    write_csv(
        PROCESSED / "group_matches.csv",
        sorted(groups, key=lambda r: (r["group"], int(r["match_number"]))),
        ["group", "match_number", "home_team", "away_team", "kickoff_beijing"],
    )
    write_csv(
        PROCESSED / "venues.csv",
        sorted(venue_map.values(), key=lambda r: r["stadium"]),
        ["stadium", "host_city", "match_count", "first_kickoff_beijing", "last_kickoff_beijing", "source"],
    )
    write_csv(
        PROCESSED / "standings.csv",
        sorted(standings_rows, key=lambda r: (r["group"], int(r["rank"] or 99), r["team"])),
        [
            "group",
            "rank",
            "team",
            "espn_team_id",
            "abbreviation",
            "played",
            "wins",
            "draws",
            "losses",
            "goals_for",
            "goals_against",
            "goal_difference",
            "points",
            "qualification_note",
            "source",
        ],
    )

    db_path = DATA / "worldcup26_basic.sqlite"
    if db_path.exists():
        db_path.unlink()
    conn = sqlite3.connect(db_path)
    for table_name, rows in {
        "matches": matches,
        "teams": sorted(teams.values(), key=lambda r: (r["group"], r["team"])),
        "group_matches": sorted(groups, key=lambda r: (r["group"], int(r["match_number"]))),
        "venues": sorted(venue_map.values(), key=lambda r: r["stadium"]),
        "standings": sorted(standings_rows, key=lambda r: (r["group"], int(r["rank"] or 99), r["team"])),
        "espn_events": espn_events,
    }.items():
        if not rows:
            continue
        fields = list(rows[0].keys())
        conn.execute(f"CREATE TABLE {table_name} ({', '.join(f'[{field}] TEXT' for field in fields)})")
        placeholders = ", ".join("?" for _ in fields)
        conn.executemany(
            f"INSERT INTO {table_name} ({', '.join(f'[{field}]' for field in fields)}) VALUES ({placeholders})",
            [[row.get(field, "") for field in fields] for row in rows],
        )
    conn.commit()
    conn.close()

    summary = {
        "fetched_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "matches": len(matches),
        "teams": len(teams),
        "venues": len(venue_map),
        "standings_rows": len(standings_rows),
        "raw_sources": {
            "fixtures": FIXTURES_JSON_URL,
            "espn_scoreboard": ESPN_SCOREBOARD_URL,
            "espn_standings": ESPN_STANDINGS_URL,
        },
        "outputs": [
            str(PROCESSED / "matches.csv"),
            str(PROCESSED / "teams.csv"),
            str(PROCESSED / "group_matches.csv"),
            str(PROCESSED / "venues.csv"),
            str(PROCESSED / "standings.csv"),
            str(db_path),
        ],
    }
    write_json(DATA / "fetch_summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
