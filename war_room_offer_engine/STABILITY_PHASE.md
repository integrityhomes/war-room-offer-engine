# War Room Stability Phase

The application is in an accuracy-and-reliability phase. New feature work should wait until the current workflow passes the release checklist below.

## Product rule

One teammate, one property identity, one verified data mode, one current analysis, and one saved team record.

The normal operator workflow is:

1. Select the current team member.
2. Enter a complete address or a listing link.
3. Enter asking and negotiated prices.
4. Run **Pull Everything & Tell Me** once.
5. Review Rent, Recorded Sale Intelligence, and the final decision.
6. Save the verified result to the Team Deal Library.
7. Reopen saved data without repurchasing it; force refresh only when the evidence is outdated.

## Stability guarantees

- Prototype/demo values are not accepted as property evidence.
- A prior property's decision is hidden as soon as the property input changes.
- Starting a different property clears prior rent, ARV, comp, location, repair, seller, decision, request, and Deal Library state.
- **Start New Property** preserves the current teammate but clears the prior deal.
- Verified RentCast intelligence is the standard accuracy-first mode.
- A complete analysis is reported only when usable property evidence exists and the subject location did not fail verification.
- Wrong-property, incomplete-location, weak-evidence, and missing-evidence cases cannot become a clean BUY.
- Paid refresh remains an advanced, intentional action.

## Release checklist

A release is stable only when all of these pass:

- Fresh browser session shows no fake asking price, rent, beds, baths, or square footage.
- Teammate identity is required before an offer calculation.
- Street-only address is blocked before paid requests.
- Complete address resolves to the exact house, city, state, and ZIP.
- Plain-address and listing-link pulls both populate the same normalized evidence contract.
- Rent screen counts, selected rows, confidence, and warnings agree.
- Recorded-sale ARV uses verified sale price/date evidence and condition warnings.
- Final lane confidence uses only evidence relevant to that lane.
- Changing the property hides the old decision immediately.
- Start New Property leaves no prior-property facts or comps behind.
- Saved deal reopens without paid requests.
- Forced refresh requires explicit confirmation and remains within the displayed hard cap.
- Team Deal Library keeps Offer Made By, Updated By, and Assigned To separate.
- The hosted core regression suite passes on the exact merge head.

## Change policy during stabilization

- Prefer small, reversible pull requests.
- Do not change offer economics while fixing state, data, routing, or UI reliability.
- Add a regression for every live defect before merging its correction.
- Do not merge an older superseded branch into `main`.
- Do not add a new provider or major workflow until the checklist is repeatedly clean on real urban, suburban, small-town, and rural properties.
