#!/usr/bin/env python3
"""
Fetch World Cup 2026 results from football-data.org API
and update results.json automatically.

Requires: FOOTBALL_DATA_API_KEY environment variable.
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

API_KEY = os.environ.get("FOOTBALL_DATA_API_KEY", "")
API_BASE = "https://api.football-data.org/v4"
COMPETITION = "WC"  # FIFA World Cup (id: 2000)
RESULTS_FILE = Path(__file__).parent / "results.json"

# ── Mapping: our match IDs keyed by (homeCode, awayCode) ──────────────
# The app uses custom 3-letter codes. The API uses FIFA TLA codes.
# This map converts API team TLA → our app codes where they differ.
API_TLA_TO_APP_CODE = {
    # Teams whose API TLA differs from our code
    "RSA": "RSA",  # South Africa — same
    "KOR": "KOR",  # South Korea — same
    "MEX": "MEX",
    "CAN": "CAN",
    "QAT": "QAT",
    "SUI": "SUI",
    "BRA": "BRA",
    "HAI": "HAI",
    "SCO": "SCO",
    "MAR": "MAR",
    "USA": "USA",
    "AUS": "AUS",
    "PAR": "PAR",
    "GER": "GER",
    "CIV": "CIV",  # Ivory Coast
    "ECU": "ECU",
    "NED": "NED",
    "JPN": "JPN",
    "TUN": "TUN",
    "BEL": "BEL",
    "EGY": "EGY",
    "IRN": "IRN",
    "NZL": "NZL",
    "ESP": "ESP",
    "KSA": "KSA",
    "URU": "URU",
    "FRA": "FRA",
    "SEN": "SEN",
    "NOR": "NOR",
    "ARG": "ARG",
    "ALG": "ALG",
    "AUT": "AUT",
    "JOR": "JOR",
    "POR": "POR",
    "UZB": "UZB",
    "COL": "COL",
    "ENG": "ENG",
    "CRO": "CRO",
    "GHA": "GHA",
    "PAN": "PAN",
    "CPV": "CPV",  # Cape Verde
    # Playoff winners — update these when playoffs are decided
    # "???": "UPD",  # Playoff winner D (Group A)
    # "???": "UPA",  # Playoff winner A (Group B)
    # "???": "UPC",  # Playoff winner C (Group D)
    # "???": "UPB",  # Playoff winner B (Group F)
    # "???": "IC2",  # Intercontinental 2 (Group I)
    # "???": "IC1",  # Intercontinental 1 (Group K)
}

# All 72 group matches: (homeCode, awayCode) → match ID
# Plus knockout matches will be matched by stage + order
GROUP_MATCHES = {
    # Group A
    ("MEX", "RSA"): 1, ("KOR", "UPD"): 2,
    ("UPD", "RSA"): 3, ("MEX", "KOR"): 4,
    ("UPD", "MEX"): 5, ("RSA", "KOR"): 6,
    # Group B
    ("CAN", "UPA"): 7, ("QAT", "SUI"): 8,
    ("SUI", "UPA"): 9, ("CAN", "QAT"): 10,
    ("SUI", "CAN"): 11, ("UPA", "QAT"): 12,
    # Group C
    ("BRA", "MAR"): 13, ("HAI", "SCO"): 14,
    ("SCO", "MAR"): 15, ("BRA", "HAI"): 16,
    ("SCO", "BRA"): 17, ("MAR", "HAI"): 18,
    # Group D
    ("USA", "PAR"): 19, ("AUS", "UPC"): 20,
    ("USA", "AUS"): 21, ("UPC", "PAR"): 22,
    ("UPC", "USA"): 23, ("PAR", "AUS"): 24,
    # Group E
    ("GER", "CUR"): 25, ("CIV", "ECU"): 26,
    ("GER", "CIV"): 27, ("ECU", "CUR"): 28,
    ("ECU", "GER"): 29, ("CUR", "CIV"): 30,
    # Group F
    ("NED", "JPN"): 31, ("UPB", "TUN"): 32,
    ("NED", "UPB"): 33, ("TUN", "JPN"): 34,
    ("JPN", "UPB"): 35, ("TUN", "NED"): 36,
    # Group G
    ("BEL", "EGY"): 37, ("IRN", "NZL"): 38,
    ("BEL", "IRN"): 39, ("NZL", "EGY"): 40,
    ("EGY", "IRN"): 41, ("NZL", "BEL"): 42,
    # Group H
    ("ESP", "CPV"): 43, ("KSA", "URU"): 44,
    ("ESP", "KSA"): 45, ("URU", "CPV"): 46,
    ("CPV", "KSA"): 47, ("URU", "ESP"): 48,
    # Group I
    ("FRA", "SEN"): 49, ("IC2", "NOR"): 50,
    ("FRA", "IC2"): 51, ("NOR", "SEN"): 52,
    ("NOR", "FRA"): 53, ("SEN", "IC2"): 54,
    # Group J
    ("ARG", "ALG"): 55, ("AUT", "JOR"): 56,
    ("ARG", "AUT"): 57, ("JOR", "ALG"): 58,
    ("ALG", "AUT"): 59, ("JOR", "ARG"): 60,
    # Group K
    ("POR", "IC1"): 61, ("UZB", "COL"): 62,
    ("POR", "UZB"): 63, ("COL", "IC1"): 64,
    ("COL", "POR"): 65, ("IC1", "UZB"): 66,
    # Group L
    ("ENG", "CRO"): 67, ("GHA", "PAN"): 68,
    ("ENG", "GHA"): 69, ("PAN", "CRO"): 70,
    ("PAN", "ENG"): 71, ("CRO", "GHA"): 72,
}

# Knockout stage mapping by API stage name
KNOCKOUT_STAGES = {
    "LAST_32": list(range(73, 89)),      # 16 matches
    "LAST_16": list(range(89, 97)),       # 8 matches
    "QUARTER_FINALS": list(range(97, 101)),  # 4 matches
    "SEMI_FINALS": [101, 102],
    "THIRD_PLACE": [103],
    "FINAL": [104],
}


def api_get(endpoint):
    """Make authenticated GET request to football-data.org."""
    url = f"{API_BASE}{endpoint}"
    req = Request(url)
    req.add_header("X-Auth-Token", API_KEY)
    try:
        with urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode())
    except HTTPError as e:
        print(f"API error {e.code}: {e.reason}")
        if e.code == 429:
            print("Rate limited — try again in a minute.")
        return None
    except URLError as e:
        print(f"Network error: {e.reason}")
        return None


def convert_tla(api_tla):
    """Convert API team TLA to our app code."""
    return API_TLA_TO_APP_CODE.get(api_tla, api_tla)


def find_match_id(home_tla, away_tla, stage, stage_matches_seen):
    """Find our internal match ID for an API match."""
    home = convert_tla(home_tla)
    away = convert_tla(away_tla)

    # Group stage: exact matchup lookup
    key = (home, away)
    if key in GROUP_MATCHES:
        return GROUP_MATCHES[key]

    # Knockout: assign by stage in order of UTC date
    if stage in KNOCKOUT_STAGES:
        ids = KNOCKOUT_STAGES[stage]
        idx = stage_matches_seen.get(stage, 0)
        if idx < len(ids):
            stage_matches_seen[stage] = idx + 1
            return ids[idx]

    return None


def load_results():
    with open(RESULTS_FILE, "r") as f:
        return json.load(f)


def save_results(data):
    data["updated"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with open(RESULTS_FILE, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")


def fetch_and_update():
    if not API_KEY:
        print("Error: FOOTBALL_DATA_API_KEY not set.")
        sys.exit(1)

    print(f"Fetching World Cup matches from football-data.org...")
    resp = api_get(f"/competitions/{COMPETITION}/matches?status=FINISHED")
    if resp is None:
        sys.exit(1)

    api_matches = resp.get("matches", [])
    if not api_matches:
        print("No finished matches found.")
        return False

    # Sort by date for consistent knockout ordering
    api_matches.sort(key=lambda m: m["utcDate"])

    data = load_results()
    existing = {r["id"]: r for r in data["results"]}
    stage_matches_seen = {}
    new_count = 0
    updated_count = 0

    for m in api_matches:
        score = m.get("score", {})
        ft = score.get("fullTime", {})
        home_goals = ft.get("home")
        away_goals = ft.get("away")

        if home_goals is None or away_goals is None:
            continue

        home_tla = m.get("homeTeam", {}).get("tla", "")
        away_tla = m.get("awayTeam", {}).get("tla", "")
        stage = m.get("stage", "")

        match_id = find_match_id(home_tla, away_tla, stage, stage_matches_seen)
        if match_id is None:
            print(f"  ⚠ No mapping for {home_tla} vs {away_tla} (stage: {stage})")
            continue

        if match_id in existing:
            old = existing[match_id]
            if old["home"] == home_goals and old["away"] == away_goals:
                continue  # No change
            old["home"] = home_goals
            old["away"] = away_goals
            updated_count += 1
            print(f"  Updated #{match_id}: {home_tla} {home_goals}-{away_goals} {away_tla}")
        else:
            data["results"].append({
                "id": match_id,
                "home": home_goals,
                "away": away_goals,
            })
            new_count += 1
            print(f"  New #{match_id}: {home_tla} {home_goals}-{away_goals} {away_tla}")

    if new_count == 0 and updated_count == 0:
        print("No changes.")
        return False

    data["results"].sort(key=lambda r: r["id"])
    save_results(data)
    print(f"\nDone: {new_count} new, {updated_count} updated. "
          f"Total: {len(data['results'])} results.")
    return True


if __name__ == "__main__":
    changed = fetch_and_update()
    sys.exit(0 if changed else 0)
