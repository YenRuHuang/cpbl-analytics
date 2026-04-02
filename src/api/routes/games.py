"""Game endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from src.api.schemas.responses import GameResponse, PaginatedResponse
from src.db.engine import get_db

router = APIRouter(prefix="/api/games", tags=["games"])


@router.get("", response_model=PaginatedResponse)
def list_games(
    year: int | None = Query(default=None, description="Season year, e.g. 2026"),
    team: str | None = Query(default=None, description="Filter by home or away team code"),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=50, ge=1, le=200),
) -> PaginatedResponse:
    """List games with optional year / team filter, paginated."""
    from sqlalchemy import text

    conditions: list[str] = []
    params: dict = {}

    if year is not None:
        conditions.append("g.year = :year")
        params["year"] = year
    if team is not None:
        conditions.append("(g.home_team = :team OR g.away_team = :team)")
        params["team"] = team

    where_clause = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    with get_db() as db:
        total_row = db.execute(
            text(f"SELECT COUNT(*) as cnt FROM games g {where_clause}"),
            params,
        ).fetchone()
        total = total_row.cnt if total_row else 0

        offset = (page - 1) * per_page
        params["limit"] = per_page
        params["offset"] = offset

        rows = db.execute(
            text(
                f"""
                SELECT * FROM games g
                {where_clause}
                ORDER BY g.game_date DESC
                LIMIT :limit OFFSET :offset
                """
            ),
            params,
        ).fetchall()

    items = [
        GameResponse(
            game_id=r.game_id,
            game_date=str(r.game_date),
            year=r.year,
            home_team=r.home_team,
            away_team=r.away_team,
            home_score=r.home_score,
            away_score=r.away_score,
            venue=r.venue,
            kind_code=r.kind_code,
            source=r.source,
        )
        for r in rows
    ]

    return PaginatedResponse(items=items, total=total, page=page, per_page=per_page)


@router.get("/{game_id}", response_model=GameResponse)
def get_game(game_id: str) -> GameResponse:
    """Fetch a single game by game_id."""
    from sqlalchemy import text

    with get_db() as db:
        row = db.execute(
            text("SELECT * FROM games WHERE game_id = :gid"),
            {"gid": game_id},
        ).fetchone()

    if row is None:
        raise HTTPException(status_code=404, detail=f"Game '{game_id}' not found")

    return GameResponse(
        game_id=row.game_id,
        game_date=str(row.game_date),
        year=row.year,
        home_team=row.home_team,
        away_team=row.away_team,
        home_score=row.home_score,
        away_score=row.away_score,
        venue=row.venue,
        kind_code=row.kind_code,
        source=row.source,
    )
