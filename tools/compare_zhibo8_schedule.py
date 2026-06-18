import csv
import json
import sqlite3
from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
RAW = DATA / "raw"
PROCESSED = DATA / "processed"

BEIJING = timezone(timedelta(hours=8))
ZHIBO8_SCHEDULE_URL = (
    "https://stats.qiumibao.com/shuju/public/index.php?_url=/data/index&year=2026"
    "&type=%E8%B5%9B%E7%A8%8B&tab=%E8%B5%9B%E7%A8%8B&league_id=4"
    "&league=%E4%B8%96%E7%95%8C%E6%9D%AF"
)

TEAM_ZH = {
    "Algeria": "阿尔及利亚",
    "Argentina": "阿根廷",
    "Australia": "澳大利亚",
    "Austria": "奥地利",
    "Belgium": "比利时",
    "Bosnia and Herzegovina": "波黑",
    "Brazil": "巴西",
    "Cabo Verde": "佛得角",
    "Canada": "加拿大",
    "Colombia": "哥伦比亚",
    "Congo DR": "民主刚果",
    "Cote d'Ivoire": "科特迪瓦",
    "Croatia": "克罗地亚",
    "Curacao": "库拉索",
    "Czechia": "捷克",
    "Ecuador": "厄瓜多尔",
    "Egypt": "埃及",
    "England": "英格兰",
    "France": "法国",
    "Germany": "德国",
    "Ghana": "加纳",
    "Haiti": "海地",
    "IR Iran": "伊朗",
    "Iraq": "伊拉克",
    "Japan": "日本",
    "Jordan": "约旦",
    "Korea Republic": "韩国",
    "Mexico": "墨西哥",
    "Morocco": "摩洛哥",
    "Netherlands": "荷兰",
    "New Zealand": "新西兰",
    "Norway": "挪威",
    "Panama": "巴拿马",
    "Paraguay": "巴拉圭",
    "Portugal": "葡萄牙",
    "Qatar": "卡塔尔",
    "Saudi Arabia": "沙特",
    "Scotland": "苏格兰",
    "Senegal": "塞内加尔",
    "South Africa": "南非",
    "Spain": "西班牙",
    "Sweden": "瑞典",
    "Switzerland": "瑞士",
    "Tunisia": "突尼斯",
    "Turkiye": "土耳其",
    "United States": "美国",
    "Uruguay": "乌拉圭",
    "Uzbekistan": "乌兹别克斯坦",
}


def read_csv(path):
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def write_csv(path, rows, fieldnames):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def fetch_text(url):
    req = Request(
        url,
        headers={
            "User-Agent": "worldcup26-data-updater/1.0",
            "Accept": "application/json,text/html,*/*",
        },
    )
    with urlopen(req, timeout=45) as response:
        return response.read().decode("utf-8")


def load_zhibo8_payload():
    RAW.mkdir(parents=True, exist_ok=True)
    try:
        text = fetch_text(ZHIBO8_SCHEDULE_URL)
        (RAW / "zhibo8_worldcup_2026_schedule.json").write_text(text, encoding="utf-8")
        return json.loads(text)
    except Exception as exc:
        cache = RAW / "zhibo8_worldcup_2026_schedule.json"
        if cache.exists():
            print(f"Zhibo8 fetch failed, using cached file: {exc}")
            return json.loads(cache.read_text(encoding="utf-8-sig"))
        raise


def beijing_from_timestamp(value):
    return datetime.fromtimestamp(int(value), timezone.utc).astimezone(BEIJING).isoformat(timespec="minutes")


def flatten_zhibo8():
    payload = load_zhibo8_payload()
    rows = []
    for group in payload.get("data", []):
        for item in group.get("list", []):
            rows.append(
                {
                    "zhibo8_match_id": item.get("saishi_id", ""),
                    "kickoff_beijing": beijing_from_timestamp(item["timestamp"]) if item.get("timestamp") else "",
                    "display_time": item.get("时间", ""),
                    "rounds": item.get("rounds", ""),
                    "home_team_zh": item.get("主队", ""),
                    "away_team_zh": item.get("客队", ""),
                    "home_team_id": item.get("homeId", ""),
                    "away_team_id": item.get("guestId", ""),
                    "score": item.get("比分", ""),
                    "state_cn": item.get("state_cn", ""),
                    "is_finish": item.get("is_finish", ""),
                    "match_page": "https://www.zhibo8.cc/" + item.get("内页", "").lstrip("/"),
                    "source": "Zhibo8 / Qiumibao stats API",
                }
            )
    return rows


