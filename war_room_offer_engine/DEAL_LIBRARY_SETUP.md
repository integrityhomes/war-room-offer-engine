# War Room Team Deal Library Setup

The app code is complete once this branch is merged, but the shared Google Sheet must be connected once.

## What the connection creates

The Apps Script automatically creates and maintains:

- **Deal Library** — one current, readable row per property.
- **Deal History** — one row for every save/update version.
- **Deal Snapshots** — the full app state split into safe chunks so large comp sets do not exceed Google Sheets cell limits.
- **Deal Library Setup** — the connection values and deployment instructions.

Opening a saved deal restores the prior property facts, rents, rental comps, sold comps, ARV work, repair analysis, negotiation, decision and team notes without calling paid data sources again.

## 1. Create the Google Sheet

Create a blank Google Sheet named something like:

`War Room Team Deal Library`

No tabs or headers have to be created manually.

## 2. Add the Apps Script

In the Google Sheet:

1. Open **Extensions → Apps Script**.
2. Delete the starter code.
3. Copy all code from:
   `setup/google_apps_script/DealLibrary.gs`
4. Paste it into `Code.gs` and save.
5. At the top of Apps Script, select the function **setupDealLibrary**.
6. Click **Run** and approve Google’s permission prompts.

The script creates all four tabs and generates a private token automatically. Open the new **Deal Library Setup** tab to copy the token.

## 3. Deploy as a web app

1. Click **Deploy → New deployment**.
2. Choose **Web app**.
3. Execute as: **Me**.
4. Who has access: choose **Anyone with the link** so the Streamlit server can call it. Requests are still protected by the private token.
5. Deploy and copy the `/exec` web-app URL.
6. Paste that URL into the **Deal Library Setup** tab for your records.

## 4. Add Streamlit secrets

In the Streamlit app settings, add:

```toml
DEAL_LIBRARY_WEBHOOK_URL = "PASTE_THE_APPS_SCRIPT_EXEC_URL_HERE"
DEAL_LIBRARY_TOKEN = "PASTE_TOKEN_FROM_DEAL_LIBRARY_SETUP_TAB"
DEAL_LIBRARY_APP_URL = "https://war-room-offer-engine.streamlit.app"
```

Use the live app URL for `DEAL_LIBRARY_APP_URL`. It creates one-click team links such as:

`https://war-room-offer-engine.streamlit.app/?deal_id=abc123...`

## 5. Test

1. Refresh the Streamlit app.
2. Open **One-Load**.
3. In **Team Deal Library**, click **Test Sheet Connection**.
4. Analyze one property.
5. Confirm the result auto-saves.
6. Click **Find Saved Deals**, open the property, and verify the app says no paid property-data credits were used.

## Normal team workflow

- Analyze a new property once with **Pull Everything & Tell Me**.
- The completed analysis auto-saves when the checkbox is enabled.
- Update assignment, status and team notes as negotiations move forward.
- Use **Save / Update Deal for Team** after manual changes.
- Reopen from **Find Saved Deals** or send the generated deal link.
- Press **Pull Everything & Tell Me** again only when fresh Zillow, RentCast or Apify data is intentionally needed.

## Team protection

Every save creates a version-history row. If two team members open the same version and one saves first, the second person receives a warning instead of silently overwriting the newer work.

## Media note

Google Sheets stores the generated repair notes, repair estimate and all analysis results. Large raw video files are not embedded in spreadsheet cells. Keep original walkthrough media in the team’s Google Drive property folder and place the Drive folder link in Team Notes. A direct Google Drive media-upload module can be added separately without changing the Deal Library design.
