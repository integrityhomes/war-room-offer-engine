function lrHandleApifyWebhook_(payload) {
  const properties = PropertiesService.getScriptProperties();
  const expected = properties.getProperty('LISTING_RADAR_WEBHOOK_SECRET') || '';
  if (!expected || String(payload.secret || '') !== expected) {
    throw new Error('Unauthorized Listing Radar webhook.');
  }

  const resource = payload.resource || {};
  const datasetId = String(payload.dataset_id || resource.defaultDatasetId || resource.defaultDatasetID || '').trim();
  const runId = String(payload.run_id || resource.id || '').trim();
  const taskId = String(payload.task_id || resource.actorTaskId || resource.actId || '').trim();
  if (!datasetId) throw new Error('Apify webhook did not include a dataset ID.');

  const market = lrFindMarketByTask_(taskId, String(payload.market_id || '').trim());
  if (!market.market_id) {
    throw new Error('No Listing Radar market is mapped to Apify task: ' + taskId);
  }

  const items = lrFetchApifyDataset_(datasetId, Number(payload.limit || 1000));
  return lrIngestItems_(items, {
    market_id: market.market_id,
    run_id: runId || ('dataset-' + datasetId),
    dataset_id: datasetId,
    apify_task_id: taskId,
    started_at: String(resource.startedAt || payload.started_at || ''),
    finished_at: String(resource.finishedAt || payload.finished_at || ''),
    cost_usd: Number(payload.cost_usd || 0)
  });
}

function lrFetchApifyDataset_(datasetId, limit) {
  const token = PropertiesService.getScriptProperties().getProperty('APIFY_TOKEN') || '';
  if (!token) throw new Error('Missing Script Property: APIFY_TOKEN');

  const url = 'https://api.apify.com/v2/datasets/' + encodeURIComponent(datasetId) +
    '/items?clean=true&format=json&limit=' + encodeURIComponent(Math.max(1, Math.min(limit || 1000, 5000)));
  const response = UrlFetchApp.fetch(url, {
    method: 'get',
    headers: {Authorization: 'Bearer ' + token},
    muteHttpExceptions: true
  });
  const code = response.getResponseCode();
  if (code < 200 || code >= 300) {
    throw new Error('Apify dataset request failed with HTTP ' + code + '.');
  }
  const data = JSON.parse(response.getContentText());
  if (!Array.isArray(data)) throw new Error('Apify dataset did not return a listing array.');
  return data;
}

function lrFindMarketByTask_(taskId, explicitMarketId) {
  const sheet = lrSpreadsheet_().getSheetByName(LR.SHEETS.MARKETS);
  const values = sheet.getDataRange().getValues();
  const headers = values[0].map(String);
  for (let index = 1; index < values.length; index++) {
    const record = lrRowObject_(headers, values[index]);
    if (explicitMarketId && String(record.market_id) === explicitMarketId) return record;
    if (taskId && String(record.apify_task_id || '').trim() === taskId) return record;
  }
  return {};
}

