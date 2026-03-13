#!/usr/bin/env python3
"""
Manchester City Schedule → ICS Generator
Data source: football-data.org (free plan)

Usage:
  python generate_mancity_ics.py --api-key YOUR_API_KEY

Get a free API key at: https://www.football-data.org/client/register

Man City team ID : 65
Competitions covered (free plan):
  PL  : Premier League
  FAC : FA Cup
  CL  : UEFA Champions League
  ELC : EFL Cup
  CLI : FIFA Club World Cup
"""

import argparse
import json
import sys
import uuid
from datetime import datetime, timedelta
from urllib.request import urlopen, Request
from urllib.error import HTTPError, URLError

# ---------------------------------------------------------------
# Constants
# ---------------------------------------------------------------
MAN_CITY_TEAM_ID = 65
BASE_URL = "https://api.football-data.org/v4"

TARGET_COMPETITIONS = {
    "PL":  "Premier League",
    "FAC": "FA Cup",
    "FA_CUP": "FA Cup",
    "CL":  "UEFA Champions League",
    "ELC": "EFL Cup",
    "CLI": "FIFA Club World Cup",
}

# ---------------------------------------------------------------
# API helpers
# ---------------------------------------------------------------
def fetch_json(url: str, api_key: str, extra_headers: dict = None) -> dict:
    headers = {"X-Auth-Token": api_key}
    if extra_headers:
        headers.update(extra_headers)
    req = Request(url, headers=headers)
    try:
        with urlopen(req, timeout=15) as res:
            return json.loads(res.read().decode())
    except HTTPError as e:
        body = e.read().decode(errors="replace")
        print(f"[ERROR] HTTP {e.code}: {url}", file=sys.stderr)
        print(f"        Response: {body[:300]}", file=sys.stderr)
        raise
    except URLError as e:
        print(f"[ERROR] Connection failed: {e.reason}", file=sys.stderr)
        raise


def get_fixtures(api_key: str) -> list:
    url = f"{BASE_URL}/teams/{MAN_CITY_TEAM_ID}/matches"
    print("[INFO] Fetching Man City fixtures...", file=sys.stderr)
    try:
        data = fetch_json(url, api_key)
    except Exception:
        sys.exit(1)

    matches = data.get("matches", [])
    filtered = [
        m for m in matches
        if m.get("competition", {}).get("code") in TARGET_COMPETITIONS
        and m.get("status") != "POSTPONED"
    ]
    print(f"[INFO] {len(filtered)} fixtures found (out of {len(matches)} total)", file=sys.stderr)
    return filtered


def get_pl_standings(api_key: str) -> list:
    """Fetch Premier League standings table (TOTAL type)."""
    url = f"{BASE_URL}/competitions/PL/standings"
    print("[INFO] Fetching PL standings...", file=sys.stderr)
    try:
        data = fetch_json(url, api_key)
    except Exception:
        print("[WARN] Could not fetch PL standings.", file=sys.stderr)
        return []

    standings = data.get("standings", [])
    print(f"[DEBUG] standings types: {[s.get('type') for s in standings]}", file=__import__("sys").stderr)
    for standing in standings:
        if standing.get("type") == "TOTAL":
            table = standing.get("table", [])
            print(f"[DEBUG] PL table has {len(table)} rows", file=__import__("sys").stderr)
            return table
    print("[WARN] TOTAL standings not found in response", file=__import__("sys").stderr)
    return []


def get_match_detail(api_key: str, match_id: int) -> dict:
    """Fetch full match detail. In v4, goals array is returned at top level."""
    url = f"{BASE_URL}/matches/{match_id}"
    try:
        data = fetch_json(url, api_key)
        goals = data.get("goals") or []
        print(f"[DEBUG] match {match_id}: {len(goals)} goals in response. Keys: {list(data.keys())}", file=__import__("sys").stderr)
        return data
    except Exception:
        return {}


# ---------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------
def escape_ics(text: str) -> str:
    return (text
            .replace("\\", "\\\\")
            .replace(";", "\\;")
            .replace(",", "\\,")
            .replace("\n", "\\n"))


