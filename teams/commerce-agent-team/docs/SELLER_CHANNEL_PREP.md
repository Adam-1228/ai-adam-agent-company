# Seller Channel Preparation

This document covers work that can be completed before live seller API access is connected.

## Rule

AI agents may create draft packages, validate required fields, and prepare Adam approval cards. They may not publish live listings, change prices, accept payments, issue refunds, or store channel API secrets in git.

## Local Readiness File

Use this public template:

```text
teams/commerce-agent-team/config/channel_accounts.example.json
```

When seller accounts are ready, copy it on EC2 only:

```bash
cp teams/commerce-agent-team/config/channel_accounts.example.json \
   teams/commerce-agent-team/config/channel_accounts.local.json
```

Then change only boolean readiness flags and non-sensitive notes. Do not add API keys, access tokens, passwords, bank account numbers, resident registration numbers, customer data, or seller portal passwords.

## Environment Variables Later

Credentials should be stored only in `.env` or system environment variables.

Expected Coupang variables:

```text
COUPANG_ACCESS_KEY
COUPANG_SECRET_KEY
COUPANG_VENDOR_ID
```

Expected Amazon variables:

```text
AMAZON_SP_CLIENT_ID
AMAZON_SP_CLIENT_SECRET
AMAZON_SP_REFRESH_TOKEN
AMAZON_SP_AWS_ACCESS_KEY_ID
AMAZON_SP_AWS_SECRET_ACCESS_KEY
AMAZON_SP_ROLE_ARN
AMAZON_SELLER_ID
AMAZON_MARKETPLACE_ID
```

The readiness checker only reports whether variables are present. It does not print values.

## Current Pre-API Flow

1. `commerce_growth_pipeline.py` creates product opportunities, risk reviews, listing drafts, channel draft payloads, approval requests, and performance tracking records.
2. `check_channel_readiness.py` reports whether seller account preparation is ready.
3. `validate_channel_submissions.py` checks generated Coupang/Amazon draft packages without calling external APIs.
4. Dashboard `/channel-ops` shows readiness and dry-run validation.
5. Dashboard `/growth-pipeline` keeps Adam approval as the final gate.