function lrIngestItems_(items, context) {
  const lock = LockService.getScriptLock();
  lock.waitLock(30000);
  try {
    const spreadsheet = lrSpreadsheet_();
    const sheets = lrEnsureAllSheets_(spreadsheet);
    const currentSheet = sheets.CURRENT;
    const historySheet = sheets.HISTORY;
    const queueSheet = sheets.QUEUE;
    const quarantineSheet = sheets.QUARANTINE;
    const runSheet = sheets.RUNS;
    const observedAt = new Date().toISOString();

    const currentHeaders = LR.HEADERS.CURRENT;
    const currentRows = currentSheet.getLastRow() > 1
      ? currentSheet.getRange(2, 1, currentSheet.getLastRow() - 1, currentHeaders.length).getValues()
      : [];
    const currentMap = new Map();
    currentRows.forEach(function(row, index) {
      const key = String(row[0] || '').trim();
      if (key) currentMap.set(key, {index: index, record: lrRowObject_(currentHeaders, row)});
    });

    const queueKeys = lrExistingFirstColumnKeys_(queueSheet);
    const newRows = [];
    const queueRows = [];
    const historyRows = [];
    const quarantineRows = [];
    const seenThisRun = new Set();
    let newCount = 0;
    let updatedCount = 0;
    let priceChanges = 0;
    let duplicates = 0;

    (items || []).forEach(function(item) {
      const incoming = lrNormalizeListing_(item, context.market_id, context.run_id, observedAt);
      if (!incoming.listing_key || !incoming.address || !incoming.zip || !incoming.asking_price) {
        quarantineRows.push([
          lrDigest_('quarantine|' + context.run_id + '|' + JSON.stringify(item)),
          context.run_id,
          context.market_id,
          incoming.data_quality || 'Missing required listing fields',
          JSON.stringify(item).slice(0, 45000),
          observedAt
        ]);
        return;
      }
      if (seenThisRun.has(incoming.listing_key)) {
        duplicates++;
        return;
      }
      seenThisRun.add(incoming.listing_key);

      const found = currentMap.get(incoming.listing_key);
      if (!found) {
        newRows.push(lrObjectRow_(currentHeaders, incoming));
        currentMap.set(incoming.listing_key, {index: currentRows.length + newRows.length - 1, record: incoming});
        newCount++;
        historyRows.push(lrHistoryRow_(incoming, 'NEW_LISTING', '', '', '', observedAt));
        if (!queueKeys.has(incoming.listing_key)) {
          queueKeys.add(incoming.listing_key);
          queueRows.push([incoming.listing_key, '', 'New', '', '', '', '', '', '', '', observedAt]);
        }
        return;
      }

      const merged = lrMergeListing_(found.record, incoming, observedAt);
      currentRows[found.index] = lrObjectRow_(currentHeaders, merged.record);
      found.record = merged.record;
      if (merged.changed) updatedCount++;
      if (merged.priceChanged) priceChanges++;
      merged.events.forEach(function(event) {
        historyRows.push(lrObjectRow_(LR.HEADERS.HISTORY, event));
      });
    });

    if (currentRows.length) {
      currentSheet.getRange(2, 1, currentRows.length, currentHeaders.length).setValues(currentRows);
    }
    if (newRows.length) {
      currentSheet.getRange(currentSheet.getLastRow() + 1, 1, newRows.length, currentHeaders.length).setValues(newRows);
    }
    if (historyRows.length) {
      historySheet.getRange(historySheet.getLastRow() + 1, 1, historyRows.length, LR.HEADERS.HISTORY.length).setValues(historyRows);
    }
    if (queueRows.length) {
      queueSheet.getRange(queueSheet.getLastRow() + 1, 1, queueRows.length, LR.HEADERS.QUEUE.length).setValues(queueRows);
    }
    if (quarantineRows.length) {
      quarantineSheet.getRange(quarantineSheet.getLastRow() + 1, 1, quarantineRows.length, LR.HEADERS.QUARANTINE.length).setValues(quarantineRows);
    }

    const runRecord = {
      run_id: context.run_id,
      market_id: context.market_id,
      apify_task_id: context.apify_task_id,
      dataset_id: context.dataset_id,
      started_at: context.started_at,
      finished_at: context.finished_at,
      status: 'SUCCEEDED',
      items_received: (items || []).length,
      new_listings: newCount,
      updated_listings: updatedCount,
      price_changes: priceChanges,
      duplicates: duplicates,
      quarantined: quarantineRows.length,
      cost_usd: context.cost_usd || 0,
      error: '',
      processed_at: observedAt
    };
    runSheet.getRange(runSheet.getLastRow() + 1, 1, 1, LR.HEADERS.RUNS.length)
      .setValues([lrObjectRow_(LR.HEADERS.RUNS, runRecord)]);

    SpreadsheetApp.flush();
    return {
      ok: true,
      run_id: context.run_id,
      market_id: context.market_id,
      items_received: (items || []).length,
      new_listings: newCount,
      updated_listings: updatedCount,
      price_changes: priceChanges,
      duplicates: duplicates,
      quarantined: quarantineRows.length
    };
  } finally {
    lock.releaseLock();
  }
}

