import os
import requests
from datetime import datetime, timedelta, timezone

API_KEY = os.environ["API_FOOTBALL_KEY"]

TEAM_ID = 50

BASE = "https://v3.football.api-sports.io"

headers = {
    "x-apisports-key": API_KEY
}

JST = timezone(timedelta(hours=9))

def current_season():

    now = datetime.now(JST)

    if now.month >= 7:
        return now.year
    else:
        return now.year - 1


SEASON = current_season()

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


def build_event(match):

    fixture_id = match["fixture"]["id"]

    home = match["teams"]["home"]["name"]
    away = match["teams"]["away"]["name"]

    league_raw = match["league"]["name"]
    round_name = match["league"]["round"]

    league = LEAGUE_NAME_MAP.get(league_raw, league_raw)

    stadium = match["fixture"]["venue"]["name"]

    start, end = convert_time(match["fixture"]["date"])

    title = f"{home} vs {away} - {league} ({round_name})"

    uid = f"{fixture_id}@mancity-calendar"

    event = f"""BEGIN:VEVENT
UID:{uid}
SUMMARY:{title}
LOCATION:{stadium}
DTSTART;TZID=Asia/Tokyo:{start}
DTEND;TZID=Asia/Tokyo:{end}
END:VEVENT
"""

    return event


def write_calendar(filename, events):

    with open(filename, "w") as f:

        f.write("BEGIN:VCALENDAR\n")
        f.write("VERSION:2.0\n")
        f.write("PRODID:-//ManCity Calendar//EN\n")
        f.write("CALSCALE:GREGORIAN\n")

        for e in events:
            f.write(e)

        f.write("END:VCALENDAR")


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


main()
