import requests
from datetime import datetime, timedelta
import os

API_KEY = os.environ["API_FOOTBALL_KEY"]

headers = {
    "x-apisports-key": API_KEY
}

url = "https://v3.football.api-sports.io/fixtures?team=50&season=2024"

res = requests.get(url, headers=headers).json()

if "response" not in res:
    print(res)
    raise Exception("API error")

events = []

for match in res["response"]:

    home = match["teams"]["home"]["name"]
    away = match["teams"]["away"]["name"]

    league = match["league"]["name"]
    round_name = match["league"]["round"]

    stadium = match["fixture"]["venue"]["name"]

    date = match["fixture"]["date"]

    start = datetime.fromisoformat(date.replace("Z","+00:00"))
    end = start + timedelta(hours=2)

    title = f"{home} vs {away} - {league} ({round_name})"

    event = f"""BEGIN:VEVENT
SUMMARY:{title}
LOCATION:{stadium}
DTSTART:{start.strftime('%Y%m%dT%H%M%SZ')}
DTEND:{end.strftime('%Y%m%dT%H%M%SZ')}
END:VEVENT
"""

    events.append(event)

calendar = "BEGIN:VCALENDAR\nVERSION:2.0\n"

for e in events:
    calendar += e

calendar += "END:VCALENDAR"

with open("city_official.ics","w") as f:
    f.write(calendar)
