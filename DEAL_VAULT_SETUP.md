# Team Deal Vault Setup

The Team Deal Vault stores one current record per property in Google Sheets and writes every save/update into a separate history tab.

## What it creates

After the first successful connection, the app automatically creates or initializes:

- `Deal Vault` — one current row per property
- `Deal History` — append-only save/update history

The saved snapshot includes the decision, deal lane, negotiation, property facts, RentCast rent and rental comps, sold comps, ARV, repairs, notes, source data, and audit fields. Uploaded media files are represented by filename, size, and type; the actual video/photo files should be placed in Google Drive and linked in the Deal Vault box.

## One-time Google setup

1. Create a new Google Sheet named `War Room Team Deal Vault`.
2. Copy the Sheet ID from the URL between `/d/` and `/edit`.
3. In Google Cloud, enable the **Google Sheets API**.
4. Create a service account and download its JSON key.
5. Share the Google Sheet with the service account's `client_email` as **Editor**.
6. Open the Streamlit app settings and add these secrets.

```toml
DEAL_VAULT_SHEET_ID = "PASTE_GOOGLE_SHEET_ID_HERE"
DEAL_VAULT_DEFAULT_USER = "Shawn"
DEAL_VAULT_TEAM_MEMBERS = ["Shawn", "Sabrina", "Carlos"]

[gcp_service_account]
type = "service_account"
project_id = "your-project-id"
private_key_id = "your-private-key-id"
private_key = """-----BEGIN PRIVATE KEY-----
PASTE_PRIVATE_KEY_HERE
-----END PRIVATE KEY-----
"""
client_email = "service-account-name@your-project-id.iam.gserviceaccount.com"
client_id = "your-client-id"
auth_uri = "https://accounts.google.com/o/oauth2/auth"
token_uri = "https://oauth2.googleapis.com/token"
auth_provider_x509_cert_url = "https://www.googleapis.com/oauth2/v1/certs"
client_x509_cert_url = "your-client-cert-url-from-the-json-file"
universe_domain = "googleapis.com"
```

7. Save the Streamlit secrets and reboot/redeploy the app.
8. Open **Team Deal Vault** and click **Refresh Deal List**. The two tabs will be created automatically.

## Daily workflow

1. Enter an address or listing link.
2. Leave **Use saved deal first** checked.
3. Click **Pull Everything & Tell Me**.
4. When the property already exists in the Deal Vault, the saved snapshot loads without calling paid property-data or AI sources.
5. Check **Refresh live data** only when a fresh RentCast, listing, comp, or condition pull is needed.
6. Completed analyses auto-save when **Auto-save completed analysis** is checked.
7. Use **Save / Update Current Deal** after changing negotiation, assignment, stage, priority, notes, or team ownership.

## Data safety

- The app upserts the current property row instead of creating duplicate property records.
- Every save or update is also appended to `Deal History`.
- Snapshot payloads are compressed to stay within Google Sheets cell limits.
- A snapshot hash and changed-field list are recorded for auditability.
- Google Sheets access is limited to the permissions granted to the service account.
- Never commit the service-account key to GitHub.
