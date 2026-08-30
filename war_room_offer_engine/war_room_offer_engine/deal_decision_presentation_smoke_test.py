from __future__ import annotations

from pathlib import Path


SOURCE = Path(__file__).with_name("deal_decision_ui.py").read_text(encoding="utf-8")


def check(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)
    print(f"OK: {message}")


check(
    'with st.expander("Optional deal details", expanded=False):' in SOURCE,
    "optional negotiation, media, and refresh controls stay collapsed by default",
)
check(
    'with st.expander("Negotiation Center", expanded=True):' not in SOURCE,
    "legacy always-open Negotiation Center does not return",
)

optional_start = SOURCE.index('with st.expander("Optional deal details", expanded=False):')
buttons_start = SOURCE.index('buttons = st.columns([3, 1])', optional_start)
optional_block = SOURCE[optional_start:buttons_start]
check('key="decision_media"' in optional_block, "property media remains available inside optional details")
check(
    'key="deal_library_force_refresh"' in optional_block,
    "intentional paid-data refresh remains available inside optional details",
)

render_start = SOURCE.index("def _render_decision")
render_end = SOURCE.index("def _reset", render_start)
render_block = SOURCE[render_start:render_end]
for label in ["Starting Offer", "Absolute Maximum", "Current Deal Price", "Confidence"]:
    check(label in render_block, f"primary recommendation keeps {label}")
check(
    render_block.index("Starting Offer") < render_block.index("Absolute Maximum") < render_block.index("Current Deal Price") < render_block.index("Confidence"),
    "primary money and confidence metrics stay in operator-first order",
)
check('**Next action:**' in render_block, "result clearly labels the next action")
check(
    'with st.expander("How this was calculated", expanded=False):' in render_block,
    "formula details stay available without crowding the recommendation",
)

print("Deal Decision Center presentation smoke test passed.")
