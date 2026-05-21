<h1 align="center">AI ADAM AGENT COMPANY</h1>

<p align="center">
  <strong>A multi-agent operating workspace for building small, practical AI teams.</strong><br/>
  <strong>실용적인 소규모 AI 팀을 구축하기 위한 멀티 에이전트 운영 워크스페이스.</strong>
</p>

<p align="center">
  <img alt="Status" src="https://img.shields.io/badge/STATUS-ACTIVE-2ea44f?style=for-the-badge" />
  <img alt="Python" src="https://img.shields.io/badge/PYTHON-3.10%2B-3776AB?style=for-the-badge" />
  <img alt="Platform" src="https://img.shields.io/badge/PLATFORM-EC2-FF9900?style=for-the-badge" />
  <img alt="Public Safe" src="https://img.shields.io/badge/PUBLIC--REPO-SAFE-1F6FEB?style=for-the-badge" />
</p>

---

## OVERVIEW &nbsp;·&nbsp; 개요

**EN —** AI Adam Agent Company is a multi-agent operating workspace for building small, practical AI teams. The first production path is **commerce automation**: find product opportunities, score margin and risk, draft listings, and give a human a clear final decision before any real marketplace action.

**KR —** AI Adam Agent Company는 실용적인 소규모 AI 팀을 구축하기 위한 멀티 에이전트 운영 워크스페이스입니다. 첫 번째 프로덕션 트랙은 **커머스 자동화**로, 상품 기회를 발굴하고 마진과 리스크를 평가하며 리스팅 초안을 작성한 뒤, 실제 마켓플레이스 액션 전에 사람이 명확하게 최종 결정을 내릴 수 있도록 돕습니다.

> **HUMAN-IN-THE-LOOP BY DEFAULT** — Agents propose. Humans decide.
> **사람이 최종 결정합니다.** 에이전트는 제안하고, 사람이 승인합니다.

---

## TEAMS &nbsp;·&nbsp; 팀 구성

| Team / 팀 | Owner / 담당 | Purpose / 역할 | Status / 상태 |
| --- | --- | --- | --- |
| `teams/commerce-agent-team` | **Codex** | Product discovery, scoring, compliance checks, listing drafts, dashboard<br/>상품 발굴 · 스코어링 · 컴플라이언스 검토 · 리스팅 초안 · 대시보드 | **Ready for EC2 deployment**<br/>EC2 배포 준비 완료 |
| `teams/client-ops-team` | **Claude** | Client onboarding, CS, recurring operations, weekly reports, QA<br/>고객 온보딩 · CS · 반복 운영 · 주간 리포트 · QA | **v0.1 ready** — 5 agents drafted, awaiting pre-launch checklist<br/>v0.1 준비 — 에이전트 5명 초안 완료, 런칭 전 체크리스트 대기 중 |

---

## REPOSITORY LAYOUT &nbsp;·&nbsp; 저장소 구조

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

- `teams/` — Each agent team lives in its own folder. / 각 에이전트 팀은 독립된 폴더로 구성됩니다.
- `shared/` — Cross-team protocols, templates, and handoff contracts. / 팀 간 공통 프로토콜, 템플릿, 핸드오프 계약서.
- `infra/` — Deployment and operations assets (EC2, etc.). / 배포 및 운영 관련 자산 (EC2 등).

---

## LOCAL QUICK START &nbsp;·&nbsp; 로컬 빠른 시작

```bash
cd teams/commerce-agent-team
python scripts/run_pipeline.py
python scripts/run_agents.py
python dashboard/app.py --check
```

Run the dashboard / 대시보드 실행:

```bash
python dashboard/app.py
```

Then open / 접속:

```
http://127.0.0.1:8080
```

---

## EC2 TARGET &nbsp;·&nbsp; EC2 배포 경로

Recommended server path / 권장 서버 경로:

```
/opt/ai-adam-agent-company
```

Commerce team working directory / 커머스 팀 작업 디렉터리:

```
/opt/ai-adam-agent-company/teams/commerce-agent-team
```

> Detailed deployment notes / 상세 배포 가이드: [`teams/commerce-agent-team/docs/EC2_DEPLOY.md`](teams/commerce-agent-team/docs/EC2_DEPLOY.md)

---

## PUBLIC REPO SAFETY &nbsp;·&nbsp; 공개 저장소 보안 정책

This repository is designed to be **public-safe** when the guardrails below are followed.
본 저장소는 아래 가이드라인을 준수할 경우 **공개 환경에서도 안전**하도록 설계되었습니다.

### DO NOT COMMIT &nbsp;·&nbsp; 커밋 금지 항목

- `.env` files / 환경변수 파일
- API keys / API 키
- AWS keys or `.pem` files / AWS 키 또는 `.pem` 파일
- Real customer data / 실제 고객 데이터
- Real order, sales, or contract data / 실제 주문 · 매출 · 계약 데이터
- Marketplace tokens / 마켓플레이스 토큰
- Generated runtime reports from production / 프로덕션 런타임에서 생성된 리포트

### SAFE TO COMMIT &nbsp;·&nbsp; 커밋 허용 항목

- Templates / 템플릿
- Sample data / 샘플 데이터
- Agent personas / 에이전트 페르소나
- Scripts / 스크립트
- Public-safe docs / 공개 가능한 문서

---

## DESIGN PRINCIPLES &nbsp;·&nbsp; 설계 원칙

1. **Human-in-the-loop by default** — Agents propose, humans approve before any real-world action.<br/>**기본적으로 사람이 개입합니다.** 에이전트는 제안하고, 실제 액션 전 사람이 승인합니다.
2. **Small, composable teams** — Each team owns a clear domain with explicit handoff contracts.<br/>**작고 조합 가능한 팀 단위.** 각 팀은 명확한 도메인과 핸드오프 계약을 갖습니다.
3. **Public-safe by construction** — Secrets and real data never enter the repository.<br/>**구조적으로 공개에 안전.** 시크릿과 실데이터는 저장소에 들어가지 않습니다.
4. **Operable on modest infrastructure** — Designed to run reliably on a single EC2 instance.<br/>**소규모 인프라에서 안정 운영.** 단일 EC2 인스턴스에서도 안정적으로 운영 가능하도록 설계되었습니다.

---

<p align="center">
  <sub><strong>Maintained by</strong> <a href="https://github.com/Adam-1228">@Adam-1228</a> &nbsp;·&nbsp; <strong>Built with</strong> Codex &amp; Claude</sub>
</p>
