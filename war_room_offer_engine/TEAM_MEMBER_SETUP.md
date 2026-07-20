# Team member and offer identity setup

The War Room now requires the teammate working an offer to identify themselves before **Pull Everything & Tell Me** can calculate or generate outreach.

## Immediate use

No configuration is required. Choose **Other / enter a name** in the **Team Member & Offer Identity** box and type your name. The selection stays active for the current browser session and follows that teammate across properties until they change it or the Streamlit session restarts.

## Shared team dropdown

For a consistent dropdown for the full acquisitions team, add a TOML list to the Streamlit app secrets:

```toml
TEAM_MEMBER_NAMES = [
  "Team Member 1",
  "Team Member 2",
  "Team Member 3",
  "Team Member 4",
  "Team Member 5",
  "Team Member 6",
  "Team Member 7",
  "Team Member 8",
  "Team Member 9",
]
```

Replace the placeholders with the actual nine team-member names. The app also accepts the aliases `OFFER_TEAM_MEMBERS` or `ACQUISITIONS_TEAM_MEMBERS`.

## How the identity is used

- Realtor text messages, emails, and follow-ups use the selected teammate's name.
- No message defaults to the owner or another teammate.
- The selected teammate is recorded as **Updated By** for each Team Deal Library version.
- The teammate who starts a new analysis is recorded as **Offer Made By** in the saved deal snapshot and audit details.
- Opening another teammate's saved deal does not change the current browser-session identity.
- **Start New Property** clears the prior deal's offer maker but keeps the current teammate selected.
- A teammate can still use **Other / enter a name** when they are not present in the configured roster.
