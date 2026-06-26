# War Room Offer Engine

Manual-first Streamlit MVP for analyzing wholesale and slow flip deals.

## What it does

- Calculates wholesale offer range
- Calculates slow flip offer range
- Chooses best exit
- Grades the deal
- Shows risk notes
- Drafts a seller/agent message
- Optional OpenAI summary if `OPENAI_API_KEY` is added

## Run locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Streamlit Cloud setup

1. Upload these files to a GitHub repo.
2. Deploy from Streamlit Cloud.
3. Main file path: `app.py`.
4. Optional secret:

```toml
OPENAI_API_KEY = "your_key_here"
```

## Next build phases

1. Connect Google Sheets lead data.
2. Connect RentCast rent values.
3. Connect Apify Zillow output.
4. Save every analysis back to Google Sheets.
5. Add offer approval workflow.
