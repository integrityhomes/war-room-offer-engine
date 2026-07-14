const DEALS_SHEET_NAME = 'Deals';
const HISTORY_SHEET_NAME = 'Deal History';
const SETUP_SHEET_NAME = 'Deal Library Setup';

const DEAL_HEADERS = [
  'deal_id',
  'address',
  'city',
  'property_state',
  'zip',
  'listing_url',
  'lead_source',
  'deal_lane',
  'decision',
  'confidence',
  'deal_status',
  'assigned_to',
  'team_notes',
  'updated_by',
  'asking_price',
  'current_negotiated_price',
  'starting_offer',
  'absolute_maximum',
  'rent',
  'rent_comp_count',
  'arv',
  'sold_comp_count',
  'repairs',
  'created_at',
  'updated_at',
  'version',
  'snapshot_json',
  'search_text'
];

const HISTORY_HEADERS = [
  'history_id',
  'deal_id',
  'version',
  'saved_at',
  'updated_by',
  'deal_status',
  'address',
  'decision',
  'current_negotiated_price',
  'absolute_maximum',
  'snapshot_json'
];

function setupDealLibrary() {
  const spreadsheet = SpreadsheetApp.getActiveSpreadsheet();
  if (!spreadsheet) {
    throw new Error('Open the Google Sheet first, then run setupDealLibrary from its bound Apps Script project.');
  }

  const properties = PropertiesService.getScriptProperties();
  properties.setProperty('DEAL_LIBRARY_SPREADSHEET_ID', spreadsheet.getId());

  let token = properties.getProperty('DEAL_LIBRARY_TOKEN');
  if (!token) {
    token = Utilities.getUuid().replace(/-/g, '') + Utilities.getUuid().replace(/-/g, '');
    properties.setProperty('DEAL_LIBRARY_TOKEN', token);
  }

  const deals = getOrCreateSheet_(spreadsheet, DEALS_SHEET_NAME, DEAL_HEADERS);
  const history = getOrCreateSheet_(spreadsheet, HISTORY_SHEET_NAME, HISTORY_HEADERS);
  formatSheet_(deals, DEAL_HEADERS.length);
  formatSheet_(history, HISTORY_HEADERS.length);

  const setup = getOrCreateSheet_(spreadsheet, SETUP_SHEET_NAME, ['Setting', 'Value', 'Instructions']);
  setup.clearContents();
  setup.getRange(1, 1, 1, 3).setValues([['Setting', 'Value', 'Instructions']]);
  setup.getRange(2, 1, 5, 3).setValues([
    ['Spreadsheet ID', spreadsheet.getId(), 'Created automatically.'],
    ['DEAL_LIBRARY_TOKEN', token, 'Copy this exact token into Streamlit secrets.'],
    ['DEAL_LIBRARY_WEBHOOK_URL', 'Add after deployment', 'Deploy this script as a web app, then paste the /exec URL here and into Streamlit secrets.'],
    ['DEAL_LIBRARY_APP_URL', 'Your Streamlit app URL', 'Used to create one-click links for team members.'],
    ['Status', 'Ready to deploy', 'Deploy > New deployment > Web app > Execute as Me > Anyone with the link.']
  ]);
  setup.setFrozenRows(1);
  setup.autoResizeColumns(1, 3);
  setup.getRange(1, 1, 1, 3).setFontWeight('bold');

  return {
    ok: true,
    spreadsheet_id: spreadsheet.getId(),
    token: token,
    deals_sheet: DEALS_SHEET_NAME,
    history_sheet: HISTORY_SHEET_NAME
  };
}

function doGet(e) {
  try {
    const params = (e && e.parameter) || {};
    authorize_(params.token || '');
    const action = String(params.action || 'health').toLowerCase();

    if (action === 'health') {
      return jsonResponse_(health_());
    }
    if (action === 'search') {
      return jsonResponse_(searchDeals_(params.q || '', params.limit || 25));
    }
    if (action === 'get') {
      return jsonResponse_(getDeal_(params.deal_id || ''));
    }
    return jsonResponse_({ok: false, error: 'Unknown Deal Library action: ' + action});
  } catch (error) {
    return jsonResponse_({ok: false, error: String(error && error.message ? error.message : error)});
  }
}

