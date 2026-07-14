from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote

import requests

try:
    from google.auth.transport.requests import Request as GoogleAuthRequest
    from google.oauth2 import service_account
except Exception:  # pragma: no cover - configuration screen handles missing package
    GoogleAuthRequest = None
    service_account = None

try:
    from deal_vault_snapshot import changed_fields, decode_snapshot, encode_snapshot, snapshot_hash
except ImportError:
    try:
        from .deal_vault_snapshot import changed_fields, decode_snapshot, encode_snapshot, snapshot_hash
    except ImportError:
        from war_room_offer_engine.deal_vault_snapshot import changed_fields, decode_snapshot, encode_snapshot, snapshot_hash


SHEETS_SCOPE = "https://www.googleapis.com/auth/spreadsheets"
SHEETS_API = "https://sheets.googleapis.com/v4/spreadsheets"
VAULT_TAB = "Deal Vault"
HISTORY_TAB = "Deal History"

VAULT_HEADERS = [
    "deal_id", "address_key", "address", "city", "state", "zip", "listing_url",
    "lead_source", "assigned_to", "stage", "priority", "drive_folder_url",
    "decision", "deal_lane", "asking_price", "negotiated_price", "starting_offer",
    "absolute_max", "rent", "rent_comp_count", "arv", "arv_confidence",
    "sold_comp_count", "repairs", "last_saved_utc", "last_saved_by",
    "snapshot_version", "snapshot_hash", "snapshot_trimmed", "snapshot_payload",
]

HISTORY_HEADERS = [
    "event_utc", "deal_id", "address", "action", "saved_by", "stage",
    "assigned_to", "decision", "negotiated_price", "snapshot_hash",
    "changed_fields", "snapshot_payload",
]

_TOKEN_CACHE: dict[str, tuple[str, float]] = {}


def _secret_value(secrets: Any, key: str, default: Any = "") -> Any:
    try:
        value = secrets.get(key, default)
    except Exception:
        try:
            value = secrets[key]
        except Exception:
            value = default
    return value


def parse_sheet_id(value: Any) -> str:
    text = str(value or "").strip()
    match = re.search(r"/spreadsheets/d/([a-zA-Z0-9-_]+)", text)
    return match.group(1) if match else text


def service_account_info(secrets: Any) -> dict[str, Any]:
    nested = _secret_value(secrets, "gcp_service_account", {})
    if isinstance(nested, dict) and nested.get("client_email"):
        return dict(nested)
    raw = _secret_value(secrets, "GOOGLE_SERVICE_ACCOUNT_JSON", "")
    if isinstance(raw, dict):
        return dict(raw)
    if str(raw or "").strip():
        try:
            return json.loads(str(raw))
        except Exception:
            return {}
    return {}


def config_from_secrets(secrets: Any) -> dict[str, Any]:
    sheet_id = parse_sheet_id(
        _secret_value(secrets, "DEAL_VAULT_SHEET_ID", "")
        or _secret_value(secrets, "DEAL_VAULT_SHEET_URL", "")
    )
    info = service_account_info(secrets)
    return {
        "sheet_id": sheet_id,
        "service_account": info,
        "configured": bool(sheet_id and info.get("client_email") and info.get("private_key")),
        "client_email": info.get("client_email", ""),
    }


def _access_token(info: dict[str, Any]) -> str:
    if service_account is None or GoogleAuthRequest is None:
        raise RuntimeError("google-auth is not installed. Add it to requirements.txt and redeploy.")
    email = str(info.get("client_email", ""))
    now = datetime.now(timezone.utc).timestamp()
    cached = _TOKEN_CACHE.get(email)
    if cached and cached[1] > now + 120:
        return cached[0]
    credentials = service_account.Credentials.from_service_account_info(info, scopes=[SHEETS_SCOPE])
    credentials.refresh(GoogleAuthRequest())
    expiry = credentials.expiry.timestamp() if credentials.expiry else now + 3000
    _TOKEN_CACHE[email] = (str(credentials.token), expiry)
    return str(credentials.token)


