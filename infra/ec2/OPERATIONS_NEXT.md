# Operations Next Steps

This runbook tracks the near-term operations work for AI Adam Agent Company.

## Current Server

```text
EC2 public IP: 3.104.252.39
Region: ap-southeast-2
Instance type: t3.micro
Repo path: /opt/ai-adam-agent-company
Commerce team path: /opt/ai-adam-agent-company/teams/commerce-agent-team
Dashboard URL: http://3.104.252.39:8080
```

## 1. Restrict AWS Security Group 8080

Server-side UFW already allows dashboard port `8080` only from:

```text
59.13.218.189/32
```

AWS security group should match that rule too.

Prompt for Chrome AI or AWS console assistant:

```text
AWS EC2 보안 그룹 sg-0e3b019128779e53a의 인바운드 규칙을 수정해줘.

목표:
- TCP 8080은 59.13.218.189/32 에서만 접속 가능해야 함
- TCP 8050은 사용하지 않으므로 삭제

작업:
1. 리전 ap-southeast-2 Sydney로 이동해.
2. EC2 보안 그룹 sg-0e3b019128779e53a / launch-wizard-1을 열어.
3. 인바운드 규칙에서 TCP 8080 규칙의 Source를 0.0.0.0/0 에서 59.13.218.189/32 로 변경해.
4. Description은 Commerce Agent Dashboard - ADAM home IP only 로 설정해.
5. TCP 8050 규칙은 삭제해.
6. 기존 22, 80, 443, 8000 규칙은 수정하지 마.
7. 아웃바운드 규칙은 건드리지 마.
8. 완료 후 TCP 8080 Source가 59.13.218.189/32이고 TCP 8050 규칙이 없는지 확인해줘.
```

## 2. Enable OpenAI API on the Server

Do not commit API keys to Git. Enter the key directly on EC2.

From local PowerShell:

```powershell
ssh -i "C:\Users\ADAM\Downloads\bot-key.pem" ubuntu@3.104.252.39
```

On EC2, use the safe config helper:

```bash
cd /opt/ai-adam-agent-company/teams/commerce-agent-team
.venv/bin/python scripts/configure_env.py --openai
.venv/bin/python scripts/test_llm.py
.venv/bin/python scripts/run_agents.py --use-llm
sudo systemctl restart commerce-dashboard.service
```

Check:

```bash
.venv/bin/python scripts/configure_env.py --show
```

## 3. Merge Claude Client Ops Team

Expected target:

```text
teams/client-ops-team/
```

Only merge public-safe files:

- agent personas
- operating protocols
- task templates
- sample reports

Do not merge:

- `.env`
- `.venv`
- customer data
- API keys
- contracts
- private reports

## 4. Port 8050 Cleanup

Server-side UFW no longer allows 8050.

AWS security group still needs to remove TCP `8050` if it remains open there.

## 5. Domain and HTTPS

Recommended production path:

1. Choose a domain or subdomain, for example `agents.adam-seong.com`.
2. Add DNS `A` record:

```text
agents.adam-seong.com -> 3.104.252.39
```

3. Install Nginx and Certbot on EC2.
4. Proxy HTTPS traffic to local dashboard port 8080.
5. Change dashboard service to bind to `127.0.0.1` instead of `0.0.0.0`.
6. Close public 8080 after HTTPS works.

Do not start this step until the domain is decided.

## 6. When Home IP Changes

Find new public IP:

```bash
curl https://api.ipify.org
```

Update UFW:

```bash
sudo ufw delete allow from 59.13.218.189/32 to any port 8080 proto tcp
sudo ufw allow from NEW_PUBLIC_IP/32 to any port 8080 proto tcp comment 'Commerce dashboard ADAM IP'
sudo ufw status numbered
```

Then update AWS security group TCP `8080` source to:

```text
NEW_PUBLIC_IP/32
```

## 7. Run Retention and Disk Safety

Commerce runs are cleaned daily by:

```text
commerce-cleanup.timer
```

The cleanup keeps the latest 30 runs and matching agent outbox artifacts.

Manual dry run:

```bash
cd /opt/ai-adam-agent-company/teams/commerce-agent-team
.venv/bin/python scripts/cleanup_runs.py --keep 30 --dry-run
```

Manual cleanup:

```bash
.venv/bin/python scripts/cleanup_runs.py --keep 30
```

Status checks:

```bash
systemctl status commerce-cleanup.timer
df -h /
```