def utc_str_to_local(utc_str: str, tz_offset_hours: int) -> datetime:
    utc_str = utc_str.replace("Z", "+00:00")
    dt_utc = datetime.fromisoformat(utc_str)
    return dt_utc + timedelta(hours=tz_offset_hours)


def format_round(match: dict) -> str:
    """Return a clean round string, e.g. 'Matchday 28' or 'Quarter-Finals'."""
    stage = match.get("stage", "")
    matchday = match.get("matchday")

    stage_labels = {
        "REGULAR_SEASON":    f"Matchday {matchday}" if matchday else "",
        "GROUP_STAGE":       f"Group Stage MD{matchday}" if matchday else "Group Stage",
        "ROUND_OF_16":       "Round of 16",
        "QUARTER_FINALS":    "Quarter-Finals",
        "SEMI_FINALS":       "Semi-Finals",
        "FINAL":             "Final",
        "3RD_PLACE":         "3rd Place",
        "PRELIMINARY_ROUND": "Preliminary Round",
        "PLAY_OFF_ROUND":    "Play-Off Round",
        "LAST_16":           "Round of 16",
        "LAST_32":           "Round of 32",
        "LAST_64":           "Round of 64",
    }
    label = stage_labels.get(stage)
    if label is not None:
        return label
    # Fallback: clean up raw stage string
    if stage:
        return stage.replace("_", " ").title()
    return f"Matchday {matchday}" if matchday else ""


def format_scorers(goals: list) -> str:
    """Returns plain text with real newlines; escape_ics() will handle \n conversion."""
    if not goals:
        return ""

    lines = ["Goals:"]
    for g in goals:
        minute  = g.get("minute", "?")
        extra   = g.get("injuryTime")
        scorer  = (g.get("scorer") or {}).get("name", "?")
        team    = (g.get("team") or {}).get("shortName") or (g.get("team") or {}).get("name", "")
        type_   = g.get("type", "")  # NORMAL, OWN_GOAL, PENALTY

        time_str = f"{minute}'"
        if extra:
            time_str += f"+{extra}"

        suffix = ""
        if type_ == "OWN_GOAL":
            suffix = " [og]"
        elif type_ == "PENALTY":
            suffix = " [pen]"

        team_str = f" ({team})" if team else ""
        lines.append(f"  {time_str} {scorer}{team_str}{suffix}")

    return "\n".join(lines)


def format_pl_standings(table: list) -> str:
    """
    Format top 5 + Man City's position.
    Returns e.g.:
      PL Standings:
       1. Arsenal          38pts  +25
       2. Man City         36pts  +20
       ...
      ---
      Man City: 2nd  36pts
    """
    if not table:
        return ""

    city_row = None
    for row in table:
        if row.get("team", {}).get("id") == MAN_CITY_TEAM_ID:
            city_row = row
            break

    def row_str(r):
        pos   = r.get("position", "?")
        name  = (r.get("team") or {}).get("shortName") or (r.get("team") or {}).get("name", "?")
        pts   = r.get("points", 0)
        gd    = r.get("goalDifference", 0)
        gd_str = f"+{gd}" if gd >= 0 else str(gd)
        return f"  {pos:>2}. {name:<18} {pts}pts  GD{gd_str}"

    lines = ["PL Standings (Top 5):"]
    top5 = table[:5]
    for r in top5:
        lines.append(row_str(r))

    if city_row and city_row not in top5:
        lines.append("  ...")
        lines.append(row_str(city_row))

    # Ordinal suffix for City's position
    if city_row:
        pos = city_row.get("position", "?")
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(pos if pos <= 20 else 0, "th")
        pts = city_row.get("points", 0)
        lines.append(f"Man City: {pos}{suffix}  {pts}pts")

    return "\n".join(lines)


