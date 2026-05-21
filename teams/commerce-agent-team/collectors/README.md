# Data Collection Layer

This folder is the safe intake layer for product discovery data.

## Current workflow

1. Put manually researched or external-AI-generated CSV files in `data/manual_inbox/`.
2. Import them with:

```bash
python scripts/import_candidates.py data/manual_inbox/new_candidates.csv
```

3. Run the agent team:

```bash
python scripts/run_agents.py
```

## Required candidate fields

The importer accepts the same fields as `data/product_candidates.csv`. Missing numeric fields are filled with conservative defaults, but `product_name`, `source_market`, `target_market`, and `category` should be supplied.

## Future collector slots

- `coupang_search_collector.py`: use approved APIs or manual export, not aggressive scraping.
- `amazon_research_collector.py`: use compliant data sources and respect marketplace terms.
- `naver_trend_collector.py`: keyword trend enrichment.
- `supplier_quote_collector.py`: quote and MOQ tracking.

Keep this layer boring and auditable. The agents can be creative; the data intake should be clean.
