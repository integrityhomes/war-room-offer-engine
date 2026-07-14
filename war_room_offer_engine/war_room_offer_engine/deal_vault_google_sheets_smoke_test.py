from __future__ import annotations

import re
from collections.abc import Mapping

from deal_vault_google_sheets import (
    HISTORY_HEADERS,
    HISTORY_TAB,
    VAULT_HEADERS,
    VAULT_TAB,
    DealVaultSheets,
    config_from_secrets,
    parse_sheet_id,
)
from deal_vault_snapshot import build_snapshot, summary_from_state


class AttrMapping(Mapping):
    def __init__(self, values):
        self.values = values

    def __getitem__(self, key):
        return self.values[key]

    def __iter__(self):
        return iter(self.values)

    def __len__(self):
        return len(self.values)


class MemoryVault(DealVaultSheets):
    def __init__(self):
        super().__init__("test-sheet", {"client_email": "test@example.com", "private_key": "test"})
        self.records = []
        self.history = []

    def ensure_ready(self):
        return None

    def list_deals(self):
        output = []
        for index, record in enumerate(self.records, start=2):
            output.append({**record, "_row_number": index})
        return output

    def _update_values(self, range_name, rows):
        assert VAULT_TAB in range_name
        match = re.search(r"!A(\d+):", range_name)
        assert match, range_name
        row_number = int(match.group(1))
        self.records[row_number - 2] = dict(zip(VAULT_HEADERS, rows[0]))

    def _append_values(self, range_name, rows):
        if VAULT_TAB in range_name:
            self.records.append(dict(zip(VAULT_HEADERS, rows[0])))
        elif HISTORY_TAB in range_name:
            self.history.append(dict(zip(HISTORY_HEADERS, rows[0])))
        else:
            raise AssertionError(range_name)


assert parse_sheet_id("https://docs.google.com/spreadsheets/d/abc-123_XYZ/edit") == "abc-123_XYZ"
config = config_from_secrets(
    {
        "DEAL_VAULT_SHEET_URL": "https://docs.google.com/spreadsheets/d/abc-123_XYZ/edit",
        "gcp_service_account": AttrMapping(
            {
                "client_email": "vault@example.iam.gserviceaccount.com",
                "private_key": "line-one\\nline-two",
                "token_uri": "https://oauth2.googleapis.com/token",
            }
        ),
    }
)
assert config["configured"]
assert config["sheet_id"] == "abc-123_XYZ"
assert "\\n" not in config["service_account"]["private_key"]
assert "\n" in config["service_account"]["private_key"]

BASE_STATE = {
    "address": "1115 Matson Dr, Marion, VA 24354",
    "city": "Marion",
    "state": "VA",
    "zip": "24354",
    "decision_property_input": "1115 Matson Dr, Marion, VA 24354",
    "decision_current_negotiated_price": 25000,
    "decision_result": {
        "decision": "BUY",
        "strategy": "Slow Flip — Keep",
        "first_offer": 28000,
        "hard_max": 32000,
    },
    "rent": 1040,
    "rentcast_rent_comp_count": 4,
    "arv": 35667,
    "arv_confidence": "Strong",
    "rentcast_value_comp_count": 10,
    "repairs": 63476,
}

vault = MemoryVault()
summary = summary_from_state(BASE_STATE)
snapshot = build_snapshot(BASE_STATE)
created = vault.save_deal(
    summary,
    snapshot,
    assigned_to="Carlos",
    stage="Offer Ready",
    priority="High",
    saved_by="Shawn",
)
assert created["action"] == "Created"
assert len(vault.records) == 1
assert len(vault.history) == 1
assert vault.records[0]["assigned_to"] == "Carlos"
assert vault.records[0]["stage"] == "Offer Ready"
assert vault.records[0]["snapshot_payload"].startswith("z1:")
assert vault.history[0]["action"] == "Created"

loaded = vault.load_snapshot(vault.records[0])
assert loaded["saved_state"]["rent"] == 1040
assert loaded["saved_state"]["decision_result"]["decision"] == "BUY"

UPDATED_STATE = dict(BASE_STATE)
UPDATED_STATE["decision_current_negotiated_price"] = 27000
UPDATED_STATE["decision_negotiation_status"] = "Negotiating"
updated = vault.save_deal(
    summary_from_state(UPDATED_STATE),
    build_snapshot(UPDATED_STATE),
    assigned_to="Carlos",
    stage="Negotiating",
    priority="Urgent",
    saved_by="Sabrina",
)
assert updated["action"] == "Updated"
assert len(vault.records) == 1
assert len(vault.history) == 2
assert vault.records[0]["negotiated_price"] == 27000
assert vault.records[0]["stage"] == "Negotiating"
assert vault.records[0]["last_saved_by"] == "Sabrina"
assert "decision_current_negotiated_price" in updated["changed_fields"]
assert vault.history[-1]["action"] == "Updated"

found = vault.find("1115 Matson Drive, Marion VA 24354", records=vault.list_deals())
assert found is not None
assert found["deal_id"] == summary["deal_id"]

print("Deal Vault secrets, create, upsert, load, normalized lookup, and history smoke test passed.")
