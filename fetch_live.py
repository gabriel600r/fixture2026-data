#!/usr/bin/env python3
"""
Fetch live match data from LiveScore API (RapidAPI) and update results.json.
Pushes updates to GitHub via the Contents API (no git required).

Compatible with Python 3.4+.

Usage:
  python3 fetch_live.py              # One-shot fetch
  python3 fetch_live.py --watch      # Poll every 2 min while match is live
  python3 fetch_live.py --test       # Test with any live match right now

Requires:
  RAPIDAPI_KEY  - LiveScore6 API key
  GITHUB_TOKEN  - GitHub personal access token with repo write access

Set via environment variables or .env file.
"""

import base64
import json
import os
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

# Python 3.4 compat: urllib
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

SCRIPT_DIR = Path(__file__).parent
RESULTS_FILE = SCRIPT_DIR / "results.json"
ENV_FILE = SCRIPT_DIR / ".env"

# LiveScore6 API on RapidAPI
API_HOST = "livescore6.p.rapidapi.com"
API_BASE = "https://" + API_HOST

# GitHub repo
GITHUB_OWNER = "gabriel600r"
GITHUB_REPO = "fixture2026-data"
GITHUB_FILE = "results.json"
GITHUB_API = "https://api.github.com"

# Poll interval in seconds
POLL_INTERVAL = 120  # 2 minutes

# Max consecutive API failures before giving up
MAX_FAILURES = 10

# ── Match configuration ─────────────────────────────────────
# Map LiveScore Eid -> our app match ID and team codes
# Format: "eid": (app_match_id, "HOME_CODE", "AWAY_CODE")
# Fill this in before each match day.
WATCHED_MATCHES = {
    # "1757983": (900, "ARG", "ZAM"),  # Test match (completed)
}

# Incident types in LiveScore API
IT_GOAL = {36, 37}         # Regular goal
IT_OWN_GOAL = {34}         # Own goal
IT_PENALTY_GOAL = {39}     # Penalty scored
IT_RED_CARD = {17, 45}     # Red card, second yellow -> red
IT_YELLOW_CARD = {43}      # Yellow card


