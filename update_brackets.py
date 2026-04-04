#!/usr/bin/env python3
"""
Automatic bracket updater for FIFA World Cup 2026.
Reads results.json, calculates group standings, determines which teams
advance, and writes bracket assignments back to results.json.

Can be called by fetch_live.py after a match ends, or manually.

Usage:
  python3 update_brackets.py              # Update and push to GitHub
  python3 update_brackets.py --dry-run    # Show changes without pushing
  python3 update_brackets.py --test       # Run with simulated full results
"""

import json
import os
import sys
import base64
import urllib.request
import urllib.error
from collections import defaultdict
from datetime import datetime

# ── Group stage matches (from matches_data.dart) ──
# 12 groups (A-L), 4 teams each, 6 matches per group = 72 matches
GROUPS = {
    'A': {'teams': ['MEX', 'KOR', 'CZE', 'RSA'], 'matches': [1, 2, 3, 4, 5, 6]},
    'B': {'teams': ['CAN', 'BIH', 'QAT', 'SUI'], 'matches': [7, 8, 9, 10, 11, 12]},
    'C': {'teams': ['BRA', 'MAR', 'SCO', 'HAI'], 'matches': [13, 14, 15, 16, 17, 18]},
    'D': {'teams': ['USA', 'PAR', 'AUS', 'GER'], 'matches': [19, 20, 21, 22, 23, 24]},
    'E': {'teams': ['ECU', 'CIV', 'CUR', 'NED'], 'matches': [25, 26, 27, 28, 29, 30]},
    'F': {'teams': ['JPN', 'TUN', 'BEL', 'IRN'], 'matches': [31, 32, 33, 34, 35, 36]},
    'G': {'teams': ['EGY', 'NZL', 'ESP', 'URU'], 'matches': [37, 38, 39, 40, 41, 42]},
    'H': {'teams': ['KSA', 'PER', 'DEN', 'FRA'], 'matches': [43, 44, 45, 46, 47, 48]},
    'I': {'teams': ['SEN', 'POR', 'ALG', 'COL'], 'matches': [49, 50, 51, 52, 53, 54]},
    'J': {'teams': ['ARG', 'NGA', 'TUR', 'CMR'], 'matches': [55, 56, 57, 58, 59, 60]},
    'K': {'teams': ['SRB', 'CRC', 'ITA', 'CHI'], 'matches': [61, 62, 63, 64, 65, 66]},
    'L': {'teams': ['ENG', 'GHA', 'PAN', 'CRO'], 'matches': [67, 68, 69, 70, 71, 72]},
}

# Match ID -> [homeCode, awayCode] mapping
MATCH_TEAMS = {}
# Build from groups
_match_pairs = {
    # Group A
    1: ('MEX', 'RSA'), 2: ('KOR', 'CZE'), 3: ('CZE', 'RSA'), 4: ('MEX', 'KOR'),
    5: ('CZE', 'MEX'), 6: ('RSA', 'KOR'),
    # Group B
    7: ('CAN', 'BIH'), 8: ('QAT', 'SUI'), 9: ('SUI', 'BIH'), 10: ('CAN', 'QAT'),
    11: ('SUI', 'CAN'), 12: ('BIH', 'QAT'),
    # Group C
    13: ('BRA', 'MAR'), 14: ('HAI', 'SCO'), 15: ('SCO', 'MAR'), 16: ('BRA', 'HAI'),
    17: ('SCO', 'BRA'), 18: ('MAR', 'HAI'),
    # Group D
    19: ('USA', 'GER'), 20: ('PAR', 'AUS'), 21: ('AUS', 'GER'), 22: ('USA', 'PAR'),
    23: ('AUS', 'USA'), 24: ('GER', 'PAR'),
    # Group E
    25: ('NED', 'CUR'), 26: ('ECU', 'CIV'), 27: ('CIV', 'CUR'), 28: ('NED', 'ECU'),
    29: ('CIV', 'NED'), 30: ('CUR', 'ECU'),
    # Group F
    31: ('JPN', 'IRN'), 32: ('BEL', 'TUN'), 33: ('TUN', 'IRN'), 34: ('JPN', 'BEL'),
    35: ('TUN', 'JPN'), 36: ('IRN', 'BEL'),
    # Group G
    37: ('ESP', 'URU'), 38: ('EGY', 'NZL'), 39: ('NZL', 'URU'), 40: ('ESP', 'EGY'),
    41: ('NZL', 'ESP'), 42: ('URU', 'EGY'),
    # Group H
    43: ('FRA', 'KSA'), 44: ('DEN', 'PER'), 45: ('PER', 'KSA'), 46: ('FRA', 'DEN'),
    47: ('PER', 'FRA'), 48: ('KSA', 'DEN'),
    # Group I
    49: ('COL', 'SEN'), 50: ('POR', 'ALG'), 51: ('ALG', 'SEN'), 52: ('COL', 'POR'),
    53: ('ALG', 'COL'), 54: ('SEN', 'POR'),
    # Group J
    55: ('ARG', 'CMR'), 56: ('NGA', 'TUR'), 57: ('TUR', 'CMR'), 58: ('ARG', 'NGA'),
    59: ('TUR', 'ARG'), 60: ('CMR', 'NGA'),
    # Group K
    61: ('ITA', 'CRC'), 62: ('SRB', 'CHI'), 63: ('CHI', 'CRC'), 64: ('ITA', 'SRB'),
    65: ('CHI', 'ITA'), 66: ('CRC', 'SRB'),
    # Group L
    67: ('ENG', 'CRO'), 68: ('PAN', 'GHA'), 69: ('ENG', 'GHA'), 70: ('PAN', 'CRO'),
    71: ('PAN', 'ENG'), 72: ('CRO', 'GHA'),
}

