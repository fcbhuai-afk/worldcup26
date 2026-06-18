import csv
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"

ROUND32 = [
    (73, "A2", "B2"),
    (74, "C1", "F2"),
    (75, "E1", "A3/B3/C3/D3/F3"),
    (76, "F1", "C2"),
    (77, "I1", "C3/D3/F3/G3/H3"),
    (78, "E2", "I2"),
    (79, "A1", "C3/E3/F3/H3/I3"),
    (80, "L1", "E3/H3/I3/J3/K3"),
    (81, "D1", "B3/E3/F3/I3/J3"),
    (82, "G1", "A3/E3/H3/I3/J3"),
    (83, "K2", "L2"),
    (84, "H1", "J2"),
    (85, "B1", "E3/F3/G3/I3/J3"),
    (86, "J1", "H2"),
    (87, "K1", "D3/E3/I3/J3/L3"),
    (88, "D2", "G2"),
]

BRACKET_PATH = [
    (89, "73胜者", "75胜者"),
    (90, "74胜者", "77胜者"),
    (91, "76胜者", "78胜者"),
    (92, "79胜者", "80胜者"),
    (93, "83胜者", "84胜者"),
    (94, "81胜者", "82胜者"),
    (95, "86胜者", "88胜者"),
    (96, "85胜者", "87胜者"),
    (97, "89胜者", "90胜者"),
    (98, "93胜者", "94胜者"),
    (99, "91胜者", "92胜者"),
    (100, "95胜者", "96胜者"),
    (101, "97胜者", "98胜者"),
    (102, "99胜者", "100胜者"),
    (103, "101负者", "102负者"),
    (104, "101胜者", "102胜者"),
]


def read_csv(name):
    with (PROCESSED / name).open("r", encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def write_csv(name, rows, fieldnames):
    with (PROCESSED / name).open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def to_int(value):
    try:
        return int(str(value).replace("+", ""))
    except (TypeError, ValueError):
        return 0


def row_sort_key(row):
    return (
        -to_int(row["points"]),
        -to_int(row["goal_difference"]),
        -to_int(row["goals_for"]),
        to_int(row["played"]),
        row["group"],
    )


def team_label(row):
    return f"{row['team']} ({row['points']}分, 净胜{row['goal_difference']})"


def group_rankings(standings):
    by_group = {}
    for row in standings:
        by_group.setdefault(row["group"], []).append(row)
    for group, rows in by_group.items():
        by_group[group] = sorted(rows, key=lambda r: to_int(r["rank"] or 99))
    return by_group


def select_third_teams(by_group):
    third_rows = []
    for group, rows in by_group.items():
        if len(rows) >= 3:
            third_rows.append(rows[2])
    ordered = sorted(third_rows, key=row_sort_key)
    advancing = ordered[:8]
    return ordered, {row["group"]: row for row in advancing}


def resolve_direct(token, by_group):
    group = token[0]
    rank = int(token[1])
    rows = by_group.get(group, [])
    if len(rows) >= rank:
        row = rows[rank - 1]
        return row["team"], group, token, team_label(row)
    return "待定", group, token, "待定"


def resolve_third(pool_token, available_thirds, used_groups):
    groups = [item[0] for item in pool_token.split("/")]
    candidates = [
        row
        for group, row in available_thirds.items()
        if group in groups and group not in used_groups
    ]
    if not candidates:
        return "待定第三名", "", pool_token, pool_token
    chosen = sorted(candidates, key=row_sort_key)[0]
    used_groups.add(chosen["group"])
    return chosen["team"], chosen["group"], f"{chosen['group']}3", team_label(chosen)


def resolve_slot(token, by_group, available_thirds, used_groups):
    if "/" in token:
        return resolve_third(token, available_thirds, used_groups)
    return resolve_direct(token, by_group)


def main():
    standings = read_csv("standings.csv")
    matches = {to_int(row["match_number"]): row for row in read_csv("matches.csv")}
    by_group = group_rankings(standings)
    third_rankings, available_thirds = select_third_teams(by_group)

    used_third_groups = set()
    round32_rows = []
    for number, left_token, right_token in ROUND32:
        left_team, left_group, left_source, left_detail = resolve_slot(
            left_token, by_group, available_thirds, used_third_groups
        )
        right_team, right_group, right_source, right_detail = resolve_slot(
            right_token, by_group, available_thirds, used_third_groups
        )
        match = matches.get(number, {})
        round32_rows.append(
            {
                "match_number": number,
                "round": "32强",
                "kickoff_beijing": match.get("kickoff_beijing", ""),
                "stadium": match.get("stadium", ""),
                "host_city": match.get("host_city", ""),
                "left_rule": left_token,
                "right_rule": right_token,
                "left_source": left_source,
                "right_source": right_source,
                "left_group": left_group,
                "right_group": right_group,
                "left_team": left_team,
                "right_team": right_team,
                "left_detail": left_detail,
                "right_detail": right_detail,
            }
        )

    path_rows = []
    for number, left, right in BRACKET_PATH:
        match = matches.get(number, {})
        if 89 <= number <= 96:
            round_name = "16强"
        elif 97 <= number <= 100:
            round_name = "1/4决赛"
        elif 101 <= number <= 102:
            round_name = "半决赛"
        elif number == 103:
            round_name = "三四名决赛"
        else:
            round_name = "决赛"
        path_rows.append(
            {
                "match_number": number,
                "round": round_name,
                "kickoff_beijing": match.get("kickoff_beijing", ""),
                "stadium": match.get("stadium", ""),
                "host_city": match.get("host_city", ""),
                "left_team": left,
                "right_team": right,
            }
        )

    third_rows = []
    advancing_groups = set(available_thirds)
    for index, row in enumerate(third_rankings, 1):
        third_rows.append(
            {
                "rank": index,
                "group": row["group"],
                "team": row["team"],
                "played": row["played"],
                "points": row["points"],
                "goal_difference": row["goal_difference"],
                "goals_for": row["goals_for"],
                "status": "晋级区" if row["group"] in advancing_groups else "淘汰区",
            }
        )

    write_csv(
        "knockout_round32_simulation.csv",
        round32_rows,
        [
            "match_number",
            "round",
            "kickoff_beijing",
            "stadium",
            "host_city",
            "left_rule",
            "right_rule",
            "left_source",
            "right_source",
            "left_group",
            "right_group",
            "left_team",
            "right_team",
            "left_detail",
            "right_detail",
        ],
    )
    write_csv(
        "third_place_snapshot.csv",
        third_rows,
        ["rank", "group", "team", "played", "points", "goal_difference", "goals_for", "status"],
    )
    write_csv(
        "knockout_path_simulation.csv",
        path_rows,
        ["match_number", "round", "kickoff_beijing", "stadium", "host_city", "left_team", "right_team"],
    )

    payload = {
        "note": "按当前 ESPN 积分榜即时推演；小组赛未完成时，未赛小组的0场0分会参与第三名临时排序，最终官方分配可能变化。",
        "third_place": third_rows,
        "round32": round32_rows,
        "path": path_rows,
    }
    (PROCESSED / "knockout_simulation.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps({"round32": len(round32_rows), "third_place": len(third_rows)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
