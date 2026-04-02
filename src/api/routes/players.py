"""Player endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from src.api.schemas.responses import PlayerResponse
from src.db.engine import get_db

router = APIRouter(prefix="/api/players", tags=["players"])


@router.get("", response_model=list[PlayerResponse])
def list_players(
    team: str | None = Query(default=None, description="Filter by team code, e.g. 'CTBC'"),
) -> list[PlayerResponse]:
    """List all players, optionally filtered by team."""
    from sqlalchemy import text

    with get_db() as db:
        if team:
            rows = db.execute(
                text("SELECT * FROM players WHERE team = :team ORDER BY name_zh"),
                {"team": team},
            ).fetchall()
        else:
            rows = db.execute(
                text("SELECT * FROM players ORDER BY name_zh")
            ).fetchall()

    return [
        PlayerResponse(
            player_id=r.player_id,
            name_zh=r.name_zh,
            name_en=r.name_en,
            team=r.team,
            position=r.position,
            bats=r.bats,
            throws=r.throws,
        )
        for r in rows
    ]


@router.get("/{player_id}", response_model=PlayerResponse)
def get_player(player_id: str) -> PlayerResponse:
    """Fetch a single player by player_id."""
    from sqlalchemy import text

    with get_db() as db:
        row = db.execute(
            text("SELECT * FROM players WHERE player_id = :pid"),
            {"pid": player_id},
        ).fetchone()

    if row is None:
        raise HTTPException(status_code=404, detail=f"Player '{player_id}' not found")

    return PlayerResponse(
        player_id=row.player_id,
        name_zh=row.name_zh,
        name_en=row.name_en,
        team=row.team,
        position=row.position,
        bats=row.bats,
        throws=row.throws,
    )
