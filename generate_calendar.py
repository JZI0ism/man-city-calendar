#!/usr/bin/env python3
"""
Manchester City 試合日程 → ICS 自動生成スクリプト
データソース: API-Sports / API-Football v3

使い方:
  python generate_mancity_ics.py --api-key YOUR_API_KEY

オプション:
  --api-key     API-Sports の APIキー (必須)
  --output      出力ファイル名 (デフォルト: city_official.ics)
  --timezone    ICSに記載するタイムゾーン名 (デフォルト: Asia/Tokyo)
  --tz-offset   UTCからのオフセット時間 (デフォルト: 9)
  --season      シーズン開始年 (デフォルト: 2024 → 2024/25)
  --via-rapidapi RapidAPI経由で使う場合に指定

APIキーの取得:
  https://dashboard.api-sports.io/ で無料登録（1日100リクエスト）

Man City チームID : 50
主な大会リーグID:
  プレミアリーグ       : 39
  FAカップ             : 45
  EFLカップ            : 48
  チャンピオンズリーグ  : 2
  ヨーロッパリーグ     : 3
"""

import argparse
import json
import sys
import uuid
from datetime import datetime, timedelta
from urllib.request import urlopen, Request
from urllib.error import HTTPError, URLError

# ---------------------------------------------------------------
# 定数
# ---------------------------------------------------------------
MAN_CITY_TEAM_ID = 50
BASE_URL_APISPORTS = "https://v3.football.api-sports.io"
BASE_URL_RAPIDAPI  = "https://api-football-v1.p.rapidapi.com/v3"

# 取得対象のリーグID
TARGET_LEAGUES = {
    39: "Premier League",
    45: "FA Cup",
    48: "EFL Cup",
    2:  "Champions League",
    3:  "Europa League",
}

# ---------------------------------------------------------------
# API ヘルパー
# ---------------------------------------------------------------
def make_headers(api_key: str, via_rapidapi: bool) -> dict:
    if via_rapidapi:
        return {
            "x-rapidapi-key":  api_key,
            "x-rapidapi-host": "api-football-v1.p.rapidapi.com",
        }
    return {"x-apisports-key": api_key}


def fetch_json(url: str, headers: dict) -> dict:
    req = Request(url, headers=headers)
    try:
        with urlopen(req, timeout=15) as res:
            return json.loads(res.read().decode())
    except HTTPError as e:
        body = e.read().decode(errors="replace")
        print(f"[ERROR] HTTP {e.code}: {url}", file=sys.stderr)
        print(f"        レスポンス: {body[:300]}", file=sys.stderr)
        if e.code == 403:
            print("  → APIキーが無効か、プランの制限に達した可能性があります。", file=sys.stderr)
        raise
    except URLError as e:
        print(f"[ERROR] 接続失敗: {e.reason}", file=sys.stderr)
        raise


def get_fixtures(api_key: str, season: int, via_rapidapi: bool) -> list:
    """Man City の全試合を取得（複数リーグ横断）"""
    base = BASE_URL_RAPIDAPI if via_rapidapi else BASE_URL_APISPORTS
    headers = make_headers(api_key, via_rapidapi)
    all_fixtures = []
    seen_ids = set()

    for league_id, league_name in TARGET_LEAGUES.items():
        url = f"{base}/fixtures?team={MAN_CITY_TEAM_ID}&season={season}&league={league_id}"
        print(f"[INFO] 取得中: {league_name} (league={league_id}, season={season})", file=sys.stderr)
        try:
            data = fetch_json(url, headers)
        except Exception:
            print(f"[WARN] {league_name} の取得をスキップしました", file=sys.stderr)
            continue

        errors = data.get("errors", {})
        if errors:
            print(f"[WARN] APIエラー: {errors}", file=sys.stderr)
            continue

        fixtures = data.get("response", [])
        print(f"       → {len(fixtures)} 件", file=sys.stderr)

        for f in fixtures:
            fid = f.get("fixture", {}).get("id")
            if fid and fid not in seen_ids:
                seen_ids.add(fid)
                all_fixtures.append(f)

    print(f"[INFO] 合計 {len(all_fixtures)} 件の試合を取得しました", file=sys.stderr)
    return all_fixtures


