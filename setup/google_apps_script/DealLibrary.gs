const DEAL_SHEET = 'Deal Library';
const HISTORY_SHEET = 'Deal History';
const SNAPSHOT_SHEET = 'Deal Snapshots';
const SETUP_SHEET = 'Deal Library Setup';
const SNAPSHOT_CHUNK_SIZE = 40000;

const DEAL_HEADERS = [
  'Deal ID', 'Address', 'City', 'State', 'Zip', 'Listing URL', 'Lead Source',
  'Deal Lane', 'Decision', 'Confidence', 'Asking Price',
  'Current Negotiated Price', 'Starting Offer', 'Absolute Maximum', 'Rent',
  'Rent Comp Count', 'ARV', 'Sold Comp Count', 'Repairs', 'Deal Status',
  'Assigned To', 'Team Notes', 'Updated By', 'Updated At', 'Created At',
  'Version', 'Snapshot Version ID', 'Snapshot Chunks', 'Search Text'
];

const HISTORY_HEADERS = ['Version ID'].concat(DEAL_HEADERS);
const SNAPSHOT_HEADERS = [
  'Deal ID', 'Version ID', 'Chunk Index', 'Chunk Count', 'Snapshot Chunk', 'Saved At'
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

  const sheets = ensureSheets_();
  formatSheet_(sheets.deals, DEAL_HEADERS.length);
  formatSheet_(sheets.history, HISTORY_HEADERS.length);
  formatSheet_(sheets.snapshots, SNAPSHOT_HEADERS.length);

  let setup = spreadsheet.getSheetByName(SETUP_SHEET);
  if (!setup) setup = spreadsheet.insertSheet(SETUP_SHEET);
  setup.clearContents();
  setup.getRange(1, 1, 1, 3).setValues([['Setting', 'Value', 'Instructions']]);
  setup.getRange(2, 1, 6, 3).setValues([
    ['Spreadsheet ID', spreadsheet.getId(), 'Created automatically.'],
    ['DEAL_LIBRARY_TOKEN', token, 'Copy this exact token into Streamlit secrets.'],
    ['DEAL_LIBRARY_WEBHOOK_URL', 'Add after deployment', 'Deploy this script as a web app, then paste the /exec URL here and into Streamlit secrets.'],
    ['DEAL_LIBRARY_APP_URL', 'Your Streamlit app URL', 'Used to create one-click links for team members.'],
    ['Snapshot storage', 'Chunked', 'Large analyses are split safely across Deal Snapshots rows.'],
    ['Status', 'Ready to deploy', 'Deploy > New deployment > Web app > Execute as Me > Anyone with the link.']
  ]);
  setup.setFrozenRows(1);
  setup.autoResizeColumns(1, 3);
  setup.getRange(1, 1, 1, 3).setFontWeight('bold');

  return {
    ok: true,
    spreadsheet_id: spreadsheet.getId(),
    token: token,
    deals_sheet: DEAL_SHEET,
    history_sheet: HISTORY_SHEET,
    snapshots_sheet: SNAPSHOT_SHEET
  };
}

function doGet(e) {
  try {
    const params = (e && e.parameter) || {};
    authorize_(params.token || '');
    const action = String(params.action || 'health').toLowerCase();
    if (action === 'health') return json_(health_());
    if (action === 'search' || action === 'list') {
      return json_(searchDeals_(params.q || '', Number(params.limit || 25)));
    }
    if (action === 'get') return json_(getDeal_(params.deal_id || ''));
    return json_({ok: false, error: 'Unknown Deal Library action: ' + action});
  } catch (error) {
    return json_({ok: false, error: String(error && error.message ? error.message : error)});
  }
}

function doPost(e) {
  try {
    const body = JSON.parse((e && e.postData && e.postData.contents) || '{}');
    authorize_(body.token || '');
    const action = String(body.action || '').toLowerCase();
    if (action === 'upsert') return json_(upsertDeal_(body.snapshot || {}));
    return json_({ok: false, error: 'Unknown Deal Library action: ' + action});
  } catch (error) {
    return json_({ok: false, error: String(error && error.message ? error.message : error)});
  }
}

