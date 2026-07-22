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

## 3A. Upgrade an existing Deal Library to secure POST

The hardened Streamlit client sends the token inside an encrypted HTTPS POST body instead of putting it in the request URL. It automatically falls back to the old GET route only while an older Apps Script deployment is still active, so this upgrade does not interrupt the team.

For an existing Deal Library:

1. Open the connected Google Sheet.
2. Open **Extensions → Apps Script**.
3. Find and delete the existing `doPost(e)` function only.
4. Copy all code from:
   `setup/google_apps_script/DealLibrarySecurePostPatch.gs`
5. Paste it below the existing Deal Library code and save.
6. Open **Deploy → Manage deployments**.
7. Click the pencil/edit icon for the current web app.
8. Choose **New version**, then click **Deploy**.
9. Return to Streamlit, reboot the app, and click **Test Sheet Connection**.

After the secure deployment tests successfully, run `rotateDealLibraryToken` once in Apps Script as a precaution. Immediately copy the returned token into the `DEAL_LIBRARY_TOKEN` Streamlit secret, save, reboot, and test the Sheet connection again. Do not rotate the token until you are ready to update the Streamlit secret in the same session.

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
- When the main analysis button is pressed, the app checks the Deal Library before paid APIs. An existing saved property opens automatically without new Zillow, RentCast or Apify charges.
- Leave **Refresh live paid data even if this property is already saved** turned off during normal use.
- Turn that refresh checkbox on only when the team intentionally needs new live data and accepts the additional API usage.
- When multiple saved properties match, the app stops and asks the user to choose instead of spending credits on a new pull.

## Team protection

Every save creates a version-history row. If two team members open the same version and one saves first, the second person receives a warning instead of silently overwriting the newer work.

## Media note

Google Sheets stores the generated repair notes, repair estimate and all analysis results. Large raw video files are not embedded in spreadsheet cells. Keep original walkthrough media in the team’s Google Drive property folder and place the Drive folder link in Team Notes. A direct Google Drive media-upload module can be added separately without changing the Deal Library design.
