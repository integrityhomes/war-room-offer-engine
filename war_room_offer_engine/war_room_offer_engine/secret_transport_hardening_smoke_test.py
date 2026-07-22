from __future__ import annotations

import importlib
import sys
from pathlib import Path

import requests


APP_DIR = Path(__file__).resolve().parent
REPO_ROOT = APP_DIR.parent.parent
for path in [str(APP_DIR), str(APP_DIR.parent), str(REPO_ROOT)]:
    if path not in sys.path:
        sys.path.insert(0, path)


security = importlib.import_module("secret_transport_hardening")
apify = importlib.import_module("apify_connector")
zillow = importlib.import_module("zillow_url_import")
library = importlib.import_module("deal_library")
data_sources = importlib.import_module("data_sources")

assert security.install() is True
assert apify.fetch_dataset_items is security.secure_fetch_dataset_items
assert apify.run_actor_for_items is security.secure_run_actor_for_items
assert zillow.fetch_task_input is security.secure_fetch_task_input
assert zillow.run_task_for_items is security.secure_run_task_for_items
assert library._request is security.secure_deal_library_request
assert data_sources.fetch_dataset_items is security.secure_fetch_dataset_items
assert data_sources.run_actor_for_items is security.secure_run_actor_for_items


SECRET = "apify_test_token_ABC123456789"
raw = (
    f"https://api.example.test/path?token={SECRET}&limit=10 "
    f"Authorization: Bearer {SECRET} "
    f'{{"api_key":"{SECRET}","password":"{SECRET}"}}'
)
redacted = security.redact_sensitive_text(raw, [SECRET])
assert SECRET not in redacted
assert "[REDACTED]" in redacted