function authorize_(suppliedToken) {
  const expected = PropertiesService.getScriptProperties().getProperty('DEAL_LIBRARY_TOKEN') || '';
  if (!expected) throw new Error('Deal Library is not initialized. Run setupDealLibrary first.');
  if (suppliedToken !== expected) throw new Error('Unauthorized Deal Library request.');
}

function spreadsheet_() {
  const id = PropertiesService.getScriptProperties().getProperty('DEAL_LIBRARY_SPREADSHEET_ID') || '';
  if (!id) throw new Error('Deal Library is not initialized. Run setupDealLibrary first.');
  return SpreadsheetApp.openById(id);
}

function ensureSheet_(name, headers) {
  const ss = spreadsheet_();
  let sheet = ss.getSheetByName(name);
  if (!sheet) sheet = ss.insertSheet(name);
  if (sheet.getLastRow() === 0) {
    sheet.getRange(1, 1, 1, headers.length).setValues([headers]);
    sheet.setFrozenRows(1);
  } else {
    const existing = sheet.getRange(1, 1, 1, Math.max(sheet.getLastColumn(), headers.length)).getValues()[0];
    headers.forEach((header, index) => {
      if (existing[index] !== header) sheet.getRange(1, index + 1).setValue(header);
    });
  }
  return sheet;
}

function ensureSheets_() {
  return {
    deals: ensureSheet_(DEAL_SHEET, DEAL_HEADERS),
    history: ensureSheet_(HISTORY_SHEET, HISTORY_HEADERS),
    snapshots: ensureSheet_(SNAPSHOT_SHEET, SNAPSHOT_HEADERS)
  };
}

function formatSheet_(sheet, columns) {
  sheet.setFrozenRows(1);
  sheet.getRange(1, 1, 1, columns).setFontWeight('bold');
  sheet.autoResizeColumns(1, Math.min(columns, 15));
}

function clean_(value) {
  return String(value === null || value === undefined ? '' : value).trim();
}

function number_(value) {
  const parsed = Number(value || 0);
  return isNaN(parsed) ? 0 : parsed;
}

function rowObject_(headers, row) {
  const result = {};
  headers.forEach((header, index) => result[header] = row[index]);
  return result;
}

function findDealRow_(sheet, dealId) {
  if (!dealId || sheet.getLastRow() < 2) return 0;
  const values = sheet.getRange(2, 1, sheet.getLastRow() - 1, 1).getValues();
  for (let index = 0; index < values.length; index++) {
    if (clean_(values[index][0]) === dealId) return index + 2;
  }
  return 0;
}

function chunkText_(text) {
  const chunks = [];
  for (let index = 0; index < text.length; index += SNAPSHOT_CHUNK_SIZE) {
    chunks.push(text.slice(index, index + SNAPSHOT_CHUNK_SIZE));
  }
  return chunks.length ? chunks : ['{}'];
}

function writeSnapshot_(sheet, dealId, versionId, snapshot, savedAt) {
  const chunks = chunkText_(JSON.stringify(snapshot));
  const rows = chunks.map((chunk, index) => [dealId, versionId, index + 1, chunks.length, chunk, savedAt]);
  sheet.getRange(sheet.getLastRow() + 1, 1, rows.length, SNAPSHOT_HEADERS.length).setValues(rows);
  return chunks.length;
}

function readSnapshot_(sheet, dealId, versionId) {
  if (sheet.getLastRow() < 2) return null;
  const rows = sheet.getRange(2, 1, sheet.getLastRow() - 1, SNAPSHOT_HEADERS.length).getValues();
  const chunks = rows
    .filter(row => clean_(row[0]) === dealId && clean_(row[1]) === versionId)
    .sort((a, b) => Number(a[2]) - Number(b[2]));
  if (!chunks.length) return null;
  return JSON.parse(chunks.map(row => String(row[4] || '')).join(''));
}

function searchText_(snapshot) {
  return [
    snapshot.address, snapshot.city, snapshot.property_state, snapshot.zip,
    snapshot.lead_source, snapshot.deal_lane, snapshot.decision,
    snapshot.deal_status, snapshot.assigned_to, snapshot.updated_by,
    snapshot.team_notes
  ].map(clean_).join(' | ').toLowerCase();
}

