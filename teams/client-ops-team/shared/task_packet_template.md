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

## 예시

```text
TASK ID: TASK-2026-05-21-001
ASSIGNEE: 01_onboarding_manager
PRIORITY: P1
REQUESTED BY: 05_coordinator_qa
CREATED AT: 2026-05-21 09:30
DUE: 2026-05-23 18:00

CONTEXT:
- 신규 케이스 CLI-2026-014 (샘플치과). 계약 검증 완료, 권한 감사 1차 통과.
- 시술 메뉴 중 회색지대 1건은 정총괄 검수 후 결정.

INPUTS:
- 외부 사업자번호 검증 캡처 (case_id로 마스킹)
- 계약서 본문 ref (외부 보관, 본 패킷에 본문 미포함)

EXPECTED OUTPUT:
- 온보딩 패키지(Markdown)
- 위험 신호 카드(JSON)
- 정기 작업 인계서(JSON)
- 응대 톤 카드(Markdown)

GUARDRAILS:
- 사업자번호 4자리 외 마스킹
- 계약서 본문 저장소 커밋 금지
- 시술 메뉴 회색지대는 정총괄 결정 전 박실행 작업 등록 금지

HANDOFF:
- Next owner: 05_coordinator_qa
- Required evidence: 위 4종 산출물 + 사업자번호 검증 결과 라벨
```

---

## 작업 코드 카탈로그

작업 코드는 `{영역}-{동사 or 명사}` 형식. v1에서는 아래 5개 영역.

### `ONB-*` (김은보 / Onboarding)

| 코드 | 설명 |
| --- | --- |
| `ONB-INTAKE` | 신규 고객 1차 정보 수집 |
| `ONB-CONTRACT` | 계약 조건 검증 |
| `ONB-FORBIDDEN` | 금지 업무 식별 |
| `ONB-PERMSCAN` | 외부 시스템 API 권한 감사 |
| `ONB-PACKAGE` | 온보딩 패키지 작성 |
| `ONB-HANDOFF-OPS` | 박실행에게 정기 작업 등록 인계 |
| `ONB-REVIEW-REQUEST` | 정총괄에게 셋업 검수 요청 |
| `ONB-RENEW` | 계약 갱신 시 재검증 (1년 주기) |

### `OPS-*` (박실행 / Ops Operator)

| 코드 | 설명 |
| --- | --- |
| `OPS-REMIND-D-1` | 예약 전일 18:00 리마인더 |
| `OPS-REMIND-H-2` | 예약 2시간 전 리마인더 |
| `OPS-NOSHOW-TRACK` | 예약 시각 +15분 시점 노쇼 마킹 |
| `OPS-REVIEW-REQ` | 방문 24h 후 리뷰 요청 |
| `OPS-DAILY-SUMMARY` | 일일 실행 요약 |
| `OPS-WEEKLY-FEED` | 주간 익명 집계 (최분석으로) |
| `OPS-RETRY` | 실패 큐 재시도 |

### `CS-*` (이용대 / CS Manager)

| 코드 | 설명 |
| --- | --- |
| `CS-INCOMING` | 신규 인입 응대 |
| `CS-RECOVERY` | 박실행 발송 실패 회수 응대 |
| `CS-FAQ` | 톤 카드 등재 FAQ 정형 응답 |
| `CS-ESCALATE` | P0 에스컬레이션 |
| `CS-REVIEW-RESPONSE` | 리뷰 요청 회신 처리 |
| `CS-TONECARD-MISSING` | 톤 카드 부재 상황 발견 |

### `ANL-*` (최분석 / Data Analyst)

| 코드 | 설명 |
| --- | --- |
| `ANL-WEEKLY` | 주간 성과 리포트 |
| `ANL-DAILY-SNAPSHOT` | 일일 KPI 스냅샷 |
| `ANL-MONTHLY` | 월간 종합 리포트 |
| `ANL-AD-HOC` | 정총괄 또는 Adam ad-hoc 분석 |
| `ANL-COMMERCE-FEED` | 커머스 팀 익명 집계 |
| `ANL-CASE-LAUNCH` | 신규 케이스 KPI 측정 시작 |

### `QA-*` (정총괄 / Coordinator-QA)

| 코드 | 설명 |
| --- | --- |
| `QA-ONB-REVIEW` | 김은보 산출물 검수 |
| `QA-OPS-DAILY` | 박실행 일일 요약 검수 |
| `QA-OPS-FAILURE` | 박실행 실패/거절 처리 |
| `QA-CS-P0` | 이용대 P0 → Adam 통지 |
| `QA-CS-DRAFT` | 이용대 P1/P2 초안 검수 |
| `QA-CS-POST-REVIEW` | 이용대 P3 사후 검수 |
| `QA-ANL-WEEKLY` | 최분석 주간 리포트 검수 |
| `QA-ANL-COMMERCE-FEED` | 커머스 송부 패키지 검수 |
| `QA-ADAM-ESCALATION` | 6대 케이스 Adam 직접 통지 |
| `QA-CONFLICT` | 4명 간 충돌 조정 |

신규 작업 코드 추가는 정총괄 1차 검토 + Adam 승인 + `shared/operating_protocol.md` 갱신을 거친다.
