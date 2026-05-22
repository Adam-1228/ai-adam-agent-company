# Commerce <> Client Ops Handoff Contract

Contract version: `2026-05-22.v2.1`

This is the canonical shared contract for handoffs between:

- `teams/commerce-agent-team`
- `teams/client-ops-team`

Team-local files may explain role-specific usage, but this root document is the source of truth.

## Common Envelope

Every handoff MUST use this envelope.

```json
{
  "contract_version": "2026-05-22.v2.1",
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
seller_account_blocker
refund_or_claim_escalation
```

Commerce does not ingest these directly as product candidates. It first receives them as anonymized signals, then routes them to the right commerce agent.

| Signal Type | Commerce Route | Fit | Processing Rule |
| --- | --- | --- | --- |
| `operational_performance` | `02_margin_analyst`, `05_ops_manager` | Partial | Use as prioritization context only. Do not treat as product demand unless paired with a product/category request. |
| `catalog_usage` | `04_listing_builder`, `02_margin_analyst` | Partial | Use to improve listing/package assumptions or flag weak catalog fit. |
| `demand_signal` | `01_market_scout` | Strong | Convert into product/category discovery task. |
| `complaint_patterns` | `03_risk_guardian`, `04_listing_builder` | Strong | Convert into risk exclusions, FAQ requirements, and copy guardrails. |
| `channel_trends` | `01_market_scout`, `04_listing_builder` | Partial | Use as channel/context signal. Do not claim causal revenue impact. |
| `seller_account_blocker` | `05_ops_manager`, `03_risk_guardian` | Strong | Pause affected channel packages until the account, permission, legal, or category blocker is cleared. Never include actual secret/account values. |
| `refund_or_claim_escalation` | `03_risk_guardian`, `05_ops_manager` | Strong | Treat as a safety signal for SKU pause, listing correction, or permanent exclusion. Include only anonymized case IDs and category counts. |

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

#### `seller_account_blocker`

```json
{
  "channel": "coupang",
  "blocker_type": "permission_insufficient",
  "severity": "high",
  "missing_permission": "listing.write",
  "discovered_at": "2026-05-22T10:30:00+09:00",
  "affected_opportunity_ids": ["ADAM-OPP-0042"],
  "remediation_owner": "Adam",
  "estimated_remediation_hours": 24,
  "do_not_disclose": ["api_key_value", "vendor_id_value"]
}
```

`do_not_disclose` MUST contain field names only, never the actual API key, vendor ID, account number, or credential value.

#### `refund_or_claim_escalation`

```json
{
  "opportunity_id": "ADAM-OPP-0042",
  "channel": "coupang",
  "trigger_type": "refund_threshold_3_in_7d",
  "severity": "high",
  "claim_breakdown": {
    "size_mismatch": 2,
    "quality_complaint": 2,
    "shipping_damage": 1
  },
  "case_ids_anonymized": ["CASE-A1", "CASE-A2", "CASE-A3"],
  "raw_customer_messages_included": false,
  "recommended_commerce_action": "review_catalog_or_exclude",
  "qa_decision": "ESCALATE_TO_ADAM",
  "qa_owner": "05_coordinator_qa"
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
channel_submission_ready
post_publish_monitoring_request
```

| Signal Type | Client Ops Route | Fit | Processing Rule |
| --- | --- | --- | --- |
| `new_automation_candidate` | `02_ops_operator`, `01_onboarding_manager` | Good | Must be dry-run until Adam or QA approves customer-facing use. |
| `market_trend` | `04_data_analyst`, `03_cs_manager` | Good | Use as weak signal for internal reporting or talking points only. |
| `tool_change_alert` | `05_coordinator_qa`, `02_ops_operator` | Partial | Commerce is not the authoritative source. Must include evidence URL/source and verification status. |
| `rejected_for_info` | Original requester, `05_coordinator_qa` | Strong | Use when commerce cannot act due to missing data or risk. |
| `collaboration_request` | Target agent(s), `05_coordinator_qa` | Strong | Use for scoped cross-team work. |
| `channel_submission_ready` | `05_coordinator_qa` | Strong | Use when commerce has generated dry-run channel packages after stage 5. Client Ops may QA the package, but must not publish or contact channels. |
| `post_publish_monitoring_request` | `04_data_analyst`, `02_ops_operator`, `05_coordinator_qa` | Strong | Use only after Adam has approved go-live and the channel is actually live. Starts KPI and incident monitoring. |

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

