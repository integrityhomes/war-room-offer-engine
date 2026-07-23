const LR = Object.freeze({
  SHEETS: {
    MARKETS: 'MARKETS',
    CURRENT: 'LISTINGS_CURRENT',
    HISTORY: 'LISTING_HISTORY',
    QUEUE: 'TEAM_QUEUE',
    RUNS: 'RUN_LOG',
    QUARANTINE: 'QUARANTINE',
    SETUP: 'LISTING_RADAR_SETUP'
  },
  HEADERS: {
    MARKETS: [
      'market_id', 'market_name', 'state', 'zip_codes', 'min_price', 'max_price',
      'max_days_on_market', 'enabled', 'rollout_wave', 'apify_task_id',
      'schedule_label', 'buy_box_notes', 'updated_at'
    ],
    CURRENT: [
      'listing_key', 'zpid', 'address', 'city', 'state', 'zip', 'market_id',
      'asking_price', 'original_price', 'price_change', 'price_change_percent',
      'beds', 'baths', 'sqft', 'lot_size', 'year_built', 'property_type',
      'days_on_market', 'listing_status', 'listing_url', 'primary_photo',
      'agent_name', 'agent_email', 'agent_phone', 'agent_brokerage',
      'contact_source', 'contact_verified_at', 'first_seen', 'last_seen',
      'last_run_id', 'feed_status', 'data_quality', 'source'
    ],
    HISTORY: [
      'event_id', 'listing_key', 'event_type', 'field_name', 'old_value',
      'new_value', 'market_id', 'run_id', 'observed_at', 'source'
    ],
    QUEUE: [
      'listing_key', 'assigned_to', 'workflow_status', 'last_contact_at',
      'next_follow_up', 'agent_response', 'team_notes', 'dismiss_reason',
      'deal_id', 'updated_by', 'updated_at'
    ],
    RUNS: [
      'run_id', 'market_id', 'apify_task_id', 'dataset_id', 'started_at',
      'finished_at', 'status', 'items_received', 'new_listings',
      'updated_listings', 'price_changes', 'duplicates', 'quarantined',
      'cost_usd', 'error', 'processed_at'
    ],
    QUARANTINE: [
      'quarantine_id', 'run_id', 'market_id', 'reason', 'raw_record_json',
      'observed_at'
    ],
    SETUP: ['setting', 'value', 'instructions']
  }
});

const LR_ILLINOIS_ZIPS = [
  '62521', '62522', '62526', '62523', '62534', '62535', '62550',
  '62551', '62554', '62555', '62557', '62563', '62701', '62702',
  '62703', '62704', '62707', '62711', '61820', '61821', '61822',
  '61801', '61802', '61701', '61704', '61761', '61764'
];

function setupListingRadarV2() {
  const spreadsheet = SpreadsheetApp.getActiveSpreadsheet();
  if (!spreadsheet) {
    throw new Error('Open the new Listing Radar Google Sheet before running setupListingRadarV2.');
  }

  const properties = PropertiesService.getScriptProperties();
  properties.setProperty('LISTING_RADAR_SPREADSHEET_ID', spreadsheet.getId());

  let appToken = properties.getProperty('LISTING_RADAR_TOKEN');
  if (!appToken) {
    appToken = lrGenerateToken_();
    properties.setProperty('LISTING_RADAR_TOKEN', appToken);
  }

  let webhookSecret = properties.getProperty('LISTING_RADAR_WEBHOOK_SECRET');
  if (!webhookSecret) {
    webhookSecret = lrGenerateToken_();
    properties.setProperty('LISTING_RADAR_WEBHOOK_SECRET', webhookSecret);
  }

  const sheets = lrEnsureAllSheets_(spreadsheet);
  Object.keys(sheets).forEach(function(key) {
    lrFormatSheet_(sheets[key]);
  });
  lrSeedMarkets_(sheets.MARKETS);
  lrWriteSetupSheet_(sheets.SETUP, spreadsheet, appToken, webhookSecret);

  return {
    ok: true,
    spreadsheet_id: spreadsheet.getId(),
    listing_radar_token: appToken,
    webhook_secret: webhookSecret,
    sheets: Object.keys(sheets)
  };
}

function lrGenerateToken_() {
  return Utilities.getUuid().replace(/-/g, '') + Utilities.getUuid().replace(/-/g, '');
}

function lrSpreadsheet_() {
  const id = PropertiesService.getScriptProperties().getProperty('LISTING_RADAR_SPREADSHEET_ID');
  if (!id) throw new Error('Listing Radar is not initialized. Run setupListingRadarV2 first.');
  return SpreadsheetApp.openById(id);
}

function lrEnsureAllSheets_(spreadsheet) {
  return {
    MARKETS: lrEnsureSheet_(spreadsheet, LR.SHEETS.MARKETS, LR.HEADERS.MARKETS),
    CURRENT: lrEnsureSheet_(spreadsheet, LR.SHEETS.CURRENT, LR.HEADERS.CURRENT),
    HISTORY: lrEnsureSheet_(spreadsheet, LR.SHEETS.HISTORY, LR.HEADERS.HISTORY),
    QUEUE: lrEnsureSheet_(spreadsheet, LR.SHEETS.QUEUE, LR.HEADERS.QUEUE),
    RUNS: lrEnsureSheet_(spreadsheet, LR.SHEETS.RUNS, LR.HEADERS.RUNS),
    QUARANTINE: lrEnsureSheet_(spreadsheet, LR.SHEETS.QUARANTINE, LR.HEADERS.QUARANTINE),
    SETUP: lrEnsureSheet_(spreadsheet, LR.SHEETS.SETUP, LR.HEADERS.SETUP)
  };
}

