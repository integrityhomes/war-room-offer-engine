// Existing Deal Library upgrade patch.
//
// In the bound Google Apps Script project, delete the old doPost(e) function,
// paste this file below the existing DealLibrary.gs code, save, and deploy a new
// web-app version. Keep doGet(e) temporarily for older clients; the current War
// Room client uses this secure JSON POST route first and falls back only while an
// older deployment is still active.

function doPost(e) {
  try {
    const body = JSON.parse((e && e.postData && e.postData.contents) || '{}');
    authorize_(body.token || '');
    const action = String(body.action || 'health').toLowerCase();
    if (action === 'health') return json_(health_());
    if (action === 'search' || action === 'list') {
      return json_(searchDeals_(body.q || '', Number(body.limit || 25)));
    }
    if (action === 'get') return json_(getDeal_(body.deal_id || ''));
    if (action === 'upsert') return json_(upsertDeal_(body.snapshot || {}));
    return json_({ok: false, error: 'Unknown Deal Library action: ' + action});
  } catch (error) {
    return json_({ok: false, error: String(error && error.message ? error.message : error)});
  }
}

// Optional precaution after the secure POST deployment is live.
// Run this once, copy the returned token into the DEAL_LIBRARY_TOKEN Streamlit
// secret immediately, then reboot the app and test the Sheet connection.
function rotateDealLibraryToken() {
  const token = Utilities.getUuid().replace(/-/g, '') + Utilities.getUuid().replace(/-/g, '');
  PropertiesService.getScriptProperties().setProperty('DEAL_LIBRARY_TOKEN', token);

  const spreadsheet = spreadsheet_();
  const setup = spreadsheet.getSheetByName(SETUP_SHEET);
  if (setup && setup.getLastRow() >= 2) {
    const settings = setup.getRange(2, 1, setup.getLastRow() - 1, 1).getValues();
    for (let index = 0; index < settings.length; index++) {
      if (String(settings[index][0] || '').trim() === 'DEAL_LIBRARY_TOKEN') {
        setup.getRange(index + 2, 2).setValue(token);
        break;
      }
    }
  }
  return token;
}
