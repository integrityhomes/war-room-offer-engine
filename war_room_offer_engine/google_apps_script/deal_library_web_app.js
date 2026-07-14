const DEAL_SHEET = 'Deal Library';
const HISTORY_SHEET = 'Deal History';
const SNAPSHOT_SHEET = 'Deal Snapshots';
const SNAPSHOT_CHUNK_SIZE = 40000;

const DEAL_HEADERS = [
  'Deal ID', 'Address', 'City', 'State', 'Zip', 'Listing URL', 'Lead Source',
  'Deal Lane', 'Decision', 'Confidence', 'Asking Price',
  'Current Negotiated Price', 'Starting Offer', 'Absolute Maximum', 'Rent',
  'Rent Comp Count', 'ARV', 'Sold Comp Count', 'Repairs', 'Deal Status',
  'Assigned To', 'Team Notes', 'Updated By', 'Updated At', 'Created At',
  'Snapshot Version ID', 'Snapshot Chunks'
];

const HISTORY_HEADERS = ['Version ID'].concat(DEAL_HEADERS);
const SNAPSHOT_HEADERS = [
  'Deal ID', 'Version ID', 'Chunk Index', 'Chunk Count', 'Snapshot Chunk', 'Saved At'
];

function doGet(e) {
  try {
    const params = (e && e.parameter) || {};
    assertAuthorized_(params.token || '');
    const action = String(params.action || 'health').toLowerCase();
    if (action === 'health') {
      ensureSheets_();
      return json_({ ok: true, service: 'War Room Deal Library', timestamp: new Date().toISOString() });
    }
    if (action === 'search' || action === 'list') {
      return json_(searchDeals_(params.q || '', Number(params.limit || 25)));
    }
    if (action === 'get') {
      return json_(getDeal_(params.deal_id || ''));
    }
    return json_({ ok: false, error: 'Unknown action: ' + action });
  } catch (error) {
    return json_({ ok: false, error: String(error && error.message ? error.message : error) });
  }
}

function doPost(e) {
  try {
    const body = JSON.parse((e && e.postData && e.postData.contents) || '{}');
    assertAuthorized_(body.token || '');
    const action = String(body.action || '').toLowerCase();
    if (action === 'upsert') {
      return json_(upsertDeal_(body.snapshot || {}));
    }
    return json_({ ok: false, error: 'Unknown action: ' + action });
  } catch (error) {
    return json_({ ok: false, error: String(error && error.message ? error.message : error) });
  }
}

function assertAuthorized_(providedToken) {
  const expected = PropertiesService.getScriptProperties().getProperty('DEAL_LIBRARY_TOKEN') || '';
  if (expected && providedToken !== expected) {
    throw new Error('Unauthorized Deal Library request.');
  }
}

