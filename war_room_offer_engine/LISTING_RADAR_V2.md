# War Room Listing Radar V2

## Decision

Rebuild the listing-feed layer beside the current AI Deal Feed Engine. Do not patch the existing RAW_FEED → MASTER_FEED → RentCast → spreadsheet offer-math chain into the War Room.

The current Illinois automation remains production until the V2 mirror completes at least 14 consecutive scheduled runs without missing listings, duplicating records, losing team work, or exposing credentials.

## One source of truth per responsibility

- **Apify tasks** find public on-market listings.
- **Listing Radar V2** stores current listing facts, listing history, run health and team workflow.
- **War Room Deal Engine** is the only authority for rent confidence, ARV confidence, repairs, lane selection, starting offer, maximum offer and BUY / REVIEW / PASS.
- **Team Deal Library** stores properties the team has chosen to analyze or pursue.
- **REI BlackBook** receives hot leads and handles the CRM/follow-up work it already performs.
- **XLeads** remains an outbound campaign and follow-up tool; it is not the listing database.

## V2 Google Sheet

A new, separate Google Sheet is created from the three files in `setup/google_apps_script/`:

- `ListingRadarV2_Setup.gs`
- `ListingRadarV2_Ingest.gs`
- `ListingRadarV2_WebApp.gs`

The setup creates:

1. `MARKETS`
2. `LISTINGS_CURRENT`
3. `LISTING_HISTORY`
4. `TEAM_QUEUE`
5. `RUN_LOG`
6. `QUARANTINE`
7. `LISTING_RADAR_SETUP`

The spreadsheet is a controlled backend and audit record. The acquisitions team works from the Listing Radar screen inside the War Room rather than horizontally scrolling through a large calculation sheet.

## Listing identity and history

Primary key:

1. Zillow ZPID
2. normalized address + ZIP
3. canonical listing URL

Repeated runs are idempotent. A repeated dataset cannot create duplicate current listings. A changed price or status creates a history event while retaining the original `first_seen` date.

Rows missing listing identity, address, ZIP or asking price are placed in `QUARANTINE`. They do not silently enter the team queue.

## Credential separation

Use three separate credentials:

- `War Room Offer Engine` Apify token for teammate-triggered single-property pulls
- `Listing Radar Feed` Apify token for scheduled multi-market feeds
- `LISTING_RADAR_TOKEN` for Streamlit ↔ Listing Radar web-app requests

All credentials belong in Streamlit secrets or Apps Script Script Properties. Never place them in source code, URLs, spreadsheet cells, screenshots or chat.

Apify dataset requests use `Authorization: Bearer` instead of token-bearing URLs.

## Market rollout

Only the existing 27 Central Illinois ZIP codes are known production inputs. They are seeded as disabled mirror configuration.

Other markets are seeded as disabled research candidates:

- St. Louis value ring
- Indiana value markets
- Southeast Michigan / Toledo corridor
- Cleveland value markets
- Dayton / Mansfield value markets
- Alabama value markets
- Southside Virginia value markets
- Texas value-market research queue

No candidate market is enabled until ZIP-level validation covers:

- current listing supply
- asking-price distribution
- rent-to-price support
- annual taxes
- insurance exposure
- title and closing friction
- local violations / municipal risk where material
- wholesale buyer liquidity
- slow-flip payment support
- duplicate and data-quality rates

Texas must not be enabled statewide. Candidate ZIP groups are ranked and tested in small waves.

## Rollout gates

### Phase 1 — Foundation

- canonical schemas
- market registry
- normalization and merge engine
- secure Apps Script setup and webhook ingestion
- read-only Listing Radar War Room section
- tests

No production connection or cutover.

### Phase 2 — Illinois mirror

- create separate Listing Radar V2 Google Sheet
- create dedicated `Listing Radar Feed` token
- create or clone an Illinois Apify task mapped to V2
- configure a success webhook
- run V1 and V2 side by side
- compare every scheduled result

### Phase 3 — Team workflow

- assignment
- contact status
- notes and follow-up
- agent-contact enrichment only for screened listings
- Analyze in Deal Engine handoff
- REI BlackBook handoff for qualified opportunities

### Phase 4 — Multi-market expansion

- enable validated market groups one wave at a time
- pin tested Actor builds
- set explicit result and cost caps
- alert on missed or failed runs
- require at least seven successful mirror runs for each new market before team use

### Phase 5 — Cutover and retirement

Retire the old AI Deal Feed Engine only after V2 has completed at least 14 clean Illinois scheduled runs and all team workflow checks pass. Preserve the old spreadsheet as a read-only archive.

## What V2 intentionally does not do

- It does not call RentCast for every scraped listing.
- It does not calculate offers in Google Sheets.
- It does not classify a property as wholesale or slow flip from asking price alone.
- It does not overwrite team notes during listing refreshes.
- It does not invent agent emails.
- It does not enable new states or ZIPs without validation.
- It does not replace the existing Illinois feed during Phase 1.
