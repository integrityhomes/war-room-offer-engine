from __future__ import annotations

from deal_vault_snapshot import (
    build_snapshot,
    changed_fields,
    deal_identity,
    decode_snapshot,
    encode_snapshot,
    restore_snapshot,
    summary_from_state,
)


STATE = {
    "address": "1115 Matson Dr, Marion, VA 24354",
    "city": "Marion",
    "state": "VA",
    "zip": "24354",
    "decision_property_input": "1115 Matson Dr, Marion, VA 24354",
    "decision_strategy": "Auto — Choose Best",
    "decision_current_negotiated_price": 25000,
    "decision_result": {
        "decision": "BUY",
        "strategy": "Slow Flip — Keep",
        "first_offer": 28000,
        "hard_max": 32000,
    },
    "rent": 1040,
    "rentcast_rent_comp_count": 4,
    "rentcast_rent_comps": [
        {"address": "Rent 1", "rent": 1300},
        {"address": "Rent 2", "rent": 750},
        {"address": "Rent 3", "rent": 1350},
        {"address": "Rent 4", "rent": 1100},
    ],
    "arv": 35667,
    "arv_confidence": "Strong",
    "auto_sold_comps": [
        {"comp_address": "Sale 1", "sold_price": 34000},
        {"comp_address": "Sale 2", "sold_price": 37000},
        {"comp_address": "Sale 3", "sold_price": 36000},
    ],
    "repairs": 63476,
    "repair_notes": "Walkthrough notes retained without re-running the video model.",
    "decision_media": object(),
}

summary = summary_from_state(STATE)
assert summary["deal_id"].startswith("DV-")
assert summary["address"] == "1115 Matson Dr, Marion, VA 24354"
assert summary["decision"] == "BUY"
assert summary["deal_lane"] == "Slow Flip — Keep"
assert summary["negotiated_price"] == 25000

snapshot = build_snapshot(STATE, media_files=[])
assert "decision_media" not in snapshot["saved_state"]
assert snapshot["saved_state"]["rentcast_rent_comp_count"] == 4
assert len(snapshot["saved_state"]["auto_sold_comps"]) == 3

payload, trimmed = encode_snapshot(snapshot)
assert payload.startswith("z1:")
assert not trimmed
round_trip = decode_snapshot(payload)
assert round_trip == snapshot

restored = {}
count = restore_snapshot(restored, round_trip)
assert count > 10
assert restored["address"] == STATE["address"]
assert restored["rent"] == 1040
assert restored["decision_result"]["decision"] == "BUY"
assert restored["deal_vault_loaded_without_api_pull"] is True

updated_state = dict(STATE)
updated_state["decision_current_negotiated_price"] = 27000
updated_snapshot = build_snapshot(updated_state)
assert "decision_current_negotiated_price" in changed_fields(snapshot, updated_snapshot)

first_id, first_key = deal_identity(address=STATE["address"])
second_id, second_key = deal_identity(address="1115 Matson Drive, Marion VA 24354")
assert first_id == second_id
assert first_key == second_key

print("Deal Vault snapshot, identity, compression, and restore smoke test passed.")
