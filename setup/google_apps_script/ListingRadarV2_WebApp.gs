function doPost(e) {
  try {
    const body = JSON.parse((e && e.postData && e.postData.contents) || '{}');
    const action = String(body.action || '').toLowerCase();

    if (action === 'apify_webhook') {
      return lrJson_({ok: true, result: lrHandleApifyWebhook_(body)});
    }

    lrAuthorizeApp_(body.token || '');
    if (action === 'health') return lrJson_(lrHealth_());
    if (action === 'list' || action === 'search') return lrJson_(lrList_(body));
    if (action === 'list_markets') return lrJson_(lrListMarkets_());
    if (action === 'get') return lrJson_(lrGet_(body.listing_key || ''));
    if (action === 'update_queue') return lrJson_(lrUpdateQueue_(body.listing_key || '', body.changes || {}));
    return lrJson_({ok: false, error: 'Unknown Listing Radar action.'});
  } catch (error) {
    return lrJson_({
      ok: false,
      error: String(error && error.message ? error.message : error)
        .replace(/apify_api_[A-Za-z0-9_-]+/g, '[REDACTED]')
        .replace(/([?&](?:token|secret)=)[^&\s]+/gi, '$1[REDACTED]')
    });
  }
}

function lrAuthorizeApp_(suppliedToken) {
  const expected = PropertiesService.getScriptProperties().getProperty('LISTING_RADAR_TOKEN') || '';
  if (!expected) throw new Error('Listing Radar is not initialized.');
  if (String(suppliedToken || '') !== expected) throw new Error('Unauthorized Listing Radar request.');
}

function lrHealth_() {
  const spreadsheet = lrSpreadsheet_();
  const current = spreadsheet.getSheetByName(LR.SHEETS.CURRENT);
  const runs = spreadsheet.getSheetByName(LR.SHEETS.RUNS);
  const quarantine = spreadsheet.getSheetByName(LR.SHEETS.QUARANTINE);
  let lastSuccessfulRun = '';
  if (runs.getLastRow() > 1) {
    const values = runs.getRange(2, 1, runs.getLastRow() - 1, LR.HEADERS.RUNS.length).getValues();
    for (let index = values.length - 1; index >= 0; index--) {
      const record = lrRowObject_(LR.HEADERS.RUNS, values[index]);
      if (String(record.status || '') === 'SUCCEEDED') {
        lastSuccessfulRun = String(record.finished_at || record.processed_at || '');
        break;
      }
    }
  }
  return {
    ok: true,
    current_count: Math.max(current.getLastRow() - 1, 0),
    run_count: Math.max(runs.getLastRow() - 1, 0),
    quarantine_count: Math.max(quarantine.getLastRow() - 1, 0),
    last_successful_run: lastSuccessfulRun,
    checked_at: new Date().toISOString()
  };
}

function lrListMarkets_() {
  const sheet = lrSpreadsheet_().getSheetByName(LR.SHEETS.MARKETS);
  const values = sheet.getDataRange().getValues();
  const markets = values.slice(1).map(function(row) {
    return lrRowObject_(LR.HEADERS.MARKETS, row);
  }).filter(function(record) {
    return String(record.market_id || '').trim();
  });
  return {ok: true, markets: markets, count: markets.length};
}

