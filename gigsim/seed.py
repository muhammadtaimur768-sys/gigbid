"""(Re)seed the GigSim database from gigsim/seed_data/*.json.

    python -m gigsim.seed            # uses GIGSIM_DATABASE_URL (default sqlite:///data/processed/gigsim.db)
"""
from __future__ import annotations

import json

from gigsim.storage import database_url, get_engine, seed


def main() -> None:
    url = database_url()
    counts = seed(get_engine(url))
    print(json.dumps(dict(database=url.split("@")[-1], counts=counts), indent=2))


if __name__ == "__main__":
    main()