class FakeResponse:
    def __init__(self, status_code=200, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload
        self.text = text

    def json(self):
        if isinstance(self._payload, BaseException):
            raise self._payload
        return self._payload


original_get = security.requests.get
original_post = security.requests.post
original_connection_settings = library.connection_settings

try:
    calls: list[tuple[str, str, dict]] = []

    def dataset_get(url, **kwargs):
        calls.append(("GET", url, kwargs))
        return FakeResponse(
            200,
            [
                {
                    "address": "101 Test St",
                    "city": "Decatur",
                    "state": "IL",
                    "zipcode": "62521",
                    "price": 50000,
                    "beds": 3,
                }
            ],
        )

    security.requests.get = dataset_get
    dataset_result = apify.fetch_dataset_items("dataset-id", SECRET, limit=5)
    assert dataset_result.get("ok") is True
    method, url, kwargs = calls[-1]
    assert method == "GET"
    assert kwargs.get("headers", {}).get("Authorization") == f"Bearer {SECRET}"
    assert "token" not in kwargs.get("params", {})
    assert SECRET not in url

    def actor_post(url, **kwargs):
        calls.append(("POST", url, kwargs))
        return FakeResponse(
            200,
            [
                {
                    "address": "102 Test St",
                    "city": "Decatur",
                    "state": "IL",
                    "zipcode": "62521",
                    "price": 51000,
                }
            ],
        )

    security.requests.post = actor_post
    actor_result = apify.run_actor_for_items("actor-id", {"startUrls": []}, SECRET, limit=5)
    assert actor_result.get("ok") is True
    method, url, kwargs = calls[-1]
    assert method == "POST"
    assert kwargs.get("headers", {}).get("Authorization") == f"Bearer {SECRET}"
    assert "token" not in kwargs.get("params", {})
    assert SECRET not in url

    def task_get(url, **kwargs):
        calls.append(("GET", url, kwargs))
        return FakeResponse(200, {"data": {"input": {"zipCodes": ["62521"]}}})

    security.requests.get = task_get
    task_input = zillow.fetch_task_input("task-id", SECRET)
    assert task_input == {"zipCodes": ["62521"]}
    method, url, kwargs = calls[-1]
    assert kwargs.get("headers", {}).get("Authorization") == f"Bearer {SECRET}"
    assert "params" not in kwargs or "token" not in kwargs.get("params", {})
    assert SECRET not in url

    def task_post(url, **kwargs):
        calls.append(("POST", url, kwargs))
        return FakeResponse(
            200,
            [
                {
                    "address": "103 Test St",
                    "city": "Decatur",
                    "state": "IL",
                    "zipcode": "62521",
                    "price": 52000,
                }
            ],
        )

    security.requests.post = task_post
    task_result = zillow.run_task_for_items("task-id", {"zipCodes": ["62521"]}, SECRET, limit=5)
    assert task_result.get("ok") is True
    method, url, kwargs = calls[-1]
    assert kwargs.get("headers", {}).get("Authorization") == f"Bearer {SECRET}"
    assert "token" not in kwargs.get("params", {})
    assert SECRET not in url

    def leaking_get(url, **kwargs):
        raise requests.ConnectionError(f"connection failed for {url}?token={SECRET}")

    security.requests.get = leaking_get
    leaked_result = apify.fetch_dataset_items("dataset-id", SECRET, limit=1)
    leaked_error = str(leaked_result.get("error", ""))
    assert SECRET not in leaked_error
    assert "token=" not in leaked_error.lower()

    def leaking_http_get(url, **kwargs):
        return FakeResponse(500, {"ok": False}, f"upstream URL {url}?token={SECRET}&x=1")

    security.requests.get = leaking_http_get
    http_result = apify.fetch_dataset_items("dataset-id", SECRET, limit=1)
    http_error = str(http_result.get("error", ""))
    assert SECRET not in http_error
    assert "[REDACTED]" in http_error

    WEBHOOK = "https://script.google.com/macros/s/test-deployment/exec"
    library.connection_settings = lambda: (WEBHOOK, SECRET)
    deal_calls: list[tuple[str, str, dict]] = []

    def secure_library_post(url, **kwargs):
        deal_calls.append(("POST", url, kwargs))
        return FakeResponse(200, {"ok": True, "deals_count": 0, "history_count": 0})

    security.requests.post = secure_library_post
    secure_health = library.health()
    assert secure_health.get("ok") is True
    method, url, kwargs = deal_calls[-1]
    assert method == "POST"
    assert url == WEBHOOK
    assert kwargs.get("json", {}).get("token") == SECRET
    assert "?" not in url

    def old_library_post(url, **kwargs):
        deal_calls.append(("POST", url, kwargs))
        return FakeResponse(200, {"ok": False, "error": "Unknown Deal Library action: search"})

    def old_library_get(url, **kwargs):
        deal_calls.append(("GET", url, kwargs))
        return FakeResponse(200, {"ok": True, "deals": [], "count": 0})

    security.requests.post = old_library_post
    security.requests.get = old_library_get
    legacy_search = library.search_deals("Decatur", limit=10)
    assert legacy_search.get("ok") is True
    assert deal_calls[-2][0] == "POST"
    assert deal_calls[-1][0] == "GET"
    assert deal_calls[-1][2].get("params", {}).get("token") == SECRET

    def leaking_library_post(url, **kwargs):
        raise requests.ConnectionError(f"failed calling {url}?token={SECRET}")

    security.requests.post = leaking_library_post
    library_error = library.health()
    visible_error = str(library_error.get("error", ""))
    assert SECRET not in visible_error
    assert "token=" not in visible_error.lower()

    def token_echo_post(url, **kwargs):
        return FakeResponse(200, {"ok": False, "error": f"authorization token={SECRET}"})

    security.requests.post = token_echo_post
    sanitized_payload = library.health()
    assert SECRET not in str(sanitized_payload)
    assert "[REDACTED]" in str(sanitized_payload)
finally:
    security.requests.get = original_get
    security.requests.post = original_post
    library.connection_settings = original_connection_settings


patch_path = REPO_ROOT / "setup" / "google_apps_script" / "DealLibrarySecurePostPatch.gs"
patch_text = patch_path.read_text(encoding="utf-8")
for required_action in ["health", "search", "list", "get", "upsert"]:
    assert required_action in patch_text
assert "rotateDealLibraryToken" in patch_text

print("Secret transport and redaction hardening smoke test passed.")
