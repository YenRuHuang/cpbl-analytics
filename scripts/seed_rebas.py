"""Import Rebas Open Data into SQLite.

Usage:
    cd ~/Documents/cpbl-analytics
    uv run python scripts/seed_rebas.py
    uv run python scripts/seed_rebas.py --data-dir data/rebas_raw
    uv run python scripts/seed_rebas.py --data-dir data/rebas_raw --download
"""

import argparse
import logging
import sys

from src.config.settings import get_settings
from src.db.engine import get_db, init_db
from src.etl.rebas_loader import download_rebas_data, load_all_games

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s  %(name)s  %(message)s",
)
logger = logging.getLogger(__name__)


def main() -> int:
    settings = get_settings()

    parser = argparse.ArgumentParser(
        description="Import Rebas Open Data JSON files into SQLite."
    )
    parser.add_argument(
        "--data-dir",
        default=settings.rebas_data_dir,
        help=f"Directory containing Rebas JSON files (default: {settings.rebas_data_dir})",
    )
    parser.add_argument(
        "--download",
        action="store_true",
        help="Clone / pull the rebas.tw-open-data repo before loading",
    )
    args = parser.parse_args()

    print("=== Rebas Open Data Importer ===")

    # Init DB
    init_db()
    print("DB initialized")

    # Optionally download / update the repo
    data_dir = args.data_dir
    if args.download:
        print(f"Downloading Rebas Open Data into {data_dir} ...")
        try:
            repo_path = download_rebas_data(data_dir)
            # Use the cloned repo as data source
            data_dir = str(repo_path)
            print(f"Download complete: {data_dir}")
        except RuntimeError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 1

    # Load all JSON files
    print(f"Loading games from {data_dir} ...")
    with get_db() as db:
        stats = load_all_games(db, data_dir)

    print()
    print("─── Summary ───────────────────────────────")
    print(f"  Loaded : {stats['loaded']:>6}")
    print(f"  Skipped: {stats['skipped']:>6}  (already in DB)")
    print(f"  Errors : {stats['errors']:>6}")
    print("────────────────────────────────────────────")

    if stats["errors"] > 0:
        print(f"WARNING: {stats['errors']} files failed — check logs above")

    # DB row counts
    from sqlalchemy import text

    with get_db() as db:
        games = db.execute(
            text("SELECT COUNT(*) FROM games WHERE source='rebas'")
        ).scalar()
        pa_count = db.execute(
            text("SELECT COUNT(*) FROM plate_appearances WHERE source='rebas'")
        ).scalar()
        pitch_count = db.execute(
            text("SELECT COUNT(*) FROM pitch_events WHERE source='rebas'")
        ).scalar()
        bat_count = db.execute(
            text("SELECT COUNT(*) FROM batter_box WHERE source='rebas'")
        ).scalar()
        pit_count = db.execute(
            text("SELECT COUNT(*) FROM pitcher_box WHERE source='rebas'")
        ).scalar()

    print()
    print("DB rows (source=rebas):")
    print(f"  games             : {games}")
    print(f"  plate_appearances : {pa_count}")
    print(f"  pitch_events      : {pitch_count}")
    print(f"  batter_box        : {bat_count}")
    print(f"  pitcher_box       : {pit_count}")

    return 0 if stats["errors"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