def _column_letter(count: int) -> str:
    value = int(count)
    output = ""
    while value:
        value, remainder = divmod(value - 1, 26)
        output = chr(65 + remainder) + output
    return output or "A"


def _sheet_range(title: str, cell_range: str) -> str:
    escaped = title.replace("'", "''")
    return f"'{escaped}'!{cell_range}"


class DealVaultSheets:
    def __init__(self, sheet_id: str, service_account_data: dict[str, Any], session=requests):
        self.sheet_id = str(sheet_id or "").strip()
        self.service_account_data = dict(service_account_data or {})
        self.session = session

    @classmethod
    def from_secrets(cls, secrets: Any, session=requests) -> "DealVaultSheets":
        config = config_from_secrets(secrets)
        if not config["configured"]:
            raise RuntimeError("Deal Vault Google Sheet or service account is not configured.")
        return cls(config["sheet_id"], config["service_account"], session=session)

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {_access_token(self.service_account_data)}",
            "Content-Type": "application/json",
        }

    def _request(self, method: str, url: str, *, params: dict | None = None, payload: dict | None = None) -> dict[str, Any]:
        response = self.session.request(
            method,
            url,
            headers=self._headers(),
            params=params,
            json=payload,
            timeout=35,
        )
        if response.status_code < 200 or response.status_code >= 300:
            raise RuntimeError(f"Google Sheets HTTP {response.status_code}: {response.text[:500]}")
        if not response.text:
            return {}
        try:
            return response.json()
        except Exception:
            return {}

    def _metadata(self) -> dict[str, Any]:
        return self._request(
            "GET",
            f"{SHEETS_API}/{self.sheet_id}",
            params={"fields": "properties.title,sheets.properties(sheetId,title)"},
        )

    def ensure_ready(self) -> None:
        metadata = self._metadata()
        titles = {
            str(item.get("properties", {}).get("title", ""))
            for item in metadata.get("sheets", [])
            if isinstance(item, dict)
        }
        requests_to_add = []
        for title in [VAULT_TAB, HISTORY_TAB]:
            if title not in titles:
                requests_to_add.append({"addSheet": {"properties": {"title": title}}})
        if requests_to_add:
            self._request(
                "POST",
                f"{SHEETS_API}/{self.sheet_id}:batchUpdate",
                payload={"requests": requests_to_add},
            )
        self._ensure_headers(VAULT_TAB, VAULT_HEADERS)
        self._ensure_headers(HISTORY_TAB, HISTORY_HEADERS)

    def _values_url(self, range_name: str, append: bool = False) -> str:
        encoded = quote(range_name, safe="")
        suffix = ":append" if append else ""
        return f"{SHEETS_API}/{self.sheet_id}/values/{encoded}{suffix}"

    def _get_values(self, range_name: str) -> list[list[Any]]:
        result = self._request("GET", self._values_url(range_name))
        return result.get("values", []) or []

    def _update_values(self, range_name: str, rows: list[list[Any]]) -> None:
        self._request(
            "PUT",
            self._values_url(range_name),
            params={"valueInputOption": "RAW"},
            payload={"range": range_name, "majorDimension": "ROWS", "values": rows},
        )

    def _append_values(self, range_name: str, rows: list[list[Any]]) -> None:
        self._request(
            "POST",
            self._values_url(range_name, append=True),
            params={"valueInputOption": "RAW", "insertDataOption": "INSERT_ROWS"},
            payload={"range": range_name, "majorDimension": "ROWS", "values": rows},
        )

    def _ensure_headers(self, title: str, headers: list[str]) -> None:
        end = _column_letter(len(headers))
        range_name = _sheet_range(title, f"A1:{end}2")
        values = self._get_values(range_name)
        current = values[0] if values else []
        if current != headers:
            self._update_values(_sheet_range(title, f"A1:{end}1"), [headers])

    def list_deals(self) -> list[dict[str, Any]]:
        self.ensure_ready()
        end = _column_letter(len(VAULT_HEADERS))
        values = self._get_values(_sheet_range(VAULT_TAB, f"A1:{end}"))
        if not values:
            return []
        headers = [str(value) for value in values[0]]
        records = []
        for row_index, row in enumerate(values[1:], start=2):
            padded = list(row) + [""] * max(0, len(headers) - len(row))
            record = {headers[index]: padded[index] for index in range(len(headers))}
            record["_row_number"] = row_index
            if record.get("deal_id"):
                records.append(record)
        records.sort(key=lambda item: str(item.get("last_saved_utc", "")), reverse=True)
        return records

    def find(self, query: str, records: list[dict[str, Any]] | None = None) -> dict[str, Any] | None:
        normalized = re.sub(r"[^a-z0-9]+", " ", str(query or "").lower()).strip()
        if not normalized:
            return None
        rows = records if records is not None else self.list_deals()
        for record in rows:
            candidates = [
                record.get("deal_id", ""), record.get("address_key", ""),
                record.get("address", ""), record.get("listing_url", ""),
            ]
            for candidate in candidates:
                candidate_normalized = re.sub(r"[^a-z0-9]+", " ", str(candidate or "").lower()).strip()
                if candidate_normalized and (
                    normalized == candidate_normalized
                    or normalized in candidate_normalized
                    or candidate_normalized in normalized
                ):
                    return record
        return None

    def load_snapshot(self, record: dict[str, Any]) -> dict[str, Any]:
        return decode_snapshot(str(record.get("snapshot_payload", "")))

    def save_deal(
        self,
        summary: dict[str, Any],
        snapshot: dict[str, Any],
        *,
        assigned_to: str = "",
        stage: str = "New",
        priority: str = "Normal",
        drive_folder_url: str = "",
        saved_by: str = "",
    ) -> dict[str, Any]:
        self.ensure_ready()
        deal_id = str(summary.get("deal_id", ""))
        if not deal_id:
            raise ValueError("A property address or listing URL is required before saving the deal.")

        records = self.list_deals()
        existing = next((record for record in records if str(record.get("deal_id")) == deal_id), None)
        previous_snapshot = self.load_snapshot(existing) if existing and existing.get("snapshot_payload") else {}
        changed = changed_fields(previous_snapshot, snapshot)
        payload, trimmed = encode_snapshot(snapshot)
        digest = snapshot_hash(snapshot)
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        action = "Updated" if existing else "Created"

        row_data = {
            **{key: summary.get(key, "") for key in VAULT_HEADERS},
            "assigned_to": assigned_to,
            "stage": stage,
            "priority": priority,
            "drive_folder_url": drive_folder_url,
            "last_saved_utc": now,
            "last_saved_by": saved_by,
            "snapshot_version": snapshot.get("snapshot_version", 1),
            "snapshot_hash": digest,
            "snapshot_trimmed": "Yes" if trimmed else "No",
            "snapshot_payload": payload,
        }
        row = [row_data.get(header, "") for header in VAULT_HEADERS]
        end = _column_letter(len(VAULT_HEADERS))
        if existing:
            row_number = int(existing["_row_number"])
            self._update_values(_sheet_range(VAULT_TAB, f"A{row_number}:{end}{row_number}"), [row])
        else:
            self._append_values(_sheet_range(VAULT_TAB, f"A:{end}"), [row])

        history = {
            "event_utc": now,
            "deal_id": deal_id,
            "address": summary.get("address", ""),
            "action": action,
            "saved_by": saved_by,
            "stage": stage,
            "assigned_to": assigned_to,
            "decision": summary.get("decision", ""),
            "negotiated_price": summary.get("negotiated_price", 0),
            "snapshot_hash": digest,
            "changed_fields": ", ".join(changed[:100]),
            "snapshot_payload": payload,
        }
        history_end = _column_letter(len(HISTORY_HEADERS))
        self._append_values(
            _sheet_range(HISTORY_TAB, f"A:{history_end}"),
            [[history.get(header, "") for header in HISTORY_HEADERS]],
        )
        return {
            "ok": True,
            "action": action,
            "deal_id": deal_id,
            "saved_at": now,
            "changed_fields": changed,
            "snapshot_trimmed": trimmed,
        }
