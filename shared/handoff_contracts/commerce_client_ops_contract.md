# Commerce <> Client Ops Handoff Contract

Contract version: `2026-05-21.v1`

This is the canonical shared contract for handoffs between:

- `teams/commerce-agent-team`
- `teams/client-ops-team`

Team-local files may explain role-specific usage, but this root document is the source of truth.

## Common Envelope

Every handoff MUST use this envelope.

```json
{
  "contract_version": "2026-05-21.v1",
  "handoff_id": "COPS-COM-2026-W21-001",
  "direction": "client_ops_to_commerce",
  "from_team": "client-ops-team",
  "to_team": "commerce-agent-team",
  "created_at": "2026-05-21T19:30:00+09:00",
  "week": "2026-W21",
  "source_agent": "04_data_analyst",
  "signal_type": "demand_signal",
  "summary": "Short public-safe summary",
  "confidence": "medium",
  "requires_human_approval": true,
  "dry_run_only": true,
  "pii_check": {
    "names_removed": true,
    "contacts_removed": true,
    "business_ids_removed": true,
    "raw_messages_removed": true,
    "amounts_indexed": true,
    "medical_legal_tax_only_as_category": true
  },
  "review": {
    "owner": "05_coordinator_qa",
    "decision": "PASS",
    "decision_reason": "PII removed and sample size is sufficient."
  },
  "payload": {}
}
```

## Client Ops -> Commerce

Allowed `signal_type` values:

```text
operational_performance
catalog_usage
demand_signal
complaint_patterns
channel_trends
```

Commerce does not ingest these directly as product candidates. It first receives them as anonymized signals, then routes them to the right commerce agent.

| Signal Type | Commerce Route | Fit | Processing Rule |
| --- | --- | --- | --- |
| `operational_performance` | `02_margin_analyst`, `05_ops_manager` | Partial | Use as prioritization context only. Do not treat as product demand unless paired with a product/category request. |
| `catalog_usage` | `04_listing_builder`, `02_margin_analyst` | Partial | Use to improve listing/package assumptions or flag weak catalog fit. |
| `demand_signal` | `01_market_scout` | Strong | Convert into product/category discovery task. |
| `complaint_patterns` | `03_risk_guardian`, `04_listing_builder` | Strong | Convert into risk exclusions, FAQ requirements, and copy guardrails. |
| `channel_trends` | `01_market_scout`, `04_listing_builder` | Partial | Use as channel/context signal. Do not claim causal revenue impact. |

### Client Ops -> Commerce Required Payloads

#### `operational_performance`

```json
{
  "industry": "clinic",
  "region": "Seoul",
  "time_window": "2026-W21",
  "sample_size_cases": 8,
  "metrics": [
    {
      "metric_name": "noshow_rate",
      "value_indexed": 0.92,
      "baseline_period": "2026-W17..W20",
      "direction": "down",
      "interpretation": "No-show rate appears lower than baseline."
    }
  ],
  "derived_commerce_request": {
    "request_type": "product_discovery",
    "category_hint": "appointment reminder automation",
    "target_market": "coupang",
    "why_commerce_should_care": "May indicate demand for reminder tools or service packages."
  }
}
```

`derived_commerce_request` is required because raw operations KPIs are not commerce product candidates.

#### `catalog_usage`

```json
{
  "catalog_or_category": "review request templates",
  "target_market": "client_ops_service_catalog",
  "time_window": "2026-W21",
  "sample_size_cases": 7,
  "usage_indexed": 1.23,
  "dropoff_or_reject_reasons": ["unclear benefit", "timing mismatch"],
  "requested_commerce_action": "listing_copy_review"
}
```

#### `demand_signal`

```json
{
  "industry": "pet grooming",
  "region": "Seoul",
  "time_window": "2026-W21",
  "sample_size_cases": 9,
  "keyword_or_intent": "pet hair cleanup after grooming",
  "category_hint": "pet supplies",
  "target_market": "coupang",
  "demand_index": 1.31,
  "evidence_summary": "Anonymized weekly request volume increased against baseline.",
  "exclusion_terms": ["medical claim", "brand name"]
}
```

#### `complaint_patterns`

```json
{
  "industry": "home office",
  "region": "Korea",
  "time_window": "2026-W21",
  "sample_size_cases": 6,
  "complaint_category": "adhesive failure",
  "severity": "medium",
  "affected_stage": "post_purchase",
  "commerce_action": "risk_exclusion",
  "recommended_guardrails": ["avoid overclaiming durability", "require real sample test"]
}
```

