# PR Review: Commerce <> Client Ops Handoff Schema

Reviewer: `commerce-agent-team`

## Summary

The proposed handoff direction is useful, but the current team-local handoff docs are not yet strict enough for production automation.

Commerce can receive all five client-ops categories as **anonymized signals**, but only `demand_signal` and `complaint_patterns` map strongly to the existing commerce workflow. The other categories need a derived commerce request or routing metadata.

## Client Ops -> Commerce Fit

| Category | Current Commerce Fit | Finding |
| --- | --- | --- |
| `operational_performance` | Partial | Commerce cannot score raw ops KPIs. Require `derived_commerce_request`. |
| `catalog_usage` | Partial | Useful for listing and packaging assumptions, not product scoring by itself. |
| `demand_signal` | Strong | Best fit for `01_market_scout`; can become a product/category discovery task. |
| `complaint_patterns` | Strong | Good fit for `03_risk_guardian` and `04_listing_builder`; should become risk/copy guardrails. |
| `channel_trends` | Partial | Useful context, but must not be treated as revenue proof. |

## Commerce -> Client Ops Fit

| Category | Fit | Finding |
| --- | --- | --- |
| `new_automation_candidate` | Good | Fits client ops, but must be `dry_run_only=true` until approval. |
| `market_trend` | Good | Fits reports/onboarding notes. Must include confidence and forbidden claims. |
| `tool_change_alert` | Partial | Commerce is not the authoritative source. Require `source_url` and `verification_status`. |
| `rejected_for_info` | Strong | Needed for schema repair loops. |
| `collaboration_request` | Strong | Fits cross-team work if scoped with due date and deliverables. |

## Required Schema Changes

1. Add a common envelope:
   - `contract_version`
   - `direction`
   - `from_team`
   - `to_team`
   - `source_agent`
   - `signal_type`
   - `confidence`
   - `requires_human_approval`
   - `dry_run_only`
   - `pii_check`
   - `review`
   - `payload`

2. Make client-to-commerce `signal_type` an enum:
   - `operational_performance`
   - `catalog_usage`
   - `demand_signal`
   - `complaint_patterns`
   - `channel_trends`

3. Make commerce-to-client `signal_type` an enum:
   - `new_automation_candidate`
   - `market_trend`
   - `tool_change_alert`
   - `rejected_for_info`
   - `collaboration_request`

4. Require `sample_size_cases >= 5` for client-derived signals.

5. Require `review.decision = PASS` before commerce accepts a handoff.

6. Require `derived_commerce_request` for `operational_performance`.

7. Require `source_url` and `verification_status` for `tool_change_alert`.

8. Keep final canonical contract in:

```text
shared/handoff_contracts/commerce_client_ops_contract.md
```

Team-local docs should point to this file instead of becoming separate sources of truth.

## Implementation Notes

Commerce now has a file-based receiver:

```bash
python teams/commerce-agent-team/scripts/import_client_ops_handoff.py shared/handoff_contracts/examples/client_ops_to_commerce_demand_signal.json --dry-run
```

This validates and routes handoffs into ignored runtime storage. It does not automatically mutate public task files or product candidate CSVs.