# ── Round of 32 bracket rules ──
# Format: match_id -> (home_source, away_source)
# Sources: '1A' = winner group A, '2A' = runner-up group A, '3X' = 3rd place (resolved later)
R32_BRACKET = {
    73: ('2A', '2B'),
    74: ('1E', '3ABCDF'),
    75: ('1F', '2C'),
    76: ('1C', '2F'),
    77: ('1I', '3CDFGH'),
    78: ('2E', '2I'),
    79: ('1A', '3CEFHI'),
    80: ('1L', '3EHIJK'),
    81: ('1D', '3BEFIJ'),
    82: ('1G', '3AEHIJ'),
    83: ('2K', '2L'),
    84: ('1H', '2J'),
    85: ('1B', '3EFGIJ'),
    86: ('1J', '2H'),
    87: ('1K', '3DEIJL'),
    88: ('2D', '2G'),
}

# ── Knockout bracket (R16 onward) ──
R16_BRACKET = {
    89: (74, 77),
    90: (73, 75),
    91: (76, 78),
    92: (79, 80),
    93: (83, 84),
    94: (81, 82),
    95: (86, 88),
    96: (85, 87),
}

QF_BRACKET = {
    97: (89, 90),
    98: (93, 94),
    99: (91, 92),
    100: (95, 96),
}

SF_BRACKET = {
    101: (97, 98),
    102: (99, 100),
}

FINAL_BRACKET = {
    104: (101, 102),
}

THIRD_PLACE_BRACKET = {
    103: (101, 102),  # losers of semis
}

# ── Third-place assignment tables ──
# Given which 8 groups have qualifying 3rd-place teams,
# assign each to specific R32 matches.
# Key = frozenset of 8 group letters, Value = dict mapping R32_match_id -> group_letter
# FIFA has published these combinations. There are 495 possible combos from C(12,8).
# The key ones that matter are the slot assignments.
# Each R32 match that takes a 3rd-place team has a list of possible groups.
# The assignment follows FIFA's published table.

# Simplified approach: for each R32 match needing a 3rd-place team,
# we know which groups are eligible. We assign in priority order.
# Match 74 (1E vs 3rd): from A,B,C,D,F
# Match 77 (1I vs 3rd): from C,D,F,G,H
# Match 79 (1A vs 3rd): from C,E,F,H,I
# Match 80 (1L vs 3rd): from E,H,I,J,K
# Match 81 (1D vs 3rd): from B,E,F,I,J
# Match 82 (1G vs 3rd): from A,E,H,I,J
# Match 85 (1B vs 3rd): from E,F,G,I,J
# Match 87 (1K vs 3rd): from D,E,I,J,L

THIRD_PLACE_SLOTS = {
    74: list('ABCDF'),
    77: list('CDFGH'),
    79: list('CEFHI'),
    80: list('EHIJK'),
    81: list('BEFIJ'),
    82: list('AEHIJ'),
    85: list('EFGIJ'),
    87: list('DEIJL'),
}