#### `channel_submission_ready`

```json
{
  "run_id": "GROWTH-20260522-093000",
  "opportunity_id": "ADAM-OPP-0042",
  "package_paths": [
    "teams/commerce-agent-team/runtime/channel_submissions/pending/GROWTH-20260522-093000_ADAM-OPP-0042_coupang.json",
    "teams/commerce-agent-team/runtime/channel_submissions/pending/GROWTH-20260522-093000_ADAM-OPP-0042_amazon.json"
  ],
  "validation_status": "draft_validated_locally",
  "approval_status": "adam_approval_required",
  "submit_status": "not_submitted",
  "risk_review": {
    "blocked": false,
    "risk_level": "review_required",
    "hard_stops": []
  },
  "forbidden_claims_present": false,
  "supplier_evidence_present": true,
  "category_match_seller_scope": true,
  "seller_scope_status": "category_match"
}
```

`channel_submission_ready` is a QA handoff only. The generated channel packages must remain `not_submitted` until Adam explicitly approves go-live.

`seller_scope_status` lifecycle:

| Status | Meaning | Client Ops Importer Behavior |
| --- | --- | --- |
| `not_connected_yet` | Seller account/API is not connected yet. Category scope cannot be checked. | INFO. Hold only if other required evidence is missing. |
| `connected` | Seller account exists, but category matching has not been evaluated. | WARN until category match is checked. |
| `category_match` | Connected seller scope supports the candidate category. | PASS if other gates pass. |
| `category_mismatch` | Connected seller scope does not support the candidate category. | WARN or HOLD; do not go live until resolved. |

#### `post_publish_monitoring_request`

```json
{
  "opportunity_id": "ADAM-OPP-0042",
  "sku": "ADAM-ADAM-OPP-0042",
  "channels_live": ["coupang"],
  "live_since": "2026-05-22T14:00:00+09:00",
  "metrics_to_track": [
    "views",
    "clicks",
    "orders_count",
    "revenue_indexed",
    "returns_count",
    "negative_review_count",
    "claim_count"
  ],
  "baseline_period": "no_baseline_first_week",
  "report_cadence": "daily_first_7_days_then_weekly",
  "client_ops_routes": ["04_data_analyst", "02_ops_operator"]
}
```

## Shared Rejection Conditions

Reject or return `rejected_for_info` when:

- any `pii_check` field is false
- `sample_size_cases` is below 5 for client-derived aggregation signals
- raw customer messages are included
- absolute customer revenue, phone numbers, emails, IDs, medical, legal, tax, or payment data are included
- `review.decision` is not `PASS`
- customer-facing action is requested without `requires_human_approval=true`
- any live channel publish is requested before Adam approval
- `channel_submission_ready` has `dry_run_only=false`, `payload.approval_status` other than `adam_approval_required`, or `payload.submit_status` other than `not_submitted`
- `tool_change_alert` lacks source or verification status
- `seller_account_blocker` includes actual secret values instead of only field names in `do_not_disclose`

## Current Commerce Receiver

Commerce currently supports safe file-based receiving through:

```bash
python teams/commerce-agent-team/scripts/import_client_ops_handoff.py path/to/handoff.json --dry-run
```

The receiver accepts v1 aggregation signals and v2 operational signals. Accepted handoffs are written under ignored runtime storage:

```text
teams/commerce-agent-team/runtime/client_ops_handoffs/
```

They are not automatically converted into product candidates. A commerce agent or script must explicitly turn the signal into a scout/risk/listing task.
