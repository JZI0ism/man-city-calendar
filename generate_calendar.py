import os
import requests
from datetime import datetime, timedelta, timezone

API_KEY = os.environ["API_FOOTBALL_KEY"]

TEAM_ID = 50
PREMIER_LEAGUE_ID = 39
BASE = "https://v3.football.api-sports.io"

headers = {
    "x-apisports-key": API_KEY
}

JST = timezone(timedelta(hours=9))


def get_json(url):
    r = requests.get(url, headers=headers)
    r.raise_for_status()
    return r.json()


def current_season():

    now = datetime.now(JST)

    if now.month >= 7:
        return now.year
    else:
        return now.year - 1


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


def get_premier_league_table(season):

    url = f"{BASE}/standings?league={PREMIER_LEAGUE_ID}&season={season}"

    res = get_json(url)

    table = res["response"][0]["league"]["standings"][0]

    top5 = []
    city_pos = None

    for t in table[:5]:
        top5.append(f'{t["rank"]}. {t["team"]["name"]}')

    for t in table:
        if t["team"]["id"] == TEAM_ID:
            city_pos = t["rank"]

    return top5, city_pos


def build_description(match, season):

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
            desc.append("Scorers")
            desc.extend(scorers)
            desc.append("")

        if match["league"]["id"] == PREMIER_LEAGUE_ID:

            top5, city_pos = get_premier_league_table(season)

            desc.append("Premier League Top 5")
            desc.extend(top5)
            desc.append("")
            desc.append("Manchester City Position")
            desc.append(str(city_pos))

    return "\\n".join(desc)


def build_event(match, season):

    fixture_id = match["fixture"]["id"]

    home = match["teams"]["home"]["name"]
    away = match["teams"]["away"]["name"]

    league = match["league"]["name"]
    round_name = match["league"]["round"]

    stadium = match["fixture"]["venue"]["name"]

    start, end = convert_time(match["fixture"]["date"])

    title = f"{home} vs {away} - {league} ({round_name})"

    description = build_description(match, season)

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


def write_calendar(events):

    with open("city_official.ics", "w") as f:

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
    seen = set()

    season_now = current_season()
    seasons = [season_now, season_now + 1]

    for season in seasons:

        data = get_json(
            f"{BASE}/fixtures?team={TEAM_ID}&season={season}"
        )

        for match in data["response"]:

            fixture_id = match["fixture"]["id"]

            if fixture_id in seen:
                continue

            seen.add(fixture_id)

            events.append(build_event(match, season))

    write_calendar(events)


main()