function summaryFromSnapshot_(snapshot, version, versionId, chunkCount, createdAt) {
  const savedAt = clean_(snapshot.saved_at) || new Date().toISOString();
  return {
    'Deal ID': clean_(snapshot.deal_id),
    'Address': clean_(snapshot.address),
    'City': clean_(snapshot.city),
    'State': clean_(snapshot.property_state),
    'Zip': clean_(snapshot.zip),
    'Listing URL': clean_(snapshot.listing_url),
    'Lead Source': clean_(snapshot.lead_source),
    'Deal Lane': clean_(snapshot.deal_lane),
    'Decision': clean_(snapshot.decision),
    'Confidence': clean_(snapshot.confidence),
    'Asking Price': number_(snapshot.asking_price),
    'Current Negotiated Price': number_(snapshot.current_negotiated_price),
    'Starting Offer': number_(snapshot.starting_offer),
    'Absolute Maximum': number_(snapshot.absolute_maximum),
    'Rent': number_(snapshot.rent),
    'Rent Comp Count': number_(snapshot.rent_comp_count),
    'ARV': number_(snapshot.arv),
    'Sold Comp Count': number_(snapshot.sold_comp_count),
    'Repairs': number_(snapshot.repairs),
    'Deal Status': clean_(snapshot.deal_status),
    'Assigned To': clean_(snapshot.assigned_to),
    'Team Notes': clean_(snapshot.team_notes),
    'Updated By': clean_(snapshot.updated_by),
    'Updated At': savedAt,
    'Created At': createdAt || savedAt,
    'Version': version,
    'Snapshot Version ID': versionId,
    'Snapshot Chunks': chunkCount,
    'Search Text': searchText_(snapshot)
  };
}

function summaryRow_(summary) {
  return DEAL_HEADERS.map(header => summary[header] === undefined ? '' : summary[header]);
}

function upsertDeal_(incomingSnapshot) {
  if (!incomingSnapshot || typeof incomingSnapshot !== 'object') {
    return {ok: false, error: 'Missing deal snapshot.'};
  }
  const dealId = clean_(incomingSnapshot.deal_id);
  if (!dealId || (!clean_(incomingSnapshot.address) && !clean_(incomingSnapshot.listing_url))) {
    return {ok: false, error: 'A Deal ID and property address or listing URL are required.'};
  }

  const lock = LockService.getScriptLock();
  lock.waitLock(30000);
  try {
    const sheets = ensureSheets_();
    const existingRow = findDealRow_(sheets.deals, dealId);
    let createdAt = new Date().toISOString();
    let currentVersion = 0;
    let currentUpdatedBy = '';
    if (existingRow) {
      const existingValues = sheets.deals.getRange(existingRow, 1, 1, DEAL_HEADERS.length).getValues()[0];
      const existing = rowObject_(DEAL_HEADERS, existingValues);
      createdAt = clean_(existing['Created At']) || createdAt;
      currentVersion = number_(existing['Version']);
      currentUpdatedBy = clean_(existing['Updated By']);
    }

    const baseVersion = number_(incomingSnapshot.base_version);
    if (existingRow && baseVersion > 0 && baseVersion !== currentVersion) {
      return {
        ok: false,
        conflict: true,
        current_version: currentVersion,
        current_updated_by: currentUpdatedBy,
        error: 'A teammate saved a newer version. Reopen the latest saved deal before updating it.'
      };
    }

    const now = new Date().toISOString();
    const nextVersion = currentVersion + 1;
    const snapshot = JSON.parse(JSON.stringify(incomingSnapshot));
    snapshot.version = nextVersion;
    snapshot.base_version = nextVersion;
    snapshot.created_at = createdAt;
    snapshot.updated_at = now;
    snapshot.saved_at = now;
    const versionId = dealId + '-v' + nextVersion + '-' + Utilities.getUuid();
    const chunkCount = writeSnapshot_(sheets.snapshots, dealId, versionId, snapshot, now);
    const summary = summaryFromSnapshot_(snapshot, nextVersion, versionId, chunkCount, createdAt);
    const row = summaryRow_(summary);

    if (existingRow) {
      sheets.deals.getRange(existingRow, 1, 1, DEAL_HEADERS.length).setValues([row]);
    } else {
      sheets.deals.appendRow(row);
    }
    sheets.history.appendRow([versionId].concat(row));

    return {
      ok: true,
      deal_id: dealId,
      version: nextVersion,
      version_id: versionId,
      saved_at: now,
      snapshot_chunks: chunkCount,
      updated_existing: Boolean(existingRow)
    };
  } finally {
    lock.releaseLock();
  }
}

