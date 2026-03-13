import os
import requests
from datetime import datetime, timedelta, timezone

API_KEY = os.environ["API_FOOTBALL_KEY"]

TEAM_ID = 50
SEASON = 2025

BASE = "https://v3.football.api-sports.io"

headers = {
    "x-apisports-key": API_KEY
}

JST = timezone(timedelta(hours=9))

LEAGUE_NAME_MAP = {
    "Premier League": "Premier League",
    "UEFA Champions League": "Champions League",
    "FA Cup": "FA Cup",
    "League Cup": "EFL Cup",
    "Community Shield": "Community Shield"
}

def get_json(url):
    r = requests.get(url, headers=headers)
    r.raise_for_status()
    return r.json()

def convert_time(date_string):

    utc = datetime.fromisoformat(date_string.replace("Z", "+00:00"))
    jst = utc.astimezone(JST)

    end = jst + timedelta(hours=2)

    return (
        jst.strftime("%Y%m%dT%H%M%S"),
        end.strftime("%Y%m%dT%H%M%S")
    )

def get_goalscorers(fixture_id):

    url = f"{BASE}/fixtures/events?fixture={fixture_id}"

    res = get_json(url)

    scorers = []

    for e in res["response"]:

        if e["type"] == "Goal":

            player = e["player"]["name"]
            minute = e["time"]["elapsed"]

            scorers.append(f"{player} {minute}'")

    return scorers

def get_premier_league_table():

    url = f"{BASE}/standings?league=39&season={SEASON}"

    res = get_json(url)

    table = res["response"][0]["league"]["standings"][0]

    top5 = []
    city_pos = None

    for t in table[:5]:
        top5.append(f'{t["rank"]} {t["team"]["name"]}')

    for t in table:
        if t["team"]["id"] == TEAM_ID:
            city_pos = t["rank"]

    return top5, city_pos

def build_description(match):

    desc = []

    status = match["fixture"]["status"]["short"]

    home = match["teams"]["home"]["name"]
    away = match["teams"]["away"]["name"]

    if status == "FT":

        score_home = match["goals"]["home"]
        score_away = match["goals"]["away"]

        desc.append("Result")
        desc.append(f"{home} {score_home}-{score_away} {away}")
        desc.append("")

        scorers = get_goalscorers(match["fixture"]["id"])

        if scorers:
            desc.append("Goalscorers")
            desc.extend(scorers)
            desc.append("")

        if match["league"]["name"] == "Premier League":

            top5, city_pos = get_premier_league_table()

            desc.append("Premier League Top 5")
            desc.extend(top5)
            desc.append("")
            desc.append("Manchester City Position")
            desc.append(str(city_pos))

    return "\\n".join(desc)

def build_event(match):

    home = match["teams"]["home"]["name"]
    away = match["teams"]["away"]["name"]

    league_raw = match["league"]["name"]
    round_name = match["league"]["round"]

    league = LEAGUE_NAME_MAP.get(league_raw, league_raw)

    stadium = match["fixture"]["venue"]["name"]

    start, end = convert_time(match["fixture"]["date"])

    title = f"{home} vs {away} - {league} ({round_name})"

    description = build_description(match)

    event = f"""BEGIN:VEVENT
SUMMARY:{title}
LOCATION:{stadium}
DTSTART:{start}
DTEND:{end}
DESCRIPTION:{description}
END:VEVENT
"""

    return event

def main():

    fixtures = get_json(
        f"{BASE}/fixtures?team={TEAM_ID}&season={SEASON}"
    )

    official = []
    friendly = []

    for match in fixtures["response"]:

        league = match["league"]["name"]

        event = build_event(match)

        if league == "Friendlies Clubs":
            friendly.append(event)
        else:
            official.append(event)

    write_calendar("city_official.ics", official)
    write_calendar("city_friendly.ics", friendly)

def write_calendar(filename, events):

    with open(filename, "w") as f:

        f.write("BEGIN:VCALENDAR\n")
        f.write("VERSION:2.0\n")

        for e in events:
            f.write(e)

        f.write("END:VCALENDAR")

main()