def log(msg):
    """Print with timestamp."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print("[{0}] {1}".format(now, msg))
    sys.stdout.flush()


def load_env():
    """Load env vars from .env file."""
    conf = {}
    if ENV_FILE.exists():
        with open(str(ENV_FILE)) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, val = line.split("=", 1)
                    conf[key.strip()] = val.strip().strip("'\"")
    return conf


def get_config():
    """Get API key and GitHub token from env or .env."""
    env = load_env()
    api_key = os.environ.get("RAPIDAPI_KEY", env.get("RAPIDAPI_KEY", ""))
    gh_token = os.environ.get("GITHUB_TOKEN", env.get("GITHUB_TOKEN", ""))
    return api_key, gh_token


def http_get(url, headers=None, timeout=15, retries=3):
    """GET request with retry logic."""
    last_err = None
    for attempt in range(retries):
        try:
            req = Request(url)
            if headers:
                for k, v in headers.items():
                    req.add_header(k, v)
            resp = urlopen(req, timeout=timeout)
            data = resp.read().decode("utf-8")
            return json.loads(data)
        except HTTPError as e:
            log("  HTTP error {0}: {1} (attempt {2}/{3})".format(
                e.code, e.reason, attempt + 1, retries))
            last_err = e
            if e.code in (401, 403, 404):
                break  # Don't retry auth/not-found errors
        except (URLError, Exception) as e:
            log("  Network error: {0} (attempt {1}/{2})".format(
                e, attempt + 1, retries))
            last_err = e
        if attempt < retries - 1:
            wait = 5 * (attempt + 1)
            log("  Retrying in {0}s...".format(wait))
            time.sleep(wait)
    return None


def http_put(url, data, headers=None, timeout=15):
    """PUT request for GitHub API."""
    body = json.dumps(data).encode("utf-8")
    req = Request(url, data=body, method="PUT") if hasattr(Request, 'method') else Request(url, data=body)
    # Python 3.4 compat for PUT
    if not hasattr(Request, 'method'):
        req.get_method = lambda: "PUT"
    else:
        req.method = "PUT"
    req.add_header("Content-Type", "application/json")
    if headers:
        for k, v in headers.items():
            req.add_header(k, v)
    try:
        resp = urlopen(req, timeout=timeout)
        return json.loads(resp.read().decode("utf-8"))
    except HTTPError as e:
        body_text = ""
        try:
            body_text = e.read().decode("utf-8")
        except Exception:
            pass
        log("  GitHub PUT error {0}: {1}".format(e.code, body_text[:200]))
        return None
    except Exception as e:
        log("  GitHub PUT failed: {0}".format(e))
        return None


# ── LiveScore API ───────────────────────────────────────────

def fetch_live_matches(api_key):
    """Fetch all live soccer matches."""
    headers = {
        "X-RapidAPI-Host": API_HOST,
        "X-RapidAPI-Key": api_key,
    }
    data = http_get(API_BASE + "/matches/v2/list-live?Category=soccer", headers)
    if not data:
        return []

    matches = []
    for stage in data.get("Stages", []):
        for ev in stage.get("Events", []):
            t1 = ev.get("T1", [{}])
            t2 = ev.get("T2", [{}])
            matches.append({
                "eid": str(ev.get("Eid", "")),
                "home_name": t1[0].get("Nm", "?") if t1 else "?",
                "away_name": t2[0].get("Nm", "?") if t2 else "?",
                "home_score": int(ev.get("Tr1", "0") or "0"),
                "away_score": int(ev.get("Tr2", "0") or "0"),
                "status_text": ev.get("Eps", ""),
                "period": int(ev.get("Epr", 0)),
                "league": stage.get("Snm", ""),
            })
    return matches


def fetch_incidents(eid, api_key):
    """Fetch match incidents (goals, cards).

    The API nests incidents: top-level events may contain a sub-array "Incs"
    with the actual goal/card details. We flatten both levels.
    """
    headers = {
        "X-RapidAPI-Host": API_HOST,
        "X-RapidAPI-Key": api_key,
    }
    data = http_get(
        API_BASE + "/matches/v2/get-incidents?Eid={0}&Category=soccer".format(eid),
        headers
    )
    if not data:
        return [], []

    goals = []
    red_cards = []

    def process_event(ev):
        """Process a single incident event."""
        it = ev.get("IT", 0)
        player = ev.get("Pn", "Unknown")
        minute = ev.get("Min", 0)
        side = ev.get("Nm", 0)

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
                "team": "__AWAY__" if side == 1 else "__HOME__",
                "og": True,
            })

        elif it in IT_RED_CARD:
            side_label = "HOME" if side == 1 else "AWAY"
            red_cards.append("{0} ({1}) {2}'".format(player, side_label, minute))

    incs = data.get("Incs", {})
    for period_key in sorted(incs.keys()):
        events = incs[period_key]
        if not isinstance(events, list):
            continue
        for ev in events:
            # Process top-level event
            process_event(ev)
            # Also process nested sub-incidents (goals are often here)
            for sub in ev.get("Incs", []):
                process_event(sub)

    goals.sort(key=lambda g: g["minute"])
    return goals, red_cards


def parse_minute(status_text):
    """Extract minute number from status like '45+2' or '78'."""
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
    st = status_text.upper().strip().replace("'", "")

    # Check text-based status first (more reliable than period number)
    if st in ("HT", "HALF TIME", "HALF-TIME"):
        return "HT"
    if st in ("FT", "FULL TIME", "FULL-TIME", "AET", "AP", "ENDED"):
        return "FT"
    if st in ("PEN", "PENALTIES", "PENALTY"):
        return "PEN"

    # Try to determine from minute number
    minute = parse_minute(status_text)
    if minute is not None:
        if minute <= 45:
            return "1H"
        elif minute <= 90:
            return "2H"
        else:
            return "ET"

    # Fallback to period number
    period_map = {
        1: "1H",
        2: "HT",
        3: "2H",
        4: "ET",
        5: "PEN",
        6: "FT",
    }
    return period_map.get(period, "1H")


# ── GitHub API ──────────────────────────────────────────────

def github_get_file(gh_token):
    """Get current results.json content and SHA from GitHub."""
    url = "{0}/repos/{1}/{2}/contents/{3}".format(
        GITHUB_API, GITHUB_OWNER, GITHUB_REPO, GITHUB_FILE)
    headers = {
        "Authorization": "token " + gh_token,
        "Accept": "application/vnd.github.v3+json",
    }
    data = http_get(url, headers)
    if not data:
        return None, None

    content = base64.b64decode(data.get("content", "")).decode("utf-8")
    sha = data.get("sha", "")
    return content, sha


def github_update_file(gh_token, new_content, sha, message):
    """Update results.json on GitHub via Contents API."""
    url = "{0}/repos/{1}/{2}/contents/{3}".format(
        GITHUB_API, GITHUB_OWNER, GITHUB_REPO, GITHUB_FILE)
    headers = {
        "Authorization": "token " + gh_token,
        "Accept": "application/vnd.github.v3+json",
    }
    encoded = base64.b64encode(new_content.encode("utf-8")).decode("ascii")
    payload = {
        "message": message,
        "content": encoded,
        "sha": sha,
    }
    return http_put(url, payload, headers, timeout=30)


# ── Main logic ──────────────────────────────────────────────

def update_results_json(results_data, match_id, match_info, goals, red_cards,
                        home_code, away_code):
    """Update the results dict with live match data. Returns (data, status)."""
    # Replace team placeholders
    for g in goals:
        if g["team"] == "__HOME__":
            g["team"] = home_code
        elif g["team"] == "__AWAY__":
            g["team"] = away_code

    red_cards = [
        rc.replace("(HOME)", "({0})".format(home_code))
          .replace("(AWAY)", "({0})".format(away_code))
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
    live_list = results_data.get("live", [])
    found = False
    for i, entry in enumerate(live_list):
        if entry["id"] == match_id:
            live_list[i] = live_entry
            found = True
            break
    if not found:
        live_list.append(live_entry)
    results_data["live"] = live_list

    # If match finished, move to results and remove from live
    if status == "FT":
        result_entry = {
            "id": match_id,
            "home": match_info["home_score"],
            "away": match_info["away_score"],
        }
        if goals:
            result_entry["goals"] = goals

        existing_ids = set(r["id"] for r in results_data["results"])
        if match_id in existing_ids:
            results_data["results"] = [
                result_entry if r["id"] == match_id else r
                for r in results_data["results"]
            ]
        else:
            results_data["results"].append(result_entry)
            results_data["results"].sort(key=lambda r: r["id"])

        results_data["live"] = [
            e for e in results_data["live"] if e["id"] != match_id
        ]

    results_data["updated"] = datetime.now(timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ")

    return results_data, status


def run_once(api_key, gh_token, test_mode=False):
    """Fetch and update once. Returns True if match is still live."""
    log("Fetching live matches...")
    live_matches = fetch_live_matches(api_key)

    if live_matches is None:
        log("API request failed, will retry next cycle")
        return True  # Keep running, don't stop on transient errors

    if not live_matches:
        log("No live matches found")
        return False

    # Find our watched matches
    targets = []
    for lm in live_matches:
        eid = lm["eid"]
        if test_mode:
            if lm["home_score"] + lm["away_score"] > 0 or len(targets) == 0:
                targets.append((lm, 900, "TST", "TST"))
                log("  TEST: Using {0} vs {1} ({2}) as match 900".format(
                    lm["home_name"], lm["away_name"], lm["league"]))
                if lm["home_score"] + lm["away_score"] > 0:
                    break  # Prefer match with goals
        elif eid in WATCHED_MATCHES:
            mid, hc, ac = WATCHED_MATCHES[eid]
            targets.append((lm, mid, hc, ac))
            log("  Found: {0} {1}-{2} {3} [{4}]".format(
                lm["home_name"], lm["home_score"], lm["away_score"],
                lm["away_name"], lm["status_text"]))

    if not targets:
        log("No watched matches currently live ({0} total live matches)".format(
            len(live_matches)))
        return False

    # Get current file from GitHub
    log("Fetching results.json from GitHub...")
    content, sha = github_get_file(gh_token)
    if content is None:
        log("ERROR: Could not fetch results.json from GitHub")
        return True  # Keep running

    results_data = json.loads(content)
    any_live = False
    changes = []

    for lm, match_id, home_code, away_code in targets:
        eid = lm["eid"]

        # Fetch incidents
        goals, red_cards = fetch_incidents(eid, api_key)
        log("  {0} {1}-{2} {3} | {4} | Goals: {5}, Red cards: {6}".format(
            lm["home_name"], lm["home_score"], lm["away_score"],
            lm["away_name"], lm["status_text"],
            len(goals), len(red_cards)))

        results_data, status = update_results_json(
            results_data, match_id, lm, goals, red_cards,
            home_code, away_code)

        changes.append("{0} {1}-{2} {3} ({4})".format(
            home_code, lm["home_score"], lm["away_score"],
            away_code, status))

        if status != "FT":
            any_live = True

    # Push to GitHub
    new_content = json.dumps(results_data, indent=2, ensure_ascii=False) + "\n"
    if new_content.strip() == content.strip():
        log("No changes to push")
        return any_live

    commit_msg = "live: {0}".format(", ".join(changes))
    log("Pushing to GitHub: {0}".format(commit_msg))
    result = github_update_file(gh_token, new_content, sha, commit_msg)
    if result:
        log("Push OK")
    else:
        log("Push FAILED")

    return any_live


def main():
    api_key, gh_token = get_config()

    if not api_key:
        print("Error: Set RAPIDAPI_KEY in env or .env file")
        sys.exit(1)
    if not gh_token:
        print("Error: Set GITHUB_TOKEN in env or .env file")
        sys.exit(1)

    test_mode = "--test" in sys.argv
    watch_mode = "--watch" in sys.argv

    if test_mode:
        log("=== TEST MODE ===")
    if watch_mode:
        log("=== WATCH MODE: polling every {0}s ===".format(POLL_INTERVAL))

    if watch_mode:
        consecutive_failures = 0
        consecutive_empty = 0
        try:
            while True:
                try:
                    still_live = run_once(api_key, gh_token, test_mode)
                    consecutive_failures = 0  # Reset on success

                    if not still_live:
                        consecutive_empty += 1
                        if consecutive_empty >= 5:
                            log("No live matches for {0} cycles. Stopping.".format(
                                consecutive_empty))
                            break
                        log("No live matches (attempt {0}/5)".format(
                            consecutive_empty))
                    else:
                        consecutive_empty = 0

                except Exception as e:
                    consecutive_failures += 1
                    log("ERROR (failure {0}/{1}): {2}".format(
                        consecutive_failures, MAX_FAILURES, e))
                    traceback.print_exc()
                    sys.stdout.flush()
                    if consecutive_failures >= MAX_FAILURES:
                        log("Too many consecutive failures. Stopping.")
                        break

                log("Next poll in {0}s...".format(POLL_INTERVAL))
                time.sleep(POLL_INTERVAL)

        except KeyboardInterrupt:
            log("Stopped by user")
    else:
        run_once(api_key, gh_token, test_mode)


if __name__ == "__main__":
    main()