def calculate_standings(group_name, group_info, results_map):
    """Calculate group standings from results."""
    teams = group_info['teams']
    match_ids = group_info['matches']

    stats = {}
    for t in teams:
        stats[t] = {'pts': 0, 'gf': 0, 'ga': 0, 'gd': 0, 'w': 0, 'played': 0}

    for mid in match_ids:
        if mid not in results_map:
            continue
        r = results_map[mid]
        pair = _match_pairs.get(mid)
        if not pair:
            continue
        home_code, away_code = pair
        home_goals = r['home']
        away_goals = r['away']

        stats[home_code]['gf'] += home_goals
        stats[home_code]['ga'] += away_goals
        stats[away_code]['gf'] += away_goals
        stats[away_code]['ga'] += home_goals
        stats[home_code]['played'] += 1
        stats[away_code]['played'] += 1

        if home_goals > away_goals:
            stats[home_code]['pts'] += 3
            stats[home_code]['w'] += 1
        elif away_goals > home_goals:
            stats[away_code]['pts'] += 3
            stats[away_code]['w'] += 1
        else:
            stats[home_code]['pts'] += 1
            stats[away_code]['pts'] += 1

    for t in teams:
        stats[t]['gd'] = stats[t]['gf'] - stats[t]['ga']

    # Sort: points, goal difference, goals for, wins
    ranked = sorted(teams, key=lambda t: (
        stats[t]['pts'], stats[t]['gd'], stats[t]['gf'], stats[t]['w']
    ), reverse=True)

    return [(t, stats[t]) for t in ranked]


def group_is_complete(group_info, results_map):
    """Check if all matches in a group have results."""
    return all(mid in results_map for mid in group_info['matches'])


def resolve_third_place(qualifying_thirds, third_teams):
    """
    Assign 8 qualifying 3rd-place teams to R32 match slots.
    qualifying_thirds: set of group letters that have qualifying 3rd-place teams
    third_teams: dict of group_letter -> team_code for 3rd place
    Returns: dict of match_id -> team_code
    """
    assignments = {}
    remaining = set(qualifying_thirds)

    # Process slots in a deterministic order (by match ID)
    for match_id in sorted(THIRD_PLACE_SLOTS.keys()):
        eligible = THIRD_PLACE_SLOTS[match_id]
        # Find the first eligible group that hasn't been assigned yet
        for group in eligible:
            if group in remaining:
                assignments[match_id] = third_teams[group]
                remaining.remove(group)
                break

    return assignments


def get_knockout_winner(match_id, results_map, brackets):
    """Get the winner of a knockout match, or None if not played yet."""
    if match_id not in results_map:
        return None

    # Need to know who played
    mid_str = str(match_id)
    if mid_str not in brackets:
        return None

    home_code = brackets[mid_str].get('home', 'TBD')
    away_code = brackets[mid_str].get('away', 'TBD')
    if home_code == 'TBD' or away_code == 'TBD':
        return None

    r = results_map[match_id]
    if r['home'] > r['away']:
        return home_code
    elif r['away'] > r['home']:
        return away_code
    else:
        # Draw in knockout = needs penalties, check if there's extra info
        # For now, can't determine winner from score alone
        return None


def get_knockout_loser(match_id, results_map, brackets):
    """Get the loser of a knockout match."""
    winner = get_knockout_winner(match_id, results_map, brackets)
    if winner is None:
        return None

    mid_str = str(match_id)
    home_code = brackets[mid_str].get('home', 'TBD')
    away_code = brackets[mid_str].get('away', 'TBD')
    return away_code if winner == home_code else home_code