# ---------------------------------------------------------------
# ICS 生成ヘルパー
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


def build_vevent(fixture: dict, tz_name: str, tz_offset_hours: int) -> list:
    fix         = fixture.get("fixture", {})
    teams       = fixture.get("teams", {})
    goals       = fixture.get("goals", {})
    league_info = fixture.get("league", {})

    home_name    = teams.get("home", {}).get("name", "?")
    away_name    = teams.get("away", {}).get("name", "?")
    competition  = league_info.get("name", "")
    round_name   = league_info.get("round", "")
    status_long  = fix.get("status", {}).get("long", "")
    status_short = fix.get("status", {}).get("short", "")
    venue_name   = fix.get("venue", {}).get("name", "") or ""
    utc_date     = fix.get("date", "")
    fixture_id   = fix.get("id", "")

    # サマリー（終了試合はスコア付き）
    if status_short == "FT":
        g_home = goals.get("home", "-")
        g_away = goals.get("away", "-")
        summary = f"{home_name} {g_home}-{g_away} {away_name} [{competition}]"
    else:
        summary = f"{home_name} vs {away_name} [{competition}]"

    desc_parts = [competition, round_name,
                  f"会場: {venue_name}" if venue_name else "",
                  f"状態: {status_long}"]
    description = escape_ics(" | ".join(p for p in desc_parts if p))

    uid = str(uuid.uuid5(uuid.NAMESPACE_URL, f"apisports-mancity-{fixture_id}"))

    if utc_date:
        dt_start = utc_str_to_local(utc_date, tz_offset_hours)
        dt_end   = dt_start + timedelta(minutes=105)
        return [
            "BEGIN:VEVENT",
            f"UID:{uid}",
            f"DTSTART;TZID={tz_name}:{dt_start.strftime('%Y%m%dT%H%M%S')}",
            f"DTEND;TZID={tz_name}:{dt_end.strftime('%Y%m%dT%H%M%S')}",
            f"SUMMARY:{escape_ics(summary)}",
            f"DESCRIPTION:{description}",
            f"LOCATION:{escape_ics(venue_name)}",
            "END:VEVENT",
        ]
    else:
        return [
            "BEGIN:VEVENT",
            f"UID:{uid}",
            "DTSTART;VALUE=DATE:19700101",
            f"SUMMARY:{escape_ics(summary)} (日時未定)",
            f"DESCRIPTION:{description}",
            "END:VEVENT",
        ]


def generate_ics(fixtures: list, tz_name: str, tz_offset_hours: int) -> str:
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//ManCity Calendar//EN",
        "CALSCALE:GREGORIAN",
        "X-WR-CALNAME:Manchester City FC",
        f"X-WR-TIMEZONE:{tz_name}",
        "X-WR-CALDESC:Manchester City FC 試合日程 (自動生成 via API-Sports)",
    ]
    for fixture in fixtures:
        lines.extend(build_vevent(fixture, tz_name, tz_offset_hours))
    lines.append("END:VCALENDAR")
    print(f"[INFO] {len(fixtures)} 件のイベントを ICS に出力しました", file=sys.stderr)
    return "\r\n".join(lines) + "\r\n"


# ---------------------------------------------------------------
# メイン
# ---------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="Man City 試合日程 ICS 生成 (API-Sports版)")
    parser.add_argument("--api-key",      required=True)
    parser.add_argument("--output",       default="city_official.ics")
    parser.add_argument("--timezone",     default="Asia/Tokyo")
    parser.add_argument("--tz-offset",    type=int, default=9)
    parser.add_argument("--season",       type=int, default=2024)
    parser.add_argument("--via-rapidapi", action="store_true")
    args = parser.parse_args()

    fixtures = get_fixtures(args.api_key, args.season, args.via_rapidapi)
    if not fixtures:
        print("[WARN] 試合データが0件です。APIキーやシーズン番号を確認してください。", file=sys.stderr)
        sys.exit(1)

    ics = generate_ics(fixtures, args.timezone, args.tz_offset)
    with open(args.output, "w", encoding="utf-8") as f:
        f.write(ics)
    print(f"[OK] {args.output} を生成しました", file=sys.stderr)


if __name__ == "__main__":
    main()