#### `channel_trends`

```json
{
  "channel": "short-form video",
  "audience_segment": "small business owners",
  "time_window": "2026-W21",
  "sample_size_cases": 10,
  "trend_type": "content_format",
  "trend_index": 1.18,
  "content_or_offer_hint": "before/after workflow demo",
  "commerce_action": "listing_angle_research"
}
```

## Commerce -> Client Ops

Allowed `signal_type` values:

```text
new_automation_candidate
market_trend
tool_change_alert
rejected_for_info
collaboration_request
```

| Signal Type | Client Ops Route | Fit | Processing Rule |
| --- | --- | --- | --- |
| `new_automation_candidate` | `02_ops_operator`, `01_onboarding_manager` | Good | Must be dry-run until Adam or QA approves customer-facing use. |
| `market_trend` | `04_data_analyst`, `03_cs_manager` | Good | Use as weak signal for internal reporting or talking points only. |
| `tool_change_alert` | `05_coordinator_qa`, `02_ops_operator` | Partial | Commerce is not the authoritative source. Must include evidence URL/source and verification status. |
| `rejected_for_info` | Original requester, `05_coordinator_qa` | Strong | Use when commerce cannot act due to missing data or risk. |
| `collaboration_request` | Target agent(s), `05_coordinator_qa` | Strong | Use for scoped cross-team work. |

### Commerce -> Client Ops Required Payloads

#### `new_automation_candidate`

```json
{
  "automation_name": "review request timing A/B dry-run",
  "trigger": "purchase_complete_plus_24h",
  "expected_outcome": "increase review request reply rate",
  "evidence_ref": "teams/commerce-agent-team/reports/latest_agent_run.md",
  "target_client_ops_route": ["02_ops_operator", "01_onboarding_manager"],
  "requires_human_approval": true,
  "dry_run_only": true,
  "forbidden_claims": ["guaranteed revenue", "guaranteed reviews"]
}
```

#### `market_trend`

```json
{
  "trend_name": "low-risk desk organization bundles",
  "category": "office supplies",
  "target_market": "coupang",
  "confidence": "medium",
  "evidence_ref": "RUN-20260521-191159",
  "client_ops_use": ["weekly_report_insight", "onboarding_note"],
  "forbidden_claims": ["guaranteed demand", "guaranteed conversion"]
}
```

#### `tool_change_alert`

```json
{
  "tool_or_platform": "coupang",
  "change_type": "policy_or_api_change",
  "effective_date": "2026-06-01",
  "source_url": "https://example.com/source",
  "verification_status": "needs_human_verification",
  "risk_level": "medium",
  "recommended_action": "QA review before changing any workflow"
}
```

#### `rejected_for_info`

```json
{
  "request_id": "COPS-COM-2026-W21-001",
  "rejection_reason": "Missing target market and sample size.",
  "missing_fields": ["payload.target_market", "payload.sample_size_cases"],
  "next_action_owner": "04_data_analyst",
  "can_resubmit": true
}
```

#### `collaboration_request`

```json
{
  "objective": "Validate whether complaint pattern should become a product exclusion rule.",
  "requested_team": "client-ops-team",
  "requested_agents": ["03_cs_manager", "05_coordinator_qa"],
  "due": "2026-05-28T18:00:00+09:00",
  "deliverables": ["masked complaint category table", "QA decision"],
  "context_ref": "RUN-20260521-191159"
}
```

## Shared Rejection Conditions

Reject or return `rejected_for_info` when:

- any `pii_check` field is false
- `sample_size_cases` is below 5 for client-derived signals
- raw customer messages are included
- absolute customer revenue, phone numbers, emails, IDs, medical, legal, tax, or payment data are included
- `review.decision` is not `PASS`
- customer-facing action is requested without `requires_human_approval=true`
- `tool_change_alert` lacks source or verification status

## Current Commerce Receiver

Commerce currently supports safe file-based receiving through:

```bash
python teams/commerce-agent-team/scripts/import_client_ops_handoff.py path/to/handoff.json --dry-run
```

Accepted handoffs are written under ignored runtime storage:

```text
teams/commerce-agent-team/runtime/client_ops_handoffs/
```

They are not automatically converted into product candidates. A commerce agent or script must explicitly turn the signal into a scout/risk/listing task.
