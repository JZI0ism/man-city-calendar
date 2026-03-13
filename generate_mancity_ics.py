#!/usr/bin/env python3
"""
Manchester City 試合日程 → ICS 自動生成スクリプト
データソース: football-data.org (無料プラン・現シーズン対応)

使い方:
  python generate_mancity_ics.py --api-key YOUR_API_KEY

APIキーの取得 (無料):
  https://www.football-data.org/client/register

Man City チームID : 65
無料プランで使える大会:
  PL  : Premier League
  FAC : FA Cup
  CL  : UEFA Champions League
  ELC : EFL Cup (Football League Cup)
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
# 定数
# ---------------------------------------------------------------
MAN_CITY_TEAM_ID = 65
BASE_URL = "https://api.football-data.org/v4"

# 無料プランで利用可能な大会コード
TARGET_COMPETITIONS = {
    "PL":  "Premier League",
    "FAC": "FA Cup",
    "CL":  "UEFA Champions League",
    "ELC": "EFL Cup",
    "CLI": "FIFA Club World Cup",
}

# ---------------------------------------------------------------
# API ヘルパー
# ---------------------------------------------------------------
def fetch_json(url: str, api_key: str) -> dict:
    req = Request(url, headers={"X-Auth-Token": api_key})
    try:
        with urlopen(req, timeout=15) as res:
            return json.loads(res.read().decode())
    except HTTPError as e:
        body = e.read().decode(errors="replace")
        print(f"[ERROR] HTTP {e.code}: {url}", file=sys.stderr)
        print(f"        レスポンス: {body[:300]}", file=sys.stderr)
        raise
    except URLError as e:
        print(f"[ERROR] 接続失敗: {e.reason}", file=sys.stderr)
        raise


def get_fixtures(api_key: str) -> list:
    """Man City の全試合を取得（現シーズン・複数大会）"""
    url = f"{BASE_URL}/teams/{MAN_CITY_TEAM_ID}/matches"
    print(f"[INFO] Man City の試合データを取得中...", file=sys.stderr)
    try:
        data = fetch_json(url, api_key)
    except Exception:
        sys.exit(1)

    matches = data.get("matches", [])

    # 対象大会だけに絞る
    filtered = [
        m for m in matches
        if m.get("competition", {}).get("code") in TARGET_COMPETITIONS
    ]

    print(f"[INFO] {len(filtered)} 件の試合を取得しました（全{len(matches)}件中）", file=sys.stderr)
    return filtered


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


def build_vevent(match: dict, tz_name: str, tz_offset_hours: int) -> list:
    competition = match.get("competition", {}).get("name", "")
    home = (match.get("homeTeam") or {}).get("shortName") or (match.get("homeTeam") or {}).get("name", "?")
    away = (match.get("awayTeam") or {}).get("shortName") or (match.get("awayTeam") or {}).get("name", "?")
    status     = match.get("status", "")
    matchday   = match.get("matchday")
    utc_date   = match.get("utcDate", "")
    match_id   = match.get("id", "")
    venue      = (match.get("venue") or "")

    # スコア
    score = match.get("score", {})
    ft    = score.get("fullTime", {})
    gh, ga = ft.get("home"), ft.get("away")

    if status == "FINISHED" and gh is not None and ga is not None:
        summary = f"{home} {gh}-{ga} {away} [{competition}]"
    else:
        summary = f"{home} vs {away} [{competition}]"

    desc_parts = [competition]
    if matchday:
        desc_parts.append(f"第{matchday}節")
    desc_parts.append(f"状態: {status}")
    if venue:
        desc_parts.append(f"会場: {venue}")
    description = escape_ics(" | ".join(desc_parts))

    uid = str(uuid.uuid5(uuid.NAMESPACE_URL, f"footballdata-mancity-{match_id}"))

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
            f"LOCATION:{escape_ics(venue)}",
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


def generate_ics(matches: list, tz_name: str, tz_offset_hours: int) -> str:
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//ManCity Calendar//EN",
        "CALSCALE:GREGORIAN",
        "X-WR-CALNAME:Manchester City FC",
        f"X-WR-TIMEZONE:{tz_name}",
        "X-WR-CALDESC:Manchester City FC 試合日程 (自動生成 via football-data.org)",
    ]
    for match in matches:
        lines.extend(build_vevent(match, tz_name, tz_offset_hours))
    lines.append("END:VCALENDAR")
    print(f"[INFO] {len(matches)} 件のイベントを ICS に出力しました", file=sys.stderr)
    return "\r\n".join(lines) + "\r\n"


# ---------------------------------------------------------------
# メイン
# ---------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="Man City ICS生成 (football-data.org版)")
    parser.add_argument("--api-key",   required=True, help="football-data.org の APIキー")
    parser.add_argument("--output",    default="city_official.ics")
    parser.add_argument("--timezone",  default="Asia/Tokyo")
    parser.add_argument("--tz-offset", type=int, default=9)
    # --season は football-data.org では不要（常に現シーズンを返す）
    args = parser.parse_args()

    matches = get_fixtures(args.api_key)
    if not matches:
        print("[WARN] 試合データが0件です。APIキーを確認してください。", file=sys.stderr)
        sys.exit(1)

    ics = generate_ics(matches, args.timezone, args.tz_offset)
    with open(args.output, "w", encoding="utf-8") as f:
        f.write(ics)
    print(f"[OK] {args.output} を生成しました", file=sys.stderr)


if __name__ == "__main__":
    main()
