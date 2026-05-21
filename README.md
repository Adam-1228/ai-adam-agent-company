# AI Adam Agent Company

AI Adam Agent Company is a multi-agent operating workspace for building small, practical AI teams.

The first production path is commerce automation: find product opportunities, score margin and risk, draft listings, and give a human a clear final decision before any real marketplace action.

## Teams

| Team | Owner | Purpose | Status |
| --- | --- | --- | --- |
| `teams/commerce-agent-team` | Codex | Product discovery, scoring, compliance checks, listing drafts, dashboard | Ready for EC2 deployment |
| `teams/client-ops-team` | Claude | Client onboarding, CS, recurring operations, weekly reports, QA | Placeholder ready |

## Repository Layout

```text
ai-adam-agent-company/
  teams/
    commerce-agent-team/
    client-ops-team/
  shared/
    protocols/
    task_templates/
    handoff_contracts/
  infra/
    ec2/
```

## Local Quick Start

```bash
cd teams/commerce-agent-team
python scripts/run_pipeline.py
python scripts/run_agents.py
python dashboard/app.py --check
```

Run the dashboard:

```bash
python dashboard/app.py
```

Then open `http://127.0.0.1:8080`.

## EC2 Target

Recommended server path:

```text
/opt/ai-adam-agent-company
```

Commerce team working directory:

```text
/opt/ai-adam-agent-company/teams/commerce-agent-team
```

Detailed deployment notes are in `teams/commerce-agent-team/docs/EC2_DEPLOY.md`.

## Public Repo Safety

This repository is designed to be public-safe when the guardrails are followed.

Do not commit:

- `.env`
- API keys
- AWS keys or `.pem` files
- real customer data
- real order/sales/contract data
- marketplace tokens
- generated runtime reports from production

Commit only templates, sample data, agent personas, scripts, and public-safe docs.

