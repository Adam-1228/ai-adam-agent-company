# Inbox - 이용대 (CS Manager)

## 수신 가능 작업 유형

| 작업 코드 | 설명 |
| --- | --- |
| `CS-INCOMING` | 신규 인입 응대 (알림톡/SMS/이메일 인박스) |
| `CS-RECOVERY` | 박실행 발송 실패 케이스 회수 응대 |
| `CS-FAQ` | 톤 카드 등재 FAQ에 대한 정형 응답 |
| `CS-ESCALATE` | 자동 분류기가 키워드 감지 시 즉시 본 작업 코드로 인입 |
| `CS-REVIEW-RESPONSE` | 박실행이 발송한 리뷰 요청에 대한 고객 회신 처리 |
| `CS-TONECARD-MISSING` | 톤 카드에 없는 신규 상황 발견 (김은보에게 패스) |

## 수신 채널

- 카카오 알림톡 webhook → 분류기 → 본 inbox
- SMS 폴백 회신 → 본 inbox
- 이메일 inbox (mailto webhook) → 본 inbox
- 박실행 실패 알림 → 본 inbox + Telegram
- 정총괄 수동 배정 → 본 inbox

## 우선순위 분류

| 우선순위 | 조건 | 응답 SLA |
| --- | --- | --- |
| **P0** | 즉시 에스컬레이션 키워드 감지 | 1분 이내 사람 통지 |
| **P1** | 박실행 실패 회수, 동일 고객 2회차 문의 | 30분 이내 초안 |
| **P2** | 톤 카드 외 신규 상황 | 2시간 이내 초안 |
| **P3** | FAQ, 일반 안내 | 4시간 이내 자동 발송 (정총괄 사후 검수) |

영업 시간 외 인입은 모두 자동응답 보류, 다음 영업일 시작 시점에 P 우선순위 재계산.

## 거절 조건

다음은 자동응답하지 않고 즉시 정총괄에게 반려한다.

- P0 키워드 ("환불", "변호사", "고소", "진단", "처방", "주민번호", "자살", "협박" 등)
- 톤 카드 자체가 부재한 고객 케이스
- 동일 케이스 3회 이상 반복 인입
- 운영 외 시간에 24시간 응대 요구
- 의료/법률/세무 자문 요청
- DRY_RUN=true 환경에서 외부 발송 강제 요구

## 현재 큐

아직 배정된 작업 없음.

(샘플은 `tasks/done.md`의 에스컬레이션 사례 참고)


## CS-001-test-refund

TASK ID: CS-001-test-refund
TASK CODE: CS-INCOMING
ASSIGNEE: 03_cs_manager (CS Manager - 이용대)
PRIORITY: P0
REQUESTED BY: assign_task.py
CREATED AT: 2026-05-21 19:48:43
DUE: 확인 필요

CONTEXT:
- 고객이 카카오 알림톡으로 '환불해주세요'라고 메시지를 보냈습니다.
- 실고객 정보 사용 금지. 가상 식별자 또는 케이스 ID만 사용합니다.

INPUTS:
- 확인 필요

EXPECTED OUTPUT:
- output_template.md 형식을 준수

GUARDRAILS:
- 사람 승인 전 외부 발송 금지
- 환불/계약/법적/의료/세무 키워드는 즉시 05_coordinator_qa 에스컬레이션

HANDOFF:
- Next owner: 확인 필요
- Required evidence: 확인 필요
