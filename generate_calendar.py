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
            desc.append("Goals")
            desc.extend(scorers)

    return "\\n".join(desc)


def build_event(match):

    fixture_id = match["fixture"]["id"]

    home = match["teams"]["home"]["name"]
    away = match["teams"]["away"]["name"]

    league = match["league"]["name"]
    round_name = match["league"]["round"]

    stadium = match["fixture"]["venue"]["name"]

    start, end = convert_time(match["fixture"]["date"])

    title = f"{home} vs {away} - {league} ({round_name})"

    description = build_description(match)

    uid = f"{fixture_id}@mancity-calendar"

    dtstamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    event = f"""BEGIN:VEVENT
UID:{uid}
DTSTAMP:{dtstamp}
SUMMARY:{title}
LOCATION:{stadium}
DTSTART;TZID=Asia/Tokyo:{start}
DTEND;TZID=Asia/Tokyo:{end}
DESCRIPTION:{description}
END:VEVENT
"""

    return event


def write_calendar(filename, events):

    with open(filename, "w") as f:

        f.write("BEGIN:VCALENDAR\n")
        f.write("VERSION:2.0\n")
        f.write("PRODID:-//ManCity Calendar//EN\n")
        f.write("CALSCALE:GREGORIAN\n")
        f.write("X-WR-TIMEZONE:Asia/Tokyo\n")

        for e in events:
            f.write(e)

        f.write("END:VCALENDAR")


def main():

    events = []

    # 過去＋未来の試合を必ず取得
    past = get_json(f"{BASE}/fixtures?team={TEAM_ID}&last=50")
    future = get_json(f"{BASE}/fixtures?team={TEAM_ID}&next=50")

    matches = past["response"] + future["response"]

    seen = set()

    for match in matches:

        fixture_id = match["fixture"]["id"]

        if fixture_id in seen:
            continue

        seen.add(fixture_id)

        event = build_event(match)

        events.append(event)

    write_calendar("city_official.ics", events)


main()