def update_brackets(data, dry_run=False):
    """Main logic: calculate standings and update brackets in results.json data."""
    results_list = data.get('results', [])
    results_map = {r['id']: r for r in results_list}
    brackets = data.get('brackets', {})
    changes = []

    # ── Step 1: Group stage -> Round of 32 ──
    group_winners = {}   # 'A' -> team_code
    group_runners = {}   # 'A' -> team_code
    group_thirds = {}    # 'A' -> (team_code, stats)
    complete_groups = set()

    for name, info in GROUPS.items():
        if not group_is_complete(info, results_map):
            continue
        complete_groups.add(name)
        standings = calculate_standings(name, info, results_map)
        group_winners[name] = standings[0][0]
        group_runners[name] = standings[1][0]
        group_thirds[name] = (standings[2][0], standings[2][1])

    # Determine qualifying 3rd-place teams (best 8 out of 12)
    third_place_assignments = {}
    if len(group_thirds) >= 8:
        # Rank all 3rd-place teams
        all_thirds = [(g, t, s) for g, (t, s) in group_thirds.items()]
        all_thirds.sort(key=lambda x: (
            x[2]['pts'], x[2]['gd'], x[2]['gf'], x[2]['w']
        ), reverse=True)

        qualifying = all_thirds[:8]
        qualifying_groups = set(g for g, t, s in qualifying)
        third_teams = {g: t for g, t, s in qualifying}
        third_place_assignments = resolve_third_place(qualifying_groups, third_teams)

    # Assign R32 matches
    for match_id, (home_src, away_src) in R32_BRACKET.items():
        mid_str = str(match_id)
        current = brackets.get(mid_str, {})
        new_home = current.get('home', 'TBD')
        new_away = current.get('away', 'TBD')

        # Resolve home
        if new_home == 'TBD':
            if home_src.startswith('1') and home_src[1] in group_winners:
                new_home = group_winners[home_src[1]]
            elif home_src.startswith('2') and home_src[1] in group_runners:
                new_home = group_runners[home_src[1]]

        # Resolve away
        if new_away == 'TBD':
            if away_src.startswith('1') and away_src[1] in group_winners:
                new_away = group_winners[away_src[1]]
            elif away_src.startswith('2') and away_src[1] in group_runners:
                new_away = group_runners[away_src[1]]
            elif away_src.startswith('3') and match_id in third_place_assignments:
                new_away = third_place_assignments[match_id]

        if new_home != 'TBD' or new_away != 'TBD':
            new_bracket = {'home': new_home, 'away': new_away}
            if current != new_bracket:
                brackets[mid_str] = new_bracket
                changes.append(f"R32 Match {match_id}: {new_home} vs {new_away}")

    # ── Step 2: R16 from R32 winners ──
    for match_id, (src_a, src_b) in R16_BRACKET.items():
        mid_str = str(match_id)
        current = brackets.get(mid_str, {})
        new_home = current.get('home', 'TBD')
        new_away = current.get('away', 'TBD')

        if new_home == 'TBD':
            winner = get_knockout_winner(src_a, results_map, brackets)
            if winner:
                new_home = winner
        if new_away == 'TBD':
            winner = get_knockout_winner(src_b, results_map, brackets)
            if winner:
                new_away = winner

        if new_home != 'TBD' or new_away != 'TBD':
            new_bracket = {'home': new_home, 'away': new_away}
            if current != new_bracket:
                brackets[mid_str] = new_bracket
                changes.append(f"R16 Match {match_id}: {new_home} vs {new_away}")

    # ── Step 3: QF from R16 winners ──
    for match_id, (src_a, src_b) in QF_BRACKET.items():
        mid_str = str(match_id)
        current = brackets.get(mid_str, {})
        new_home = current.get('home', 'TBD')
        new_away = current.get('away', 'TBD')

        if new_home == 'TBD':
            winner = get_knockout_winner(src_a, results_map, brackets)
            if winner:
                new_home = winner
        if new_away == 'TBD':
            winner = get_knockout_winner(src_b, results_map, brackets)
            if winner:
                new_away = winner

        if new_home != 'TBD' or new_away != 'TBD':
            new_bracket = {'home': new_home, 'away': new_away}
            if current != new_bracket:
                brackets[mid_str] = new_bracket
                changes.append(f"QF Match {match_id}: {new_home} vs {new_away}")

    # ── Step 4: SF from QF winners ──
    for match_id, (src_a, src_b) in SF_BRACKET.items():
        mid_str = str(match_id)
        current = brackets.get(mid_str, {})
        new_home = current.get('home', 'TBD')
        new_away = current.get('away', 'TBD')

        if new_home == 'TBD':
            winner = get_knockout_winner(src_a, results_map, brackets)
            if winner:
                new_home = winner
        if new_away == 'TBD':
            winner = get_knockout_winner(src_b, results_map, brackets)
            if winner:
                new_away = winner

        if new_home != 'TBD' or new_away != 'TBD':
            new_bracket = {'home': new_home, 'away': new_away}
            if current != new_bracket:
                brackets[mid_str] = new_bracket
                changes.append(f"SF Match {match_id}: {new_home} vs {new_away}")

    # ── Step 5: Final from SF winners, 3rd place from SF losers ──
    for match_id, (src_a, src_b) in FINAL_BRACKET.items():
        mid_str = str(match_id)
        current = brackets.get(mid_str, {})
        new_home = current.get('home', 'TBD')
        new_away = current.get('away', 'TBD')

        if new_home == 'TBD':
            winner = get_knockout_winner(src_a, results_map, brackets)
            if winner:
                new_home = winner
        if new_away == 'TBD':
            winner = get_knockout_winner(src_b, results_map, brackets)
            if winner:
                new_away = winner

        if new_home != 'TBD' or new_away != 'TBD':
            new_bracket = {'home': new_home, 'away': new_away}
            if current != new_bracket:
                brackets[mid_str] = new_bracket
                changes.append(f"FINAL Match {match_id}: {new_home} vs {new_away}")

    # 3rd place match (losers of semis)
    for match_id, (src_a, src_b) in THIRD_PLACE_BRACKET.items():
        mid_str = str(match_id)
        current = brackets.get(mid_str, {})
        new_home = current.get('home', 'TBD')
        new_away = current.get('away', 'TBD')

        if new_home == 'TBD':
            loser = get_knockout_loser(src_a, results_map, brackets)
            if loser:
                new_home = loser
        if new_away == 'TBD':
            loser = get_knockout_loser(src_b, results_map, brackets)
            if loser:
                new_away = loser

        if new_home != 'TBD' or new_away != 'TBD':
            new_bracket = {'home': new_home, 'away': new_away}
            if current != new_bracket:
                brackets[mid_str] = new_bracket
                changes.append(f"3RD Match {match_id}: {new_home} vs {new_away}")

    data['brackets'] = brackets
    return changes


