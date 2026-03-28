#!/usr/bin/env python3
"""
Fetch live match data from LiveScore API (RapidAPI) and update results.json.

Usage:
  python3 fetch_live.py              # One-shot fetch
  python3 fetch_live.py --watch      # Poll every 2 min while match is live
  python3 fetch_live.py --test       # Test with any live match right now

Requires: RAPIDAPI_KEY environment variable (or .env file).
"""

import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

SCRIPT_DIR = Path(__file__).parent
RESULTS_FILE = SCRIPT_DIR / "results.json"
ENV_FILE = SCRIPT_DIR / ".env"

# LiveScore6 API on RapidAPI
API_HOST = "livescore6.p.rapidapi.com"
API_BASE = f"https://{API_HOST}"

# ── Match configuration ─────────────────────────────────────
# Map LiveScore Eid → our app match ID
WATCHED_MATCHES = {
    "1757983": 900,  # Argentina vs Zambia (31/3/2026 23:15 ART)
}

# Incident types in LiveScore API
IT_GOAL = {36, 37}         # Regular goal
IT_OWN_GOAL = {34}         # Own goal
IT_PENALTY_GOAL = {39}     # Penalty scored
IT_RED_CARD = {17, 45}     # Red card, second yellow → red
IT_YELLOW_CARD = {43}      # Yellow card

# Period mapping: Epr value → our status code
PERIOD_MAP = {
    1: "1H",   # First half
    2: "HT",   # Half-time (between periods)
    3: "2H",   # Second half
    4: "ET",   # Extra time
    5: "PEN",  # Penalties
    6: "FT",   # Full time
}


def load_api_key():
    """Load API key from env or .env file."""
    key = os.environ.get("RAPIDAPI_KEY", "")
    if not key and ENV_FILE.exists():
        for line in ENV_FILE.read_text().splitlines():
            if line.startswith("RAPIDAPI_KEY="):
                key = line.split("=", 1)[1].strip().strip("'\"")
                break
    return key


def api_get(endpoint, api_key):
    """Make authenticated GET to LiveScore API."""
    url = f"{API_BASE}{endpoint}"
    req = Request(url)
    req.add_header("X-RapidAPI-Host", API_HOST)
    req.add_header("X-RapidAPI-Key", api_key)
    try:
        with urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode())
    except HTTPError as e:
        print(f"  API error {e.code}: {e.reason}")
        return None
    except URLError as e:
        print(f"  Network error: {e.reason}")
        return None


def fetch_live_matches(api_key):
    """Fetch all live soccer matches."""
    data = api_get("/matches/v2/list-live?Category=soccer", api_key)
    if not data:
        return []

    matches = []
    for stage in data.get("Stages", []):
        for ev in stage.get("Events", []):
            matches.append({
                "eid": ev.get("Eid", ""),
                "home_name": ev.get("T1", [{}])[0].get("Nm", "?") if ev.get("T1") else "?",
                "away_name": ev.get("T2", [{}])[0].get("Nm", "?") if ev.get("T2") else "?",
                "home_score": int(ev.get("Tr1", 0)),
                "away_score": int(ev.get("Tr2", 0)),
                "status_text": ev.get("Eps", ""),
                "period": int(ev.get("Epr", 0)),
                "league": stage.get("Snm", ""),
            })
    return matches


def fetch_incidents(eid, api_key):
    """Fetch match incidents (goals, cards)."""
    data = api_get(f"/matches/v2/get-incidents?Eid={eid}&Category=soccer", api_key)
    if not data:
        return [], []

    goals = []
    red_cards = []

    incs = data.get("Incs", {})
    for period_key, events in incs.items():
        for ev in events:
            it = ev.get("IT", 0)
            player = ev.get("Pn", "Unknown")
            minute = ev.get("Min", 0)
            side = ev.get("Nm", 0)  # 1=home, 2=away

            if it in IT_GOAL or it in IT_PENALTY_GOAL:
                goal = {
                    "player": player,
                    "minute": minute,
                    "team": "__HOME__" if side == 1 else "__AWAY__",
                }
                if it in IT_PENALTY_GOAL:
                    goal["pen"] = True
                goals.append(goal)

            elif it in IT_OWN_GOAL:
                goals.append({
                    "player": player,
                    "minute": minute,
                    "team": "__HOME__" if side == 1 else "__AWAY__",
                    "og": True,
                })

            elif it in IT_RED_CARD:
                side_label = "HOME" if side == 1 else "AWAY"
                red_cards.append(f"{player} ({side_label}) {minute}'")

    goals.sort(key=lambda g: g["minute"])
    return goals, red_cards


def parse_minute(status_text):
    """Extract minute number from status like '45+2\'' or '78\''."""
    s = status_text.replace("'", "").strip()
    if "+" in s:
        parts = s.split("+")
        try:
            return int(parts[0]) + int(parts[1])
        except ValueError:
            pass
    try:
        return int(s)
    except ValueError:
        return None


def map_status(period, status_text):
    """Map LiveScore period/status to our status code."""
    if status_text.upper() in ("HT", "HALF TIME"):
        return "HT"
    if status_text.upper() in ("FT", "FULL TIME", "AET", "AP"):
        return "FT"
    return PERIOD_MAP.get(period, "1H")