function lrList_(filters) {
  const spreadsheet = lrSpreadsheet_();
  const currentSheet = spreadsheet.getSheetByName(LR.SHEETS.CURRENT);
  const queueSheet = spreadsheet.getSheetByName(LR.SHEETS.QUEUE);
  const currentValues = currentSheet.getLastRow() > 1
    ? currentSheet.getRange(2, 1, currentSheet.getLastRow() - 1, LR.HEADERS.CURRENT.length).getValues()
    : [];
  const queueMap = new Map();
  if (queueSheet.getLastRow() > 1) {
    queueSheet.getRange(2, 1, queueSheet.getLastRow() - 1, LR.HEADERS.QUEUE.length).getValues()
      .forEach(function(row) {
        const record = lrRowObject_(LR.HEADERS.QUEUE, row);
        if (record.listing_key) queueMap.set(String(record.listing_key), record);
      });
  }

  const query = String(filters.query || '').toLowerCase().trim();
  const marketId = String(filters.market_id || '').trim();
  const feedStatus = String(filters.feed_status || '').trim();
  const workflowStatus = String(filters.workflow_status || '').trim();
  const limit = Math.max(1, Math.min(Number(filters.limit || 100), 500));
  const priority = {PRICE_DROP: 0, NEW: 1, UPDATED: 2, PRICE_INCREASE: 3, UNCHANGED: 4};

  const listings = currentValues.map(function(row) {
    const listing = lrRowObject_(LR.HEADERS.CURRENT, row);
    const queue = queueMap.get(String(listing.listing_key || '')) || {};
    return Object.assign({}, listing, queue);
  }).filter(function(listing) {
    if (marketId && String(listing.market_id || '') !== marketId) return false;
    if (feedStatus && String(listing.feed_status || '') !== feedStatus) return false;
    if (workflowStatus && String(listing.workflow_status || 'New') !== workflowStatus) return false;
    if (!query) return true;
    const haystack = [
      listing.address, listing.city, listing.state, listing.zip, listing.agent_name,
      listing.agent_email, listing.agent_phone, listing.agent_brokerage,
      listing.assigned_to, listing.workflow_status
    ].join(' ').toLowerCase();
    return haystack.indexOf(query) !== -1;
  }).sort(function(a, b) {
    const aPriority = priority[String(a.feed_status || '')] === undefined ? 9 : priority[String(a.feed_status || '')];
    const bPriority = priority[String(b.feed_status || '')] === undefined ? 9 : priority[String(b.feed_status || '')];
    if (aPriority !== bPriority) return aPriority - bPriority;
    return String(b.last_seen || '').localeCompare(String(a.last_seen || ''));
  }).slice(0, limit);

  return {ok: true, listings: listings, count: listings.length};
}

function lrGet_(listingKey) {
  const result = lrList_({limit: 500});
  const listing = result.listings.find(function(item) {
    return String(item.listing_key || '') === String(listingKey || '');
  });
  return listing
    ? {ok: true, listing: listing}
    : {ok: false, error: 'Listing was not found.'};
}

function lrUpdateQueue_(listingKey, changes) {
  listingKey = String(listingKey || '').trim();
  if (!listingKey) return {ok: false, error: 'Listing key is required.'};
  const allowed = [
    'assigned_to', 'workflow_status', 'last_contact_at', 'next_follow_up',
    'agent_response', 'team_notes', 'dismiss_reason', 'deal_id', 'updated_by'
  ];
  const lock = LockService.getScriptLock();
  lock.waitLock(30000);
  try {
    const sheet = lrSpreadsheet_().getSheetByName(LR.SHEETS.QUEUE);
    let rowNumber = 0;
    if (sheet.getLastRow() > 1) {
      const keys = sheet.getRange(2, 1, sheet.getLastRow() - 1, 1).getValues();
      for (let index = 0; index < keys.length; index++) {
        if (String(keys[index][0] || '') === listingKey) {
          rowNumber = index + 2;
          break;
        }
      }
    }
    const record = {listing_key: listingKey, workflow_status: 'New', updated_at: new Date().toISOString()};
    if (rowNumber) {
      Object.assign(record, lrRowObject_(LR.HEADERS.QUEUE, sheet.getRange(rowNumber, 1, 1, LR.HEADERS.QUEUE.length).getValues()[0]));
    }
    allowed.forEach(function(key) {
      if (changes[key] !== undefined) record[key] = changes[key];
    });
    record.updated_at = new Date().toISOString();
    const row = lrObjectRow_(LR.HEADERS.QUEUE, record);
    if (rowNumber) sheet.getRange(rowNumber, 1, 1, row.length).setValues([row]);
    else sheet.getRange(sheet.getLastRow() + 1, 1, 1, row.length).setValues([row]);
    SpreadsheetApp.flush();
    return {ok: true, queue: record};
  } finally {
    lock.releaseLock();
  }
}

function lrJson_(payload) {
  return ContentService.createTextOutput(JSON.stringify(payload))
    .setMimeType(ContentService.MimeType.JSON);
}