def compare():
    matches = read_csv(PROCESSED / "matches.csv")
    zhibo_rows = flatten_zhibo8()
    zhibo_by_key = {
        (row["kickoff_beijing"], row["home_team_zh"], row["away_team_zh"]): row
        for row in zhibo_rows
    }
    zhibo_by_time = {}
    for row in zhibo_rows:
        zhibo_by_time.setdefault(row["kickoff_beijing"], []).append(row)
    used_zhibo8_ids = set()

    comparison = []
    for match in matches:
        home_zh = TEAM_ZH.get(match["home_team"], "")
        away_zh = TEAM_ZH.get(match["away_team"], "")
        z = None
        if home_zh and away_zh:
            z = zhibo_by_key.get((match["kickoff_beijing"], home_zh, away_zh))
        if not z and len(zhibo_by_time.get(match["kickoff_beijing"], [])) == 1:
            z = zhibo_by_time[match["kickoff_beijing"]][0]
        if z:
            used_zhibo8_ids.add(z["zhibo8_match_id"])
            expected_score = ""
            if (
                match.get("completed") == "True"
                and match.get("home_score") != ""
                and match.get("away_score") != ""
            ):
                expected_score = f"{match['home_score']}-{match['away_score']}"
            issues = []
            if home_zh and z["home_team_zh"] != home_zh:
                issues.append(f"主队不同: expected {home_zh}, zhibo8 {z['home_team_zh']}")
            if away_zh and z["away_team_zh"] != away_zh:
                issues.append(f"客队不同: expected {away_zh}, zhibo8 {z['away_team_zh']}")
            if expected_score and z["score"] not in ("VS", expected_score):
                issues.append(f"比分不同: expected {expected_score}, zhibo8 {z['score']}")
            comparison.append(
                {
                    "match_number": match["match_number"],
                    "kickoff_beijing": match["kickoff_beijing"],
                    "home_team": match["home_team"],
                    "away_team": match["away_team"],
                    "home_team_zh_expected": home_zh,
                    "away_team_zh_expected": away_zh,
                    "zhibo8_match_id": z["zhibo8_match_id"],
                    "zhibo8_home_team": z["home_team_zh"],
                    "zhibo8_away_team": z["away_team_zh"],
                    "local_score": expected_score,
                    "zhibo8_score": z["score"],
                    "zhibo8_state": z["state_cn"],
                    "check_status": "OK" if not issues else "DIFF",
                    "issues": "; ".join(issues),
                }
            )
        else:
            comparison.append(
                {
                    "match_number": match["match_number"],
                    "kickoff_beijing": match["kickoff_beijing"],
                    "home_team": match["home_team"],
                    "away_team": match["away_team"],
                    "check_status": "MISSING_IN_ZHIBO8",
                    "issues": "直播吧没有同一北京时间的比赛",
                }
            )

    extra = [
        {
            "match_number": "",
            "kickoff_beijing": z["kickoff_beijing"],
            "home_team": "",
            "away_team": "",
            "zhibo8_match_id": z["zhibo8_match_id"],
            "zhibo8_home_team": z["home_team_zh"],
            "zhibo8_away_team": z["away_team_zh"],
            "zhibo8_score": z["score"],
            "zhibo8_state": z["state_cn"],
            "check_status": "EXTRA_IN_ZHIBO8",
            "issues": "本地赛程没有同一北京时间的比赛",
        }
        for z in zhibo_rows
        if z["zhibo8_match_id"] not in used_zhibo8_ids
    ]
    comparison.extend(extra)

    write_csv(
        PROCESSED / "zhibo8_schedule.csv",
        zhibo_rows,
        [
            "zhibo8_match_id",
            "kickoff_beijing",
            "display_time",
            "rounds",
            "home_team_zh",
            "away_team_zh",
            "home_team_id",
            "away_team_id",
            "score",
            "state_cn",
            "is_finish",
            "match_page",
            "source",
        ],
    )
    write_csv(
        PROCESSED / "schedule_crosscheck_zhibo8.csv",
        comparison,
        [
            "match_number",
            "kickoff_beijing",
            "home_team",
            "away_team",
            "home_team_zh_expected",
            "away_team_zh_expected",
            "zhibo8_match_id",
            "zhibo8_home_team",
            "zhibo8_away_team",
            "local_score",
            "zhibo8_score",
            "zhibo8_state",
            "check_status",
            "issues",
        ],
    )

    db_path = DATA / "worldcup26_basic.sqlite"
    if db_path.exists():
        conn = sqlite3.connect(db_path)
        for table_name, rows in {
            "zhibo8_schedule": zhibo_rows,
            "schedule_crosscheck_zhibo8": comparison,
        }.items():
            conn.execute(f"DROP TABLE IF EXISTS {table_name}")
            if rows:
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
        "local_matches": len(matches),
        "zhibo8_matches": len(zhibo_rows),
        "ok": sum(1 for row in comparison if row["check_status"] == "OK"),
        "diff": sum(1 for row in comparison if row["check_status"] == "DIFF"),
        "missing_in_zhibo8": sum(1 for row in comparison if row["check_status"] == "MISSING_IN_ZHIBO8"),
        "extra_in_zhibo8": sum(1 for row in comparison if row["check_status"] == "EXTRA_IN_ZHIBO8"),
    }
    (DATA / "zhibo8_crosscheck_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    compare()