function lrNormalizeListing_(item, marketId, runId, observedAt) {
  const zpid = lrDigits_(lrPick_(item, ['zpid', 'id', 'listingId', 'hdpData.homeInfo.zpid']));
  const address = lrText_(lrPick_(item, ['address', 'streetAddress', 'unformattedAddress', 'fullAddress', 'hdpData.homeInfo.streetAddress']));
  const city = lrText_(lrPick_(item, ['city', 'addressCity', 'hdpData.homeInfo.city']));
  const state = lrText_(lrPick_(item, ['state', 'addressState', 'stateCode', 'hdpData.homeInfo.state'])).toUpperCase();
  const zip = lrDigits_(lrPick_(item, ['zip', 'zipcode', 'postalCode', 'hdpData.homeInfo.zipcode'])).slice(0, 5);
  const url = lrUrl_(lrPick_(item, ['url', 'detailUrl', 'hdpUrl', 'listingUrl', 'zillowUrl']));
  const price = lrNumber_(lrPick_(item, ['price', 'unformattedPrice', 'listPrice', 'asking_price', 'hdpData.homeInfo.price']));
  const phone = lrPhone_(lrPick_(item, ['agent_phone', 'agentPhone', 'listingAgent.phone', 'attributionInfo.agentPhoneNumber']));
  let email = lrText_(lrPick_(item, ['agent_email', 'agentEmail', 'listingAgent.email', 'attributionInfo.agentEmail'])).toLowerCase();
  if (email && !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email)) email = '';
  const key = lrListingKey_(zpid, address, zip, url);
  const missing = [];
  if (!key) missing.push('listing identity');
  if (!address) missing.push('address');
  if (!zip) missing.push('ZIP');
  if (!price) missing.push('asking price');

  return {
    listing_key: key,
    zpid: zpid,
    address: address,
    city: city,
    state: state,
    zip: zip,
    market_id: marketId,
    asking_price: price,
    original_price: price,
    price_change: 0,
    price_change_percent: 0,
    beds: lrNumber_(lrPick_(item, ['beds', 'bedrooms', 'hdpData.homeInfo.bedrooms'])),
    baths: lrNumber_(lrPick_(item, ['baths', 'bathrooms', 'hdpData.homeInfo.bathrooms'])),
    sqft: lrNumber_(lrPick_(item, ['sqft', 'livingArea', 'int_size', 'hdpData.homeInfo.livingArea'])),
    lot_size: lrText_(lrPick_(item, ['lot_size', 'lotSize', 'lotAreaString', 'lotAreaValue'])),
    year_built: lrNumber_(lrPick_(item, ['year_built', 'yearBuilt', 'hdpData.homeInfo.yearBuilt'])),
    property_type: lrText_(lrPick_(item, ['property_type', 'propertyType', 'homeType'])),
    days_on_market: lrNumber_(lrPick_(item, ['days_on_market', 'daysOnZillow', 'daysOnMarket'])),
    listing_status: lrText_(lrPick_(item, ['listing_status', 'status', 'homeStatus'])) || 'Active',
    listing_url: url,
    primary_photo: lrPrimaryPhoto_(item),
    agent_name: lrText_(lrPick_(item, ['agent_name', 'agentName', 'listingAgent.name', 'attributionInfo.agentName'])),
    agent_email: email,
    agent_phone: phone,
    agent_brokerage: lrText_(lrPick_(item, ['agent_brokerage', 'brokerageName', 'brokerName', 'attributionInfo.brokerName'])),
    contact_source: email || phone ? 'Zillow' : 'Missing',
    contact_verified_at: '',
    first_seen: observedAt,
    last_seen: observedAt,
    last_run_id: runId,
    feed_status: 'NEW',
    data_quality: missing.length ? 'Missing: ' + missing.join(', ') : 'Complete',
    source: 'Apify Zillow'
  };
}

function lrMergeListing_(existing, incoming, observedAt) {
  const result = Object.assign({}, existing);
  const events = [];
  let changed = false;
  let priceChanged = false;
  const oldPrice = lrNumber_(existing.asking_price);
  const newPrice = lrNumber_(incoming.asking_price);
  result.last_seen = observedAt;
  result.last_run_id = incoming.last_run_id;
  result.market_id = incoming.market_id || existing.market_id;
  result.feed_status = 'UNCHANGED';

  if (newPrice && newPrice !== oldPrice) {
    result.asking_price = newPrice;
    result.original_price = lrNumber_(existing.original_price) || oldPrice || newPrice;
    result.price_change = oldPrice ? newPrice - oldPrice : 0;
    result.price_change_percent = oldPrice ? ((newPrice - oldPrice) / oldPrice) * 100 : 0;
    result.feed_status = oldPrice && newPrice < oldPrice ? 'PRICE_DROP' : 'PRICE_INCREASE';
    events.push(lrEvent_(incoming, result.feed_status, 'asking_price', oldPrice, newPrice, observedAt));
    changed = true;
    priceChanged = true;
  }

  LR.HEADERS.CURRENT.forEach(function(field) {
    if (['listing_key', 'first_seen', 'last_seen', 'asking_price', 'original_price', 'price_change', 'price_change_percent', 'feed_status'].indexOf(field) !== -1) return;
    const value = incoming[field];
    if (value === '' || value === null || value === undefined || value === existing[field]) return;
    const oldValue = existing[field];
    result[field] = value;
    changed = true;
    if (['listing_status', 'listing_url', 'agent_name', 'agent_phone', 'agent_email', 'agent_brokerage'].indexOf(field) !== -1) {
      events.push(lrEvent_(incoming, 'FIELD_CHANGED', field, oldValue, value, observedAt));
      if (result.feed_status === 'UNCHANGED') result.feed_status = 'UPDATED';
    }
  });
  return {record: result, events: events, changed: changed, priceChanged: priceChanged};
}

