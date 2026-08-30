from __future__ import annotations

import runpy
from pathlib import Path


CANONICAL_APP = (
    Path(__file__).resolve().parent
    / "war_room_offer_engine"
    / "war_room_offer_engine"
    / "app.py"
)

if not CANONICAL_APP.exists():
    raise RuntimeError(
        "The canonical War Room Offer Engine app could not be found at "
        f"{CANONICAL_APP}."
    )

# Compatibility launcher only. The nested app is the single production UI.
runpy.run_path(str(CANONICAL_APP), run_name="__main__")