function getDeal_(dealId) {
  const sheets = ensureSheets_();
  const rowNumber = findDealRow_(sheets.deals, clean_(dealId));
  if (!rowNumber) return {ok: false, error: 'Saved deal was not found.'};
  const row = sheets.deals.getRange(rowNumber, 1, 1, DEAL_HEADERS.length).getValues()[0];
  const record = rowObject_(DEAL_HEADERS, row);
  const versionId = clean_(record['Snapshot Version ID']);
  const snapshot = readSnapshot_(sheets.snapshots, clean_(dealId), versionId);
  if (!snapshot) return {ok: false, error: 'The deal summary exists, but its full snapshot could not be reconstructed.'};
  snapshot.version = number_(record['Version']);
  snapshot.base_version = number_(record['Version']);
  snapshot.updated_at = clean_(record['Updated At']);
  return {ok: true, deal: publicSummary_(record), snapshot: snapshot};
}

function publicSummary_(record) {
  return {
    deal_id: clean_(record['Deal ID']),
    address: clean_(record['Address']),
    city: clean_(record['City']),
    state: clean_(record['State']),
    zip: clean_(record['Zip']),
    listing_url: clean_(record['Listing URL']),
    lead_source: clean_(record['Lead Source']),
    deal_lane: clean_(record['Deal Lane']),
    decision: clean_(record['Decision']),
    confidence: clean_(record['Confidence']),
    asking_price: number_(record['Asking Price']),
    current_negotiated_price: number_(record['Current Negotiated Price']),
    starting_offer: number_(record['Starting Offer']),
    absolute_maximum: number_(record['Absolute Maximum']),
    rent: number_(record['Rent']),
    rent_comp_count: number_(record['Rent Comp Count']),
    arv: number_(record['ARV']),
    sold_comp_count: number_(record['Sold Comp Count']),
    repairs: number_(record['Repairs']),
    deal_status: clean_(record['Deal Status']),
    assigned_to: clean_(record['Assigned To']),
    team_notes: clean_(record['Team Notes']),
    updated_by: clean_(record['Updated By']),
    updated_at: clean_(record['Updated At']),
    created_at: clean_(record['Created At']),
    version: number_(record['Version'])
  };
}

function searchDeals_(query, requestedLimit) {
  const sheets = ensureSheets_();
  if (sheets.deals.getLastRow() < 2) return {ok: true, deals: [], count: 0};
  const limit = Math.max(1, Math.min(Number(requestedLimit || 25), 100));
  const rows = sheets.deals.getRange(2, 1, sheets.deals.getLastRow() - 1, DEAL_HEADERS.length).getValues();
  const q = clean_(query).toLowerCase();
  const deals = rows
    .map(row => rowObject_(DEAL_HEADERS, row))
    .filter(record => !q || clean_(record['Search Text']).indexOf(q) !== -1)
    .sort((a, b) => clean_(b['Updated At']).localeCompare(clean_(a['Updated At'])))
    .slice(0, limit)
    .map(publicSummary_);
  return {ok: true, deals: deals, count: deals.length};
}

function health_() {
  const sheets = ensureSheets_();
  return {
    ok: true,
    spreadsheet_id: spreadsheet_().getId(),
    spreadsheet_name: spreadsheet_().getName(),
    deals_count: Math.max(sheets.deals.getLastRow() - 1, 0),
    history_count: Math.max(sheets.history.getLastRow() - 1, 0),
    snapshot_chunk_count: Math.max(sheets.snapshots.getLastRow() - 1, 0),
    checked_at: new Date().toISOString()
  };
}

function json_(payload) {
  return ContentService.createTextOutput(JSON.stringify(payload)).setMimeType(ContentService.MimeType.JSON);
}
