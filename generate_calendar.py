import requests
from datetime import datetime, timedelta, timezone

API_KEY = "YOUR_API_KEY"
TEAM_ID = 50

JST = timezone(timedelta(hours=9))

headers = {
    "x-apisports-key": API_KEY
}

fixtures_url = "https://v3.football.api-sports.io/fixtures?team=50&season=2025"

res = requests.get(fixtures_url, headers=headers)
data = res.json()

official_events = []
friendly_events = []

for match in data["response"]:

    home = match["teams"]["home"]["name"]
    away = match["teams"]["away"]["name"]

    league = match["league"]["name"]
    round_name = match["league"]["round"]

    stadium = match["fixture"]["venue"]["name"]

    date_utc = datetime.fromisoformat(match["fixture"]["date"].replace("Z", "+00:00"))
    date_jst = date_utc.astimezone(JST)

    end_time = date_jst + timedelta(hours=2)

    dtstart = date_jst.strftime("%Y%m%dT%H%M%S")
    dtend = end_time.strftime("%Y%m%dT%H%M%S")

    title = f"{home} vs {away} - {league} ({round_name})"

    event = f"""BEGIN:VEVENT
SUMMARY:{title}
LOCATION:{stadium}
DTSTART:{dtstart}
DTEND:{dtend}
END:VEVENT
"""

    if league == "Friendlies Clubs":
        friendly_events.append(event)
    else:
        official_events.append(event)

def write_calendar(filename, events):

    with open(filename, "w") as f:
        f.write("BEGIN:VCALENDAR\n")
        f.write("VERSION:2.0\n")

        for e in events:
            f.write(e)

        f.write("END:VCALENDAR")

write_calendar("city_official.ics", official_events)
write_calendar("city_friendly.ics", friendly_events)
