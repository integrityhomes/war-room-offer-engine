# War Room Stability-First Release Plan

The app is now in a **stability-first feature freeze**. New features should wait until the current property-analysis workflow is predictable for every teammate.

## Product goal

One simple workflow should reliably answer:

1. Who is working the offer?
2. What exact property and price are being analyzed?
3. What evidence was successfully loaded?
4. Is the selected deal lane supported by that evidence?
5. What is the safe offer range and next action?
6. Was the complete result saved for the team?

The default screen should remain simple. Detailed tools stay available in their individual workspaces and the collapsed advanced section.

## Phase 1 — Production state safety and simple readiness

This phase is implemented in the current stability PR.

- Remove realistic-looking demo values from genuinely blank production sessions.
- Require teammate identity, complete property location, and a real price before analysis.
- Clear all property-specific evidence immediately when a different property is entered.
- Preserve global settings and the current teammate while clearing the prior property.
- Start forced paid refreshes from clean evidence so old comps cannot masquerade as new results.
- Mark each loaded analysis with the property it belongs to.
- Preserve the correct property marker when a Team Deal Library snapshot is restored.
- Add a compact four-item readiness/status card.
- Collapse negotiation and technical sections by default.
- Catch unexpected analysis errors and stop safely without retaining a BUY decision.
- Extend Start New Property so all modern RentCast, ARV, repair, location, and audit aliases are cleared.

### Phase 1 acceptance test

Use two properties in the same browser session:

1. Complete a verified analysis for Property A.
2. Type Property B without pressing Pull.
3. Confirm Property A's rent, ARV, repairs, contacts, negotiation, and decision disappear immediately.
4. Confirm the selected teammate remains.
5. Confirm Pull is disabled until Property B has a complete location and price.
6. Run Property B once and confirm every Rent and ARV row belongs to Property B's geography.
7. Force one refresh and confirm old evidence is not reused when the provider returns an error.
8. Open a saved deal and confirm its evidence is restored without replacing the current teammate.

## Phase 2 — Consolidate the runtime architecture

Begin only after Phase 1 passes live testing.

- Inventory every monkey patch and wrapper in startup order.
- Replace overlapping wrappers with one explicit application bootstrap.
- Establish one canonical property state model and one canonical evidence model.
- Remove legacy aliases only after saved-deal migration coverage exists.
- Make provider responses flow through one typed normalization boundary.
- Keep Basic and Verified intelligence paths explicit, testable, and impossible to mix.

## Phase 3 — End-to-end release testing

- Add browser tests for a local urban property, suburban property, small-town property, and remote property.
- Test plain addresses and listing URLs.
- Test successful provider responses, empty responses, timeouts, credit-limit blocks, and wrong-location responses.
- Test two teammates updating the same saved deal.
- Test app reboot and Team Deal Library restore without another paid pull.
- Publish a release checklist and require it before every merge to `main`.

## Stability rules during the freeze

- No new provider, strategy, or major screen until the current release checklist passes.
- One problem per PR whenever practical.
- Every production bug gets a deterministic regression test.
- No BUY may survive a property mismatch, missing real price, failed location verification, or stale prior-property evidence.
- No realistic demo number may appear as verified property data.
- Paid pulls must remain explicit, counted, capped, and reusable through the Team Deal Library.
- The simple default workflow must stay usable without opening advanced controls.