# ---------------------------------------------------------------
# VEVENT builder
# ---------------------------------------------------------------
def build_vevent(match: dict, tz_name: str, tz_offset_hours: int,
                 pl_standings_str: str, api_key: str) -> list:

    competition  = match.get("competition", {}).get("name", "")
    comp_code    = match.get("competition", {}).get("code", "")
    home         = (match.get("homeTeam") or {}).get("shortName") or (match.get("homeTeam") or {}).get("name", "?")
    away         = (match.get("awayTeam") or {}).get("shortName") or (match.get("awayTeam") or {}).get("name", "?")
    status       = match.get("status", "")
    utc_date     = match.get("utcDate", "")
    match_id     = match.get("id", "")
    round_str    = format_round(match)

    # --- SUMMARY: always "(Home) vs (Away) - (League) (Round)", never changes ---
    summary = f"{home} vs {away} - {competition}"
    if round_str:
        summary += f" {round_str}"

    # --- DESCRIPTION: result info only for finished matches ---
    desc_parts = []

    if status == "FINISHED":
        score   = match.get("score", {})
        ft      = score.get("fullTime", {})
        gh, ga  = ft.get("home"), ft.get("away")

        if gh is not None and ga is not None:
            desc_parts.append(f"Result: {home} {gh}-{ga} {away}")

        # Fetch goal scorers from match detail endpoint
        detail = get_match_detail(api_key, match_id)
        goals  = detail.get("goals") or []
        if goals:
            scorers_str = format_scorers(goals)
            if scorers_str:
                desc_parts.append(scorers_str)

        # PL standings only for Premier League matches
        if comp_code == "PL" and pl_standings_str:
            desc_parts.append(pl_standings_str)

    description = escape_ics("\n\n".join(desc_parts)) if desc_parts else ""

    uid = str(uuid.uuid5(uuid.NAMESPACE_URL, f"footballdata-mancity-{match_id}"))

    if utc_date:
        dt_start = utc_str_to_local(utc_date, tz_offset_hours)
        dt_end   = dt_start + timedelta(minutes=105)
        vevent = [
            "BEGIN:VEVENT",
            f"UID:{uid}",
            f"DTSTART;TZID={tz_name}:{dt_start.strftime('%Y%m%dT%H%M%S')}",
            f"DTEND;TZID={tz_name}:{dt_end.strftime('%Y%m%dT%H%M%S')}",
            f"SUMMARY:{escape_ics(summary)}",
        ]
        if description:
            vevent.append(f"DESCRIPTION:{description}")
        vevent.append("END:VEVENT")
        return vevent
    else:
        vevent = [
            "BEGIN:VEVENT",
            f"UID:{uid}",
            "DTSTART;VALUE=DATE:19700101",
            f"SUMMARY:{escape_ics(summary)} (TBC)",
        ]
        if description:
            vevent.append(f"DESCRIPTION:{description}")
        vevent.append("END:VEVENT")
        return vevent


# ---------------------------------------------------------------
# ICS builder
# ---------------------------------------------------------------
def generate_ics(matches: list, tz_name: str, tz_offset_hours: int,
                 pl_standings_str: str, api_key: str) -> str:
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//ManCity Calendar//EN",
        "CALSCALE:GREGORIAN",
        "X-WR-CALNAME:Manchester City FC",
        f"X-WR-TIMEZONE:{tz_name}",
    ]
    for match in matches:
        lines.extend(build_vevent(match, tz_name, tz_offset_hours,
                                  pl_standings_str, api_key))
    lines.append("END:VCALENDAR")
    print(f"[INFO] {len(matches)} events written to ICS", file=sys.stderr)
    return "\r\n".join(lines) + "\r\n"


# ---------------------------------------------------------------
# Main
# ---------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="Man City ICS generator (football-data.org)")
    parser.add_argument("--api-key",   required=True)
    parser.add_argument("--output",    default="city_official.ics")
    parser.add_argument("--timezone",  default="Asia/Tokyo")
    parser.add_argument("--tz-offset", type=int, default=9)
    args = parser.parse_args()

    matches = get_fixtures(args.api_key)
    if not matches:
        print("[WARN] No fixtures found. Check your API key.", file=sys.stderr)
        sys.exit(1)

    pl_table        = get_pl_standings(args.api_key)
    pl_standings_str = format_pl_standings(pl_table)

    ics = generate_ics(matches, args.timezone, args.tz_offset,
                       pl_standings_str, args.api_key)

    with open(args.output, "w", encoding="utf-8") as f:
        f.write(ics)
    print(f"[OK] {args.output} generated", file=sys.stderr)


if __name__ == "__main__":
    main()
