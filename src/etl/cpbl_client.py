"""CPBL 官網公開資料整合 — 從 cpbl.com.tw 取得比賽資料。"""

import json
import time
from dataclasses import dataclass, field
from pathlib import Path

import httpx

from src.config.settings import DATA_DIR, get_settings


@dataclass(frozen=True)
class GameDetail:
    game_sno: int
    game_date: str
    home_team: str
    away_team: str
    home_score: int
    away_score: int
    venue: str
    status: str  # 'final', 'in_progress', 'postponed'


@dataclass(frozen=True)
class BattingLine:
    player_name: str
    team: str  # 'home' | 'away'
    ab: int
    h: int
    hr: int
    rbi: int
    bb: int
    so: int
    sb: int
    lob: int
    left_behind_lob: int


@dataclass(frozen=True)
class PitchingLine:
    player_name: str
    team: str
    ip: float
    h: int
    r: int
    er: int
    bb: int
    so: int
    hr: int
    pitch_count: int


@dataclass(frozen=True)
class PlayByPlay:
    inning_seq: int
    batter_name: str
    pitcher_name: str
    ball_count: int
    strike_count: int
    out_count: int
    first_base: str
    second_base: str
    third_base: str
    action_name: str
    batting_action: str
    is_strike: bool
    is_ball: bool
    home_score: int
    away_score: int


@dataclass
class GameData:
    detail: GameDetail
    batting: list[BattingLine] = field(default_factory=list)
    pitching: list[PitchingLine] = field(default_factory=list)
    plays: list[PlayByPlay] = field(default_factory=list)
    raw_json: dict = field(default_factory=dict)