def generate_test_results():
    """Generate simulated results for ALL 72 group matches to test the bracket logic."""
    import random
    random.seed(2026)  # Deterministic for reproducibility

    results = []
    for mid, (home, away) in sorted(_match_pairs.items()):
        h = random.randint(0, 4)
        a = random.randint(0, 3)
        results.append({'id': mid, 'home': h, 'away': a})
    return results


def push_to_github(data):
    """Push updated results.json to GitHub via Contents API."""
    token = os.environ.get('GITHUB_TOKEN', '')
    if not token:
        # Try loading from .env
        env_path = os.path.join(os.path.dirname(__file__), '.env')
        if os.path.exists(env_path):
            with open(env_path) as f:
                for line in f:
                    if line.startswith('GITHUB_TOKEN='):
                        token = line.strip().split('=', 1)[1].strip('"\'')

    if not token:
        print("ERROR: No GITHUB_TOKEN found")
        return False

    repo = 'gabriel600r/fixture2026-data'
    path = 'results.json'
    url = 'https://api.github.com/repos/{}/contents/{}'.format(repo, path)

    # Get current SHA
    req = urllib.request.Request(url, headers={
        'Authorization': 'token ' + token,
        'Accept': 'application/vnd.github.v3+json',
    })
    try:
        resp = urllib.request.urlopen(req)
        current = json.loads(resp.read().decode())
        sha = current['sha']
    except Exception as e:
        print("ERROR getting SHA: {}".format(e))
        return False

    # Update timestamp
    data['updated'] = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')

    content = json.dumps(data, indent=2, ensure_ascii=False).encode()
    body = json.dumps({
        'message': 'auto: update brackets',
        'content': base64.b64encode(content).decode(),
        'sha': sha,
    }).encode()

    req = urllib.request.Request(url, data=body, method='PUT', headers={
        'Authorization': 'token ' + token,
        'Accept': 'application/vnd.github.v3+json',
        'Content-Type': 'application/json',
    })
    try:
        urllib.request.urlopen(req)
        print("Pushed to GitHub successfully.")
        return True
    except Exception as e:
        print("ERROR pushing: {}".format(e))
        return False


def main():
    dry_run = '--dry-run' in sys.argv
    test_mode = '--test' in sys.argv

    # Load results.json
    script_dir = os.path.dirname(os.path.abspath(__file__))
    results_path = os.path.join(script_dir, 'results.json')

    with open(results_path) as f:
        data = json.load(f)

    if test_mode:
        print("=== TEST MODE: Simulating all 72 group results ===\n")
        data['results'] = generate_test_results()
        data['brackets'] = {}

    changes = update_brackets(data)

    if not changes:
        print("No bracket changes needed.")
        return

    print("Bracket updates:")
    for c in changes:
        print("  " + c)

    if test_mode:
        # Show group standings
        results_map = {r['id']: r for r in data['results']}
        print("\n=== Group Standings ===")
        for name in sorted(GROUPS.keys()):
            info = GROUPS[name]
            standings = calculate_standings(name, info, results_map)
            print(f"\nGroup {name}:")
            for i, (team, s) in enumerate(standings):
                pos = ['1st', '2nd', '3rd', '4th'][i]
                print(f"  {pos}: {team} - {s['pts']}pts (GD:{s['gd']:+d}, GF:{s['gf']})")

    if dry_run or test_mode:
        print("\n(Dry run / test — not pushing to GitHub)")
        if test_mode:
            # Save test results locally for inspection
            test_path = os.path.join(script_dir, 'test_brackets.json')
            with open(test_path, 'w') as f:
                json.dump(data['brackets'], f, indent=2)
            print(f"Test brackets saved to {test_path}")
    else:
        # Save locally and push
        with open(results_path, 'w') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        push_to_github(data)


if __name__ == '__main__':
    main()