function doPost(e) {
  try {
    const body = parseJsonBody_(e);
    authorize_(body.token || '');
    const action = String(body.action || '').toLowerCase();

    if (action === 'upsert') {
      return jsonResponse_(upsertDeal_(body.snapshot || {}));
    }
    return jsonResponse_({ok: false, error: 'Unknown Deal Library action: ' + action});
  } catch (error) {
    return jsonResponse_({ok: false, error: String(error && error.message ? error.message : error)});
  }
}

function upsertDeal_(incomingSnapshot) {
  if (!incomingSnapshot || typeof incomingSnapshot !== 'object') {
    return {ok: false, error: 'Missing deal snapshot.'};
  }

  const dealId = cleanString_(incomingSnapshot.deal_id);
  const address = cleanString_(incomingSnapshot.address);
  if (!dealId || !address) {
    return {ok: false, error: 'A deal ID and property address are required.'};
  }

  const lock = LockService.getScriptLock();
  lock.waitLock(30000);
  try {
    const spreadsheet = openLibrarySpreadsheet_();
    const dealsSheet = getOrCreateSheet_(spreadsheet, DEALS_SHEET_NAME, DEAL_HEADERS);
    const historySheet = getOrCreateSheet_(spreadsheet, HISTORY_SHEET_NAME, HISTORY_HEADERS);
    const rows = sheetRowsAsObjects_(dealsSheet, DEAL_HEADERS);
    const existingIndex = rows.findIndex(row => cleanString_(row.deal_id) === dealId);
    const existing = existingIndex >= 0 ? rows[existingIndex] : null;
    const currentVersion = existing ? number_(existing.version) : 0;
    const baseVersion = number_(incomingSnapshot.base_version);

    if (existing && baseVersion > 0 && currentVersion > baseVersion) {
      return {
        ok: false,
        conflict: true,
        error: 'A teammate saved a newer version of this deal. Reopen the latest saved deal before updating it.',
        current_version: currentVersion,
        current_updated_at: existing.updated_at,
        current_updated_by: existing.updated_by
      };
    }

    const now = new Date().toISOString();
    const version = currentVersion + 1;
    const createdAt = existing && existing.created_at ? String(existing.created_at) : now;
    const snapshot = JSON.parse(JSON.stringify(incomingSnapshot));
    snapshot.version = version;
    snapshot.base_version = version;
    snapshot.created_at = createdAt;
    snapshot.updated_at = now;
    snapshot.saved_at = now;

    const rowObject = buildDealRow_(snapshot, createdAt, now, version);
    const rowValues = DEAL_HEADERS.map(header => rowObject[header] === undefined ? '' : rowObject[header]);

    if (existingIndex >= 0) {
      dealsSheet.getRange(existingIndex + 2, 1, 1, DEAL_HEADERS.length).setValues([rowValues]);
    } else {
      dealsSheet.appendRow(rowValues);
    }

    const historyId = dealId + '-v' + version + '-' + Utilities.getUuid().slice(0, 8);
    const historyObject = {
      history_id: historyId,
      deal_id: dealId,
      version: version,
      saved_at: now,
      updated_by: cleanString_(snapshot.updated_by),
      deal_status: cleanString_(snapshot.deal_status),
      address: address,
      decision: cleanString_(snapshot.decision),
      current_negotiated_price: number_(snapshot.current_negotiated_price),
      absolute_maximum: number_(snapshot.absolute_maximum),
      snapshot_json: JSON.stringify(snapshot)
    };
    historySheet.appendRow(HISTORY_HEADERS.map(header => historyObject[header] === undefined ? '' : historyObject[header]));

    return {
      ok: true,
      deal_id: dealId,
      version: version,
      saved_at: now,
      created: existingIndex < 0,
      history_id: historyId
    };
  } finally {
    lock.releaseLock();
  }
}