class CpblClient:
    """CPBL 官網公開資料整合 client。"""

    def __init__(self) -> None:
        settings = get_settings()
        self.base_url = settings.cpbl_base_url
        self.rate_limit = settings.cpbl_rate_limit_seconds
        self.cache_dir = Path(DATA_DIR / "cpbl_raw")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._last_request_time = 0.0

    def _rate_limit_wait(self) -> None:
        elapsed = time.time() - self._last_request_time
        if elapsed < self.rate_limit:
            time.sleep(self.rate_limit - elapsed)
        self._last_request_time = time.time()

    def fetch_game(self, year: int, game_sno: int, kind_code: str = "A") -> GameData | None:
        """Fetch a single game's data. Returns None if game doesn't exist."""
        # Check disk cache first
        cache_path = self.cache_dir / f"{year}_{kind_code}_{game_sno}.json"
        if cache_path.exists():
            raw = json.loads(cache_path.read_text())
            if raw.get("Success"):
                return self._parse_game(raw, game_sno)
            return None

        # Fetch from CPBL
        self._rate_limit_wait()
        try:
            with httpx.Client(timeout=15) as client:
                resp = client.post(
                    f"{self.base_url}/box/getlive",
                    data={"year": year, "kindCode": kind_code, "gameSno": game_sno},
                    headers={"User-Agent": "CPBL-Analytics/0.1"},
                )
                resp.raise_for_status()
                raw = resp.json()
        except (httpx.HTTPError, json.JSONDecodeError):
            return None

        # Cache to disk
        cache_path.write_text(json.dumps(raw, ensure_ascii=False))

        if not raw.get("Success"):
            return None
        return self._parse_game(raw, game_sno)

    def fetch_season(
        self, year: int, kind_code: str = "A", max_empty: int = 3
    ) -> list[GameData]:
        """Fetch all games for a season. Stops after max_empty consecutive empty results."""
        games: list[GameData] = []
        empty_streak = 0

        for sno in range(1, 500):
            game = self.fetch_game(year, sno, kind_code)
            if game is None:
                empty_streak += 1
                if empty_streak >= max_empty:
                    break
                continue
            empty_streak = 0
            games.append(game)
            if len(games) % 10 == 0:
                print(f"  {len(games)} games fetched...")

        return games

    def _parse_game(self, raw: dict, game_sno: int) -> GameData | None:
        """Parse raw API response into typed GameData.

        優先使用 CurtGameDetailJson（對應請求的 gameSno），
        fallback 到 GameDetailJson 中 GameSno 匹配的項目。
        """
        d = None

        # 優先：CurtGameDetailJson 是對應 gameSno 的正確資料
        curt_json = raw.get("CurtGameDetailJson")
        if curt_json:
            try:
                d = json.loads(curt_json)
            except (json.JSONDecodeError, TypeError):
                d = None

        # Fallback：從 GameDetailJson array 中找匹配的 gameSno
        if d is None:
            try:
                details_raw = json.loads(raw.get("GameDetailJson", "[]"))
                if not details_raw:
                    return None
                # 找 GameSno 匹配的，找不到就用第一個
                d = next(
                    (g for g in details_raw if g.get("GameSno") == game_sno),
                    details_raw[0],
                )
            except (json.JSONDecodeError, IndexError):
                return None

        if d is None:
            return None

        # Parse game detail
        status = "final" if d.get("GameStatus") == 3 else "in_progress" if d.get("GameStatus") == 2 else "unknown"
        detail = GameDetail(
            game_sno=game_sno,
            game_date=str(d.get("GameDate", ""))[:10],
            home_team=d.get("HomeTeamName", ""),
            away_team=d.get("VisitingTeamName", ""),
            home_score=int(d.get("HomeTotalScore", 0) or 0),
            away_score=int(d.get("VisitingTotalScore", 0) or 0),
            venue=d.get("FieldAbbe", ""),
            status=status,
        )

        # Parse batting lines
        batting = self._parse_batting(raw.get("BattingJson", "[]"))

        # Parse pitching lines
        pitching = self._parse_pitching(raw.get("PitchingJson", "[]"))

        # Parse play-by-play
        plays = self._parse_plays(raw.get("LiveLogJson", "[]"))

        return GameData(
            detail=detail,
            batting=batting,
            pitching=pitching,
            plays=plays,
            raw_json=raw,
        )

    def _parse_batting(self, batting_json: str) -> list[BattingLine]:
        try:
            rows = json.loads(batting_json) if isinstance(batting_json, str) else batting_json
        except json.JSONDecodeError:
            return []

        if not rows:
            return []

        lines: list[BattingLine] = []
        for row in rows:
            team = "home" if row.get("VisitingHomeType") in ("H", "2") else "away"
            lines.append(BattingLine(
                player_name=row.get("HitterName", ""),
                team=team,
                ab=int(row.get("HittingCnt", 0) or 0),
                h=int(row.get("HitCnt", 0) or 0),
                hr=int(row.get("HomeRunCnt", 0) or 0),
                rbi=int(row.get("RunBattedINCnt", 0) or 0),
                bb=int(row.get("BasesONBallsCnt", 0) or 0),
                so=int(row.get("StrikeOutCnt", 0) or 0),
                sb=int(row.get("StealBaseOKCnt", 0) or 0),
                lob=int(row.get("Lobs", 0) or 0),
                left_behind_lob=int(row.get("LeftBehindLobs", 0) or 0),
            ))
        return lines

    def _parse_pitching(self, pitching_json: str) -> list[PitchingLine]:
        try:
            rows = json.loads(pitching_json) if isinstance(pitching_json, str) else pitching_json
        except json.JSONDecodeError:
            return []

        if not rows:
            return []

        lines: list[PitchingLine] = []
        for row in rows:
            team = "home" if row.get("VisitingHomeType") in ("H", "2") else "away"
            # Parse IP: "5.2" means 5 and 2/3 innings
            ip_raw = row.get("InningPitchedCnt", 0) or 0
            ip_div3 = row.get("InningPitchedDiv3Cnt", 0) or 0
            ip = float(ip_raw) + float(ip_div3) / 3.0

            lines.append(PitchingLine(
                player_name=row.get("PitcherName", ""),
                team=team,
                ip=round(ip, 1),
                h=int(row.get("HitCnt", 0) or 0),
                r=int(row.get("RunCnt", 0) or 0),
                er=int(row.get("EarnedRunCnt", 0) or 0),
                bb=int(row.get("BasesONBallsCnt", 0) or 0),
                so=int(row.get("StrikeOutCnt", 0) or 0),
                hr=int(row.get("HomeRunCnt", 0) or 0),
                pitch_count=int(row.get("PitchCnt", 0) or 0),
            ))
        return lines

    def _parse_plays(self, plays_json: str) -> list[PlayByPlay]:
        try:
            rows = json.loads(plays_json) if isinstance(plays_json, str) else plays_json
        except json.JSONDecodeError:
            return []

        if not rows:
            return []

        plays: list[PlayByPlay] = []
        for row in rows:
            plays.append(PlayByPlay(
                inning_seq=int(row.get("InningSeq", 0) or 0),
                batter_name=row.get("HitterName", ""),
                pitcher_name=row.get("PitcherName", ""),
                ball_count=int(row.get("BallCnt", 0) or 0),
                strike_count=int(row.get("StrikeCnt", 0) or 0),
                out_count=int(row.get("OutCnt", 0) or 0),
                first_base=row.get("FirstBase", ""),
                second_base=row.get("SecondBase", ""),
                third_base=row.get("ThirdBase", ""),
                action_name=row.get("ActionName", ""),
                batting_action=row.get("BattingActionName", ""),
                is_strike=bool(row.get("IsStrike")),
                is_ball=bool(row.get("IsBall")),
                home_score=int(row.get("HomeScore", 0) or 0),
                away_score=int(row.get("VisitingScore", 0) or 0),
            ))
        return plays