function lrEnsureSheet_(spreadsheet, name, headers) {
  let sheet = spreadsheet.getSheetByName(name);
  if (!sheet) sheet = spreadsheet.insertSheet(name);
  const current = sheet.getLastColumn() > 0
    ? sheet.getRange(1, 1, 1, sheet.getLastColumn()).getValues()[0]
    : [];
  headers.forEach(function(header, index) {
    if (current[index] !== header) sheet.getRange(1, index + 1).setValue(header);
  });
  return sheet;
}

function lrFormatSheet_(sheet) {
  sheet.setFrozenRows(1);
  if (sheet.getLastColumn() > 0) {
    sheet.getRange(1, 1, 1, sheet.getLastColumn()).setFontWeight('bold');
    sheet.autoResizeColumns(1, Math.min(sheet.getLastColumn(), 12));
  }
}

function lrSeedMarkets_(sheet) {
  if (sheet.getLastRow() > 1) return;
  const now = new Date().toISOString();
  const seeds = [
    ['IL_CENTRAL_TARGET_ZIPS', 'Central Illinois — Current Target ZIPs', 'IL', LR_ILLINOIS_ZIPS.join(','), 20000, 75000, 14, false, 1, '', 'Twice daily', 'Mirror existing Illinois task; no cutover until 14 scheduled runs pass.', now],
    ['MO_STL_VALUE_RING', 'St. Louis Value Ring', 'MO', '', 15000, 90000, 30, false, 2, '', 'Research', 'Seed cities: Dellwood, Moline Acres, Calverton Park, Flordell Hills and Riverview. Exclude Jennings unless separately approved.', now],
    ['IN_VALUE_MARKETS', 'Indiana Value Markets', 'IN', '', 15000, 90000, 30, false, 2, '', 'Research', 'Select ZIPs after price, rent, tax, inventory and buyer-demand scoring.', now],
    ['MI_TOLEDO_CORRIDOR', 'Southeast Michigan / Toledo Corridor', 'MI', '', 15000, 100000, 30, false, 2, '', 'Research', 'Research Monroe-area and nearby Michigan ZIPs. Ohio ZIPs stay in Ohio market groups.', now],
    ['OH_CLEVELAND_VALUE', 'Cleveland Value Markets', 'OH', '', 15000, 100000, 30, false, 3, '', 'Research', 'Validate block-level demand, taxes, violations, title and exit liquidity.', now],
    ['OH_DAYTON_MANSFIELD', 'Dayton / Mansfield Value Markets', 'OH', '', 15000, 100000, 30, false, 3, '', 'Research', 'Separate market groups after current listing and rent-support validation.', now],
    ['AL_VALUE_MARKETS', 'Alabama Value Markets', 'AL', '', 15000, 100000, 30, false, 3, '', 'Research', 'Select ZIPs using inventory, rent-to-price, taxes, insurance, title and buyer demand.', now],
    ['VA_SOUTHSIDE_VALUE', 'Southside Virginia Value Markets', 'VA', '', 20000, 125000, 45, false, 3, '', 'Research', 'Seed Franklin, Courtland, Wakefield and Southampton County; verify well, septic, crawlspace and rural rent support.', now],
    ['TX_VALUE_MARKETS', 'Texas Value Markets — Research Queue', 'TX', '', 25000, 125000, 45, false, 4, '', 'Research', 'Do not enable statewide. Rank ZIPs by supply, rent-to-price, taxes, insurance, title friction and buyer liquidity.', now]
  ];
  sheet.getRange(2, 1, seeds.length, LR.HEADERS.MARKETS.length).setValues(seeds);
}

function lrWriteSetupSheet_(sheet, spreadsheet, appToken, webhookSecret) {
  sheet.clearContents();
  sheet.getRange(1, 1, 1, 3).setValues([LR.HEADERS.SETUP]);
  const rows = [
    ['Spreadsheet ID', spreadsheet.getId(), 'Created automatically.'],
    ['LISTING_RADAR_TOKEN', appToken, 'Copy into Streamlit secrets after the separate web app is deployed.'],
    ['LISTING_RADAR_WEBHOOK_SECRET', webhookSecret, 'Use in the Apify webhook payload. Never place it in source code.'],
    ['APIFY_TOKEN', 'Add in Apps Script project settings', 'Create a dedicated token named Listing Radar Feed. Do not paste it into a sheet cell.'],
    ['Deployment URL', 'Add after deployment', 'Deploy this separate project as a web app and copy the /exec URL.'],
    ['Mode', 'Mirror only', 'Current Illinois automation remains production until the V2 mirror passes 14 scheduled runs.']
  ];
  sheet.getRange(2, 1, rows.length, 3).setValues(rows);
  lrFormatSheet_(sheet);
}
