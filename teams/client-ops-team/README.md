# AI Client Ops Team

신규 고객 온보딩, 정시 자동화 운영, 1차 CS, 주간 성과 분석, 외부 산출물 최종 QA를 맡는 5명짜리 파일 기반 AI 에이전트 팀입니다.

이 팀의 목적은 자체 상품을 파는 것이 아니라, 자매 팀(`commerce-agent-team`)이 발굴/검수한 결과와 실제 운영 고객을 안전하게 연결하고, 사람(Adam)의 판단이 필요한 케이스만 정확히 골라 올리는 것입니다.

## Team

| Agent | Role | LLM | Output |
| --- | --- | --- | --- |
| `01_onboarding_manager` (김은보) | 신규 고객 정보 수집/계약 검증/권한 감사 | Claude | 온보딩 패키지 + 위험 신호 |
| `02_ops_operator` (박실행) | 정시 자동화 작업 실행 (리마인더/노쇼/리뷰요청) | Gemini Flash | 실행 결과 정형 로그 |
| `03_cs_manager` (이용대) | 1차 응대 + 에스컬레이션 판단 | Claude | 응대 초안 또는 에스컬레이션 카드 |
| `04_data_analyst` (최분석) | 주간 성과 분석 + 리포트 초안 | Claude + Codex | 주간 리포트 (TL;DR + 표 + 출처) |
| `05_coordinator_qa` (정총괄) | 외부 산출물 최종 QA + 사람 에스컬레이션 게이트 | Claude | 통과/보류/Adam에 올림 |

## Folder Structure

```text
client-ops-team/
  agents/                    # 5명의 페르소나, inbox, memory, output_template
    01_onboarding_manager/
    02_ops_operator/
    03_cs_manager/
    04_data_analyst/
    05_coordinator_qa/
  config/                    # LLM 모델 설정
  shared/                    # 운영 원칙, 패킷 양식, 핸드오프 계약, 커머스팀 연동
  tasks/                     # 대기/진행/완료 큐
  reports/                   # 실제 주간/일간 리포트 (gitignore)
  company_manifest.md        # 팀 헌장
  .env.example               # 환경변수 placeholder
```

## Quick Start

```bash
cd "C:\Users\ADAM\Documents\Ai Adam Agent Company\ai-adam-agent-company\teams\client-ops-team"
copy .env.example .env
```

`.env`를 열어 실제 키를 채웁니다. 이 팀은 아직 실행 스크립트가 없습니다. v0.1은 페르소나/계약/핸드오프 문서 단계입니다.

에이전트에게 일을 시키려면 각 에이전트의 `inbox.md`에 작업 패킷(`shared/task_packet_template.md` 형식)을 직접 적습니다.

## LLM 배정 원칙

- 판단/공감/문서화가 본질인 자리(`01`, `03`, `04`, `05`): Claude
- 반복 실행/멱등성이 본질인 자리(`02`): Gemini Flash
- 코드 자동화/스크립트는 Codex가 보조 (`04` 데이터 처리)

상세는 `company_manifest.md`와 `config/agent_models.json`을 봅니다.

## 커머스 팀과의 관계

- 같은 모노레포의 자매 팀: `teams/commerce-agent-team` (Codex 담당)
- 우리 팀 → 커머스 팀: 운영 현장에서 발견한 자동화 후보, 익명 집계 트렌드
- 커머스 팀 → 우리 팀: 신규 상품/카탈로그 변경, 시장 트렌드

핸드오프는 `shared/commerce_integration.md`, `shared/handoff_to_commerce.md`, `shared/handoff_from_commerce.md`를 봅니다.

## Pre-Launch

실운영 전 12개 카테고리 점검은 `shared/pre_launch_checklist.md`에 있습니다. 이 체크리스트가 모두 통과되기 전에는 실제 고객 응대를 시작하지 않습니다.

## Guardrails

- 사람 승인 전 자동 환불, 자동 계약 변경, 자동 외부 발송 금지
- 의료/법률/세무/개인정보 케이스는 즉시 사람에게 에스컬레이션
- 실고객 정보, 실계약서, 실 API 키는 이 폴더에 절대 커밋하지 않음
- `02_ops_operator`는 양방향 대화 금지, 정형 출력만, 멱등성 보장