def update_live_data(match_id, match_info, goals, red_cards, home_code, away_code):
    """Update results.json with live match data."""
    data = json.loads(RESULTS_FILE.read_text())

    # Replace team placeholders with actual codes
    for g in goals:
        if g["team"] == "__HOME__":
            g["team"] = home_code
        elif g["team"] == "__AWAY__":
            g["team"] = away_code

    # Also fix red card labels
    red_cards = [
        rc.replace("(HOME)", f"({home_code})").replace("(AWAY)", f"({away_code})")
        for rc in red_cards
    ]

    status = map_status(match_info["period"], match_info["status_text"])
    minute = parse_minute(match_info["status_text"])

    live_entry = {
        "id": match_id,
        "status": status,
        "minute": minute,
        "home": match_info["home_score"],
        "away": match_info["away_score"],
    }

    if goals:
        live_entry["goals"] = goals
    if red_cards:
        live_entry["redCards"] = red_cards

    # Update or add in live array
    live_list = data.get("live", [])
    found = False
    for i, entry in enumerate(live_list):
        if entry["id"] == match_id:
            live_list[i] = live_entry
            found = True
            break
    if not found:
        live_list.append(live_entry)

    data["live"] = live_list

    # If match finished, move to results and remove from live
    if status == "FT":
        result_entry = {
            "id": match_id,
            "home": match_info["home_score"],
            "away": match_info["away_score"],
        }
        if goals:
            result_entry["goals"] = goals

        # Add/update in results
        existing_ids = {r["id"] for r in data["results"]}
        if match_id in existing_ids:
            data["results"] = [
                result_entry if r["id"] == match_id else r
                for r in data["results"]
            ]
        else:
            data["results"].append(result_entry)
            data["results"].sort(key=lambda r: r["id"])

        # Remove from live
        data["live"] = [e for e in data["live"] if e["id"] != match_id]

    data["updated"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    RESULTS_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")

    return status


def git_push():
    """Commit and push results.json."""
    try:
        subprocess.run(["git", "-C", str(SCRIPT_DIR), "add", "results.json"],
                       check=True, capture_output=True)
        msg = f"live: auto-update {datetime.now().strftime('%H:%M')}"
        subprocess.run(["git", "-C", str(SCRIPT_DIR), "commit", "-m", msg],
                       check=True, capture_output=True)
        subprocess.run(["git", "-C", str(SCRIPT_DIR), "push"],
                       check=True, capture_output=True)
        return True
    except subprocess.CalledProcessError:
        return False


def run_once(api_key, test_mode=False):
    """Fetch and update once. Returns True if match is still live."""
    now = datetime.now().strftime("%H:%M:%S")

    print(f"\n[{now}] Fetching live matches...")
    live_matches = fetch_live_matches(api_key)

    if not live_matches:
        print("  No live matches found.")
        return False

    still_live = False

    for lm in live_matches:
        eid = lm["eid"]

        # In test mode, use the first match with goals
        if test_mode:
            if int(lm["home_score"]) + int(lm["away_score"]) > 0:
                match_id = 900  # Map to test match
                home_code = "ARG"  # Pretend it's Argentina
                away_code = "ZAM"
                print(f"  TEST MODE: Using {lm['home_name']} vs {lm['away_name']} as match 900")
            else:
                continue
        elif eid in WATCHED_MATCHES:
            match_id = WATCHED_MATCHES[eid]
            home_code = "ARG"
            away_code = "ZAM"
        else:
            continue

        print(f"  {lm['home_name']} {lm['home_score']}-{lm['away_score']} {lm['away_name']}")
        print(f"  Status: {lm['status_text']} (period: {lm['period']})")

        # Fetch incidents
        goals, red_cards = fetch_incidents(eid, api_key)
        print(f"  Goals: {len(goals)}, Red cards: {len(red_cards)}")

        # Update JSON
        status = update_live_data(match_id, lm, goals, red_cards, home_code, away_code)
        print(f"  Updated results.json (status: {status})")

        # Push to GitHub
        if git_push():
            print(f"  Pushed to GitHub")
        else:
            print(f"  Push failed (no changes or git error)")

        if status != "FT":
            still_live = True

        if test_mode:
            break  # Only process one match in test mode

    return still_live


def main():
    api_key = load_api_key()
    if not api_key:
        print("Error: Set RAPIDAPI_KEY env variable or create .env file")
        print("  echo 'RAPIDAPI_KEY=your_key_here' > .env")
        sys.exit(1)

    test_mode = "--test" in sys.argv
    watch_mode = "--watch" in sys.argv

    if test_mode:
        print("=== TEST MODE: will use any live match as match 900 ===")

    if watch_mode:
        print("=== WATCH MODE: polling every 2 minutes ===")
        print("Press Ctrl+C to stop.\n")
        try:
            while True:
                still_live = run_once(api_key, test_mode)
                if not still_live:
                    print("\nNo more live matches being tracked. Stopping.")
                    break
                print("\nWaiting 2 minutes...")
                time.sleep(120)
        except KeyboardInterrupt:
            print("\nStopped.")
    else:
        run_once(api_key, test_mode)


if __name__ == "__main__":
    main()
