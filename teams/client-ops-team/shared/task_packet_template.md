# Task Packet Template

Use this format when assigning work to any client-ops agent.

```text
TASK ID:
ASSIGNEE:
PRIORITY:
REQUESTED BY:
CREATED AT:
DUE:

CONTEXT:
- Use masked or synthetic details only.

INPUTS:
- Source files or case IDs.

EXPECTED OUTPUT:
- Markdown summary, JSONL log, checklist, draft response, or escalation card.

GUARDRAILS:
- No real customer data in Git.
- No outbound message without approval unless explicitly marked dry-run.
- Escalate legal, medical, refund, contract, or personal-data risks.

HANDOFF:
- Next owner:
- Required evidence:
```

