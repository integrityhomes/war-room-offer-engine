# War Room Team Deal Library Setup

The app code is complete once this branch is merged, but the shared Google Sheet must be connected once.

## What the connection creates

The Apps Script automatically creates and maintains:

- **Deal Library** — one current, readable row per property.
- **Deal History** — one row for every save/update version.
- **Deal Snapshots** — the full app state split into safe chunks so large comp sets do not exceed Google Sheets cell limits.

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
   `google_apps_script/deal_library_web_app.js`
4. Paste it into `Code.gs` and save.

## 3. Add a private access token

In Apps Script:

1. Open **Project Settings**.
2. Under **Script Properties**, add:
   - Property: `DEAL_LIBRARY_TOKEN`
   - Value: a long private random value.
3. Optional: add `DEAL_LIBRARY_SPREADSHEET_ID` using the ID from the Google Sheet URL. A bound script normally does not require this, but adding it removes ambiguity.

## 4. Deploy as a web app

1. Click **Deploy → New deployment**.
2. Choose **Web app**.
3. Execute as: **Me**.
4. Who has access: choose the option that allows the Streamlit server to call the app. The private token still protects requests.
5. Deploy and copy the `/exec` web-app URL.

## 5. Add Streamlit secrets

In the Streamlit app settings, add:

```toml
DEAL_LIBRARY_WEBHOOK_URL = "PASTE_THE_APPS_SCRIPT_EXEC_URL_HERE"
DEAL_LIBRARY_TOKEN = "THE_SAME_PRIVATE_TOKEN"
DEAL_LIBRARY_APP_URL = "https://war-room-offer-engine.streamlit.app"
```

Use the live app URL for `DEAL_LIBRARY_APP_URL`. It is used to create team deep links such as:

`https://war-room-offer-engine.streamlit.app/?deal_id=abc123...`

## 6. Test

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

## Media note

Google Sheets stores the generated repair notes, repair estimate, filenames represented in saved notes, and all analysis results. Large raw video files are not embedded in spreadsheet cells. Keep original walkthrough media in the team's Google Drive property folder and place the Drive folder link in Team Notes. A direct Google Drive media-upload module can be added separately without changing the Deal Library design.