function getDeal_(dealId) {
  const id = cleanString_(dealId);
  if (!id) {
    return {ok: false, error: 'Missing deal ID.'};
  }
  const spreadsheet = openLibrarySpreadsheet_();
  const sheet = getOrCreateSheet_(spreadsheet, DEALS_SHEET_NAME, DEAL_HEADERS);
  const rows = sheetRowsAsObjects_(sheet, DEAL_HEADERS);
  const row = rows.find(item => cleanString_(item.deal_id) === id);
  if (!row) {
    return {ok: false, error: 'Saved deal was not found.'};
  }
  const snapshot = safeParseJson_(row.snapshot_json, null);
  if (!snapshot) {
    return {ok: false, error: 'Saved deal snapshot is invalid.'};
  }
  snapshot.version = number_(row.version);
  snapshot.base_version = number_(row.version);
  snapshot.created_at = row.created_at || snapshot.created_at || '';
  snapshot.updated_at = row.updated_at || snapshot.updated_at || '';
  return {ok: true, snapshot: snapshot};
}

function searchDeals_(query, requestedLimit) {
  const q = cleanString_(query).toLowerCase();
  const limit = Math.max(1, Math.min(number_(requestedLimit) || 25, 100));
  const spreadsheet = openLibrarySpreadsheet_();
  const sheet = getOrCreateSheet_(spreadsheet, DEALS_SHEET_NAME, DEAL_HEADERS);
  const rows = sheetRowsAsObjects_(sheet, DEAL_HEADERS);

  const matched = rows.filter(row => {
    if (!q) return true;
    return cleanString_(row.search_text).toLowerCase().indexOf(q) >= 0;
  });

  matched.sort((a, b) => String(b.updated_at || '').localeCompare(String(a.updated_at || '')));
  const deals = matched.slice(0, limit).map(row => ({
    deal_id: cleanString_(row.deal_id),
    address: cleanString_(row.address),
    city: cleanString_(row.city),
    property_state: cleanString_(row.property_state),
    zip: cleanString_(row.zip),
    deal_lane: cleanString_(row.deal_lane),
    decision: cleanString_(row.decision),
    confidence: cleanString_(row.confidence),
    deal_status: cleanString_(row.deal_status),
    assigned_to: cleanString_(row.assigned_to),
    updated_by: cleanString_(row.updated_by),
    asking_price: number_(row.asking_price),
    current_negotiated_price: number_(row.current_negotiated_price),
    starting_offer: number_(row.starting_offer),
    absolute_maximum: number_(row.absolute_maximum),
    rent: number_(row.rent),
    arv: number_(row.arv),
    version: number_(row.version),
    updated_at: cleanString_(row.updated_at)
  }));

  return {ok: true, count: deals.length, deals: deals};
}

function health_() {
  const spreadsheet = openLibrarySpreadsheet_();
  const deals = getOrCreateSheet_(spreadsheet, DEALS_SHEET_NAME, DEAL_HEADERS);
  const history = getOrCreateSheet_(spreadsheet, HISTORY_SHEET_NAME, HISTORY_HEADERS);
  return {
    ok: true,
    spreadsheet_id: spreadsheet.getId(),
    spreadsheet_name: spreadsheet.getName(),
    deals_count: Math.max(deals.getLastRow() - 1, 0),
    history_count: Math.max(history.getLastRow() - 1, 0),
    checked_at: new Date().toISOString()
  };
}