function lrEvent_(listing, type, field, oldValue, newValue, observedAt) {
  return {
    event_id: lrDigest_(listing.listing_key + '|' + type + '|' + field + '|' + observedAt),
    listing_key: listing.listing_key,
    event_type: type,
    field_name: field,
    old_value: oldValue,
    new_value: newValue,
    market_id: listing.market_id,
    run_id: listing.last_run_id,
    observed_at: observedAt,
    source: listing.source
  };
}

function lrHistoryRow_(listing, type, field, oldValue, newValue, observedAt) {
  return lrObjectRow_(LR.HEADERS.HISTORY, lrEvent_(listing, type, field, oldValue, newValue, observedAt));
}

function lrExistingFirstColumnKeys_(sheet) {
  const keys = new Set();
  if (sheet.getLastRow() < 2) return keys;
  sheet.getRange(2, 1, sheet.getLastRow() - 1, 1).getValues().forEach(function(row) {
    const key = String(row[0] || '').trim();
    if (key) keys.add(key);
  });
  return keys;
}

function lrListingKey_(zpid, address, zip, url) {
  if (zpid) return 'zpid:' + zpid;
  if (address && zip) return 'address:' + lrDigest_(lrNormalizeAddress_(address) + '|' + zip).slice(0, 20);
  if (url) return 'url:' + lrDigest_(String(url).toLowerCase()).slice(0, 20);
  return '';
}

function lrNormalizeAddress_(value) {
  return lrText_(value).toLowerCase().replace(/[^a-z0-9 ]+/g, ' ').replace(/\s+/g, ' ').trim();
}

function lrPrimaryPhoto_(item) {
  let value = lrPick_(item, ['primary_photo', 'photo_main', 'imgSrc', 'hdpData.homeInfo.imgSrc']);
  if (value) return lrUrl_(value);
  value = lrPick_(item, ['photos', 'photo_all', 'images', 'carouselPhotos']);
  if (Array.isArray(value) && value.length) {
    let first = value[0];
    if (typeof first === 'object') first = lrPick_(first, ['url', 'imageUrl', 'imgSrc', 'mixedSources.jpeg.0.url']);
    return lrUrl_(first);
  }
  if (typeof value === 'string') return lrUrl_(value.split(/[|\n]/)[0]);
  return '';
}

function lrPick_(obj, paths) {
  for (let index = 0; index < paths.length; index++) {
    const parts = paths[index].split('.');
    let current = obj;
    for (let part = 0; part < parts.length; part++) {
      if (current === null || current === undefined || typeof current !== 'object') {
        current = '';
        break;
      }
      current = current[parts[part]];
    }
    if (current !== '' && current !== null && current !== undefined) return current;
  }
  return '';
}

function lrRowObject_(headers, row) {
  const result = {};
  headers.forEach(function(header, index) { result[header] = row[index]; });
  return result;
}

function lrObjectRow_(headers, object) {
  return headers.map(function(header) { return object[header] === undefined ? '' : object[header]; });
}

function lrText_(value) { return String(value === null || value === undefined ? '' : value).replace(/\s+/g, ' ').trim(); }
function lrDigits_(value) { return lrText_(value).replace(/\D/g, ''); }
function lrNumber_(value) {
  const number = Number(String(value === null || value === undefined ? '' : value).replace(/[^0-9.\-]/g, ''));
  return isNaN(number) ? 0 : number;
}
function lrPhone_(value) {
  let digits = lrDigits_(value);
  if (digits.length === 11 && digits.charAt(0) === '1') digits = digits.slice(1);
  return digits.length === 10 ? digits : '';
}
function lrUrl_(value) {
  let text = lrText_(value);
  if (text.indexOf('//') === 0) text = 'https:' + text;
  if (text.indexOf('s://') === 0) text = 'http' + text;
  if (text.indexOf('www.') === 0) text = 'https://' + text;
  return text;
}
function lrDigest_(value) {
  const bytes = Utilities.computeDigest(Utilities.DigestAlgorithm.SHA_256, String(value));
  return bytes.map(function(byte) { const item = (byte < 0 ? byte + 256 : byte).toString(16); return item.length === 1 ? '0' + item : item; }).join('').slice(0, 32);
}
