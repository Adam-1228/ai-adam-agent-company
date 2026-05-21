# EC2 Deployment Guide

이 문서는 `ai-adam-agent-company` 안의 `commerce-agent-team`을 EC2에서 실행하기 위한 최소 운영 절차입니다.

## 1. 서버 준비

Ubuntu 기준:

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip git
```

프로젝트 위치 예시:

```bash
sudo mkdir -p /opt/ai-adam-agent-company
sudo chown -R ubuntu:ubuntu /opt/ai-adam-agent-company
```

로컬에서 EC2로 복사하거나 GitHub에 올린 뒤 clone합니다.

```bash
cd /opt
git clone https://github.com/Adam-1228/ai-adam-agent-company.git
cd /opt/ai-adam-agent-company/teams/commerce-agent-team
```

## 2. 환경 변수 설정

```bash
cp .env.example .env
nano .env
```

처음에는 mock 모드로도 실행됩니다.

```text
LLM_PROVIDER=mock
```

대시보드 로그인을 켜려면 아래 값도 설정합니다.

```text
DASHBOARD_USERNAME=adam
DASHBOARD_PASSWORD=strong-random-password
```

OpenAI API를 붙일 때:

```text
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-...
OPENAI_BASE_URL=https://api.openai.com/v1
```

`.env`는 절대 GitHub에 올리지 않습니다.

## 3. 수동 실행 확인

```bash
python3 -m venv .venv
.venv/bin/python scripts/run_pipeline.py
.venv/bin/python scripts/run_agents.py
.venv/bin/python dashboard/app.py --check
```

LLM 보강 메모까지 실행하려면:

```bash
.venv/bin/python scripts/run_agents.py --use-llm
```

## 4. 대시보드 실행

로컬 서버 내부에서만 확인:

```bash
.venv/bin/python dashboard/app.py --host 127.0.0.1 --port 8080
```

외부 접속을 열 때:

```bash
.venv/bin/python dashboard/app.py --host 0.0.0.0 --port 8080
```

EC2 보안 그룹에서 8080 포트는 본인 IP만 허용하는 것을 권장합니다. 더 안전한 방식은 SSH 터널입니다.

```bash
ssh -L 8080:127.0.0.1:8080 ubuntu@YOUR_EC2_PUBLIC_IP
```

그 뒤 브라우저에서 `http://127.0.0.1:8080`을 엽니다.

## 5. systemd 자동 실행

회사 repo root 기준으로 아래 파일들을 서버에 복사합니다.

```bash
sudo cp /opt/ai-adam-agent-company/teams/commerce-agent-team/ops/systemd/commerce-agents.service /etc/systemd/system/
sudo cp /opt/ai-adam-agent-company/teams/commerce-agent-team/ops/systemd/commerce-agents.timer /etc/systemd/system/
sudo cp /opt/ai-adam-agent-company/teams/commerce-agent-team/ops/systemd/commerce-dashboard.service /etc/systemd/system/
```

서비스 파일 안의 `User`, `WorkingDirectory`, `EnvironmentFile`, `ExecStart` 경로가 실제 서버 경로와 맞는지 확인합니다.

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now commerce-agents.timer
sudo systemctl enable --now commerce-dashboard.service
```

상태 확인:

```bash
systemctl status commerce-agents.timer
systemctl status commerce-dashboard.service
journalctl -u commerce-agents.service -n 100 --no-pager
journalctl -u commerce-dashboard.service -n 100 --no-pager
```

## 6. 운영 루틴

1. `data/manual_inbox/`에 새 후보 CSV를 넣습니다.
2. `python3 scripts/import_candidates.py data/manual_inbox/new_candidates.csv`로 후보 DB에 반영합니다.
3. 타이머가 자동으로 실행되거나 `python3 scripts/run_agents.py --use-llm`을 수동 실행합니다.
4. 대시보드에서 최신 리포트를 확인합니다.
5. 사람이 최종 승인한 상품만 샘플 구매, 상세페이지 제작, 판매 등록 단계로 넘깁니다.

## 7. 주의 사항

- 자동 크롤링과 자동 게시 전에는 각 플랫폼 약관과 API 정책을 확인합니다.
- KC, 식품, 화장품, 전기용품, 어린이용품, 의료/건강 표현 상품은 보수적으로 제외합니다.
- 타 판매자의 이미지, 상세페이지, 리뷰 문구는 그대로 사용하지 않습니다.
- 첫 매출 전까지는 자동 등록보다 “후보 발굴 -> 검수 -> 사람 승인” 흐름을 유지합니다.