function buildDealRow_(snapshot, createdAt, updatedAt, version) {
  const searchParts = [
    snapshot.address,
    snapshot.city,
    snapshot.property_state,
    snapshot.zip,
    snapshot.lead_source,
    snapshot.deal_lane,
    snapshot.decision,
    snapshot.deal_status,
    snapshot.assigned_to,
    snapshot.updated_by,
    snapshot.team_notes
  ];
  return {
    deal_id: cleanString_(snapshot.deal_id),
    address: cleanString_(snapshot.address),
    city: cleanString_(snapshot.city),
    property_state: cleanString_(snapshot.property_state),
    zip: cleanString_(snapshot.zip),
    listing_url: cleanString_(snapshot.listing_url),
    lead_source: cleanString_(snapshot.lead_source),
    deal_lane: cleanString_(snapshot.deal_lane),
    decision: cleanString_(snapshot.decision),
    confidence: cleanString_(snapshot.confidence),
    deal_status: cleanString_(snapshot.deal_status),
    assigned_to: cleanString_(snapshot.assigned_to),
    team_notes: cleanString_(snapshot.team_notes),
    updated_by: cleanString_(snapshot.updated_by),
    asking_price: number_(snapshot.asking_price),
    current_negotiated_price: number_(snapshot.current_negotiated_price),
    starting_offer: number_(snapshot.starting_offer),
    absolute_maximum: number_(snapshot.absolute_maximum),
    rent: number_(snapshot.rent),
    rent_comp_count: number_(snapshot.rent_comp_count),
    arv: number_(snapshot.arv),
    sold_comp_count: number_(snapshot.sold_comp_count),
    repairs: number_(snapshot.repairs),
    created_at: createdAt,
    updated_at: updatedAt,
    version: version,
    snapshot_json: JSON.stringify(snapshot),
    search_text: searchParts.map(cleanString_).join(' | ').toLowerCase()
  };
}

function openLibrarySpreadsheet_() {
  const id = PropertiesService.getScriptProperties().getProperty('DEAL_LIBRARY_SPREADSHEET_ID');
  if (!id) {
    throw new Error('Deal Library is not initialized. Run setupDealLibrary first.');
  }
  return SpreadsheetApp.openById(id);
}

function authorize_(suppliedToken) {
  const expected = PropertiesService.getScriptProperties().getProperty('DEAL_LIBRARY_TOKEN') || '';
  if (!expected) {
    throw new Error('Deal Library token is not configured. Run setupDealLibrary first.');
  }
  if (String(suppliedToken || '') !== expected) {
    throw new Error('Unauthorized Deal Library request.');
  }
}

function getOrCreateSheet_(spreadsheet, name, headers) {
  let sheet = spreadsheet.getSheetByName(name);
  if (!sheet) {
    sheet = spreadsheet.insertSheet(name);
  }
  ensureHeaders_(sheet, headers);
  return sheet;
}

function ensureHeaders_(sheet, headers) {
  const current = sheet.getLastColumn() > 0
    ? sheet.getRange(1, 1, 1, Math.max(sheet.getLastColumn(), headers.length)).getValues()[0]
    : [];
  const currentHeaders = current.slice(0, headers.length).map(String);
  if (currentHeaders.join('|') !== headers.join('|')) {
    sheet.getRange(1, 1, 1, headers.length).setValues([headers]);
  }
  sheet.setFrozenRows(1);
}

function formatSheet_(sheet, columnCount) {
  sheet.setFrozenRows(1);
  sheet.getRange(1, 1, 1, columnCount).setFontWeight('bold');
  sheet.getRange(1, 1, 1, columnCount).setBackground('#d9ead3');
  sheet.autoResizeColumns(1, columnCount);
}

function sheetRowsAsObjects_(sheet, headers) {
  const lastRow = sheet.getLastRow();
  if (lastRow < 2) return [];
  const values = sheet.getRange(2, 1, lastRow - 1, headers.length).getValues();
  return values.map(row => {
    const object = {};
    headers.forEach((header, index) => object[header] = row[index]);
    return object;
  });
}

function parseJsonBody_(e) {
  const text = e && e.postData ? e.postData.contents : '';
  if (!text) return {};
  const parsed = JSON.parse(text);
  return parsed && typeof parsed === 'object' ? parsed : {};
}

function jsonResponse_(data) {
  return ContentService
    .createTextOutput(JSON.stringify(data))
    .setMimeType(ContentService.MimeType.JSON);
}

function safeParseJson_(value, fallback) {
  try {
    return JSON.parse(String(value || ''));
  } catch (error) {
    return fallback;
  }
}

function cleanString_(value) {
  if (value === null || value === undefined) return '';
  return String(value).trim();
}

function number_(value) {
  const parsed = Number(value || 0);
  return isFinite(parsed) ? parsed : 0;
}