function spreadsheet_() {
  const spreadsheetId = PropertiesService.getScriptProperties().getProperty('DEAL_LIBRARY_SPREADSHEET_ID') || '';
  return spreadsheetId ? SpreadsheetApp.openById(spreadsheetId) : SpreadsheetApp.getActiveSpreadsheet();
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

function normalizeText_(value) {
  return String(value === null || value === undefined ? '' : value).trim();
}

function number_(value) {
  const parsed = Number(value || 0);
  return isNaN(parsed) ? 0 : parsed;
}

function indexMap_(headers) {
  const map = {};
  headers.forEach((header, index) => map[header] = index);
  return map;
}

function rowObject_(headers, row) {
  const result = {};
  headers.forEach((header, index) => result[header] = row[index]);
  return result;
}

function summaryFromSnapshot_(snapshot, versionId, chunkCount, createdAt) {
  const savedAt = normalizeText_(snapshot.saved_at) || new Date().toISOString();
  return {
    'Deal ID': normalizeText_(snapshot.deal_id),
    'Address': normalizeText_(snapshot.address),
    'City': normalizeText_(snapshot.city),
    'State': normalizeText_(snapshot.state),
    'Zip': normalizeText_(snapshot.zip),
    'Listing URL': normalizeText_(snapshot.listing_url),
    'Lead Source': normalizeText_(snapshot.lead_source),
    'Deal Lane': normalizeText_(snapshot.deal_lane),
    'Decision': normalizeText_(snapshot.decision),
    'Confidence': normalizeText_(snapshot.confidence),
    'Asking Price': number_(snapshot.asking_price),
    'Current Negotiated Price': number_(snapshot.current_negotiated_price),
    'Starting Offer': number_(snapshot.starting_offer),
    'Absolute Maximum': number_(snapshot.absolute_maximum),
    'Rent': number_(snapshot.rent),
    'Rent Comp Count': number_(snapshot.rent_comp_count),
    'ARV': number_(snapshot.arv),
    'Sold Comp Count': number_(snapshot.sold_comp_count),
    'Repairs': number_(snapshot.repairs),
    'Deal Status': normalizeText_(snapshot.deal_status),
    'Assigned To': normalizeText_(snapshot.assigned_to),
    'Team Notes': normalizeText_(snapshot.team_notes),
    'Updated By': normalizeText_(snapshot.updated_by),
    'Updated At': savedAt,
    'Created At': createdAt || savedAt,
    'Snapshot Version ID': versionId,
    'Snapshot Chunks': chunkCount
  };
}

function summaryRow_(summary) {
  return DEAL_HEADERS.map(header => summary[header] === undefined ? '' : summary[header]);
}

function findDealRow_(sheet, dealId) {
  if (!dealId || sheet.getLastRow() < 2) return 0;
  const values = sheet.getRange(2, 1, sheet.getLastRow() - 1, 1).getValues();
  for (let index = 0; index < values.length; index++) {
    if (normalizeText_(values[index][0]) === dealId) return index + 2;
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
  const json = JSON.stringify(snapshot);
  const chunks = chunkText_(json);
  const rows = chunks.map((chunk, index) => [dealId, versionId, index + 1, chunks.length, chunk, savedAt]);
  sheet.getRange(sheet.getLastRow() + 1, 1, rows.length, SNAPSHOT_HEADERS.length).setValues(rows);
  return chunks.length;
}

function readSnapshot_(sheet, dealId, versionId) {
  if (sheet.getLastRow() < 2) return null;
  const rows = sheet.getRange(2, 1, sheet.getLastRow() - 1, SNAPSHOT_HEADERS.length).getValues();
  const chunks = rows
    .filter(row => normalizeText_(row[0]) === dealId && normalizeText_(row[1]) === versionId)
    .sort((a, b) => Number(a[2]) - Number(b[2]));
  if (!chunks.length) return null;
  return JSON.parse(chunks.map(row => String(row[4] || '')).join(''));
}

function upsertDeal_(snapshot) {
  const sheets = ensureSheets_();
  const dealId = normalizeText_(snapshot.deal_id);
  if (!dealId) return { ok: false, error: 'Saved deal is missing a Deal ID.' };
  if (!normalizeText_(snapshot.address) && !normalizeText_(snapshot.listing_url)) {
    return { ok: false, error: 'Saved deal is missing an address or listing URL.' };
  }

  const savedAt = normalizeText_(snapshot.saved_at) || new Date().toISOString();
  const versionId = dealId + '-' + Utilities.getUuid();
  const existingRow = findDealRow_(sheets.deals, dealId);
  let createdAt = savedAt;
  if (existingRow) {
    const existing = sheets.deals.getRange(existingRow, 1, 1, DEAL_HEADERS.length).getValues()[0];
    createdAt = normalizeText_(existing[DEAL_HEADERS.indexOf('Created At')]) || savedAt;
  }

  const chunkCount = writeSnapshot_(sheets.snapshots, dealId, versionId, snapshot, savedAt);
  const summary = summaryFromSnapshot_(snapshot, versionId, chunkCount, createdAt);
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
    version_id: versionId,
    saved_at: savedAt,
    snapshot_chunks: chunkCount,
    updated_existing: Boolean(existingRow)
  };
}

function getDeal_(dealId) {
  const sheets = ensureSheets_();
  const rowNumber = findDealRow_(sheets.deals, normalizeText_(dealId));
  if (!rowNumber) return { ok: false, error: 'Saved deal was not found.' };
  const row = sheets.deals.getRange(rowNumber, 1, 1, DEAL_HEADERS.length).getValues()[0];
  const record = rowObject_(DEAL_HEADERS, row);
  const versionId = normalizeText_(record['Snapshot Version ID']);
  const snapshot = readSnapshot_(sheets.snapshots, normalizeText_(dealId), versionId);
  if (!snapshot) return { ok: false, error: 'Saved deal summary exists, but its full snapshot could not be reconstructed.' };
  return { ok: true, deal: publicSummary_(record), snapshot: snapshot };
}

function publicSummary_(record) {
  return {
    deal_id: normalizeText_(record['Deal ID']),
    address: normalizeText_(record['Address']),
    city: normalizeText_(record['City']),
    state: normalizeText_(record['State']),
    zip: normalizeText_(record['Zip']),
    listing_url: normalizeText_(record['Listing URL']),
    lead_source: normalizeText_(record['Lead Source']),
    deal_lane: normalizeText_(record['Deal Lane']),
    decision: normalizeText_(record['Decision']),
    confidence: normalizeText_(record['Confidence']),
    asking_price: number_(record['Asking Price']),
    current_negotiated_price: number_(record['Current Negotiated Price']),
    starting_offer: number_(record['Starting Offer']),
    absolute_maximum: number_(record['Absolute Maximum']),
    rent: number_(record['Rent']),
    rent_comp_count: number_(record['Rent Comp Count']),
    arv: number_(record['ARV']),
    sold_comp_count: number_(record['Sold Comp Count']),
    repairs: number_(record['Repairs']),
    deal_status: normalizeText_(record['Deal Status']),
    assigned_to: normalizeText_(record['Assigned To']),
    team_notes: normalizeText_(record['Team Notes']),
    updated_by: normalizeText_(record['Updated By']),
    updated_at: normalizeText_(record['Updated At']),
    created_at: normalizeText_(record['Created At'])
  };
}

function searchDeals_(query, requestedLimit) {
  const sheets = ensureSheets_();
  if (sheets.deals.getLastRow() < 2) return { ok: true, deals: [] };
  const limit = Math.max(1, Math.min(Number(requestedLimit || 25), 100));
  const rows = sheets.deals.getRange(2, 1, sheets.deals.getLastRow() - 1, DEAL_HEADERS.length).getValues();
  const q = normalizeText_(query).toLowerCase();
  const deals = rows
    .map(row => rowObject_(DEAL_HEADERS, row))
    .filter(record => {
      if (!q) return true;
      return [
        record['Address'], record['City'], record['State'], record['Zip'],
        record['Deal Status'], record['Assigned To'], record['Decision'],
        record['Deal Lane'], record['Lead Source'], record['Team Notes']
      ].some(value => normalizeText_(value).toLowerCase().indexOf(q) !== -1);
    })
    .sort((a, b) => normalizeText_(b['Updated At']).localeCompare(normalizeText_(a['Updated At'])))
    .slice(0, limit)
    .map(publicSummary_);
  return { ok: true, deals: deals, count: deals.length };
}

function json_(payload) {
  return ContentService
    .createTextOutput(JSON.stringify(payload))
    .setMimeType(ContentService.MimeType.JSON);
}
