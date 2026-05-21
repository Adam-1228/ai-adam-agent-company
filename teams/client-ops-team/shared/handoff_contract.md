# Handoff Contract

## ONB -> OPS

Onboarding Manager hands off:

- case ID
- approved operating scope
- allowed channels
- blocked promises or sensitive keywords
- task schedule

Ops Operator must not execute anything outside the approved scope.

## OPS -> CS

Ops Operator hands off:

- failed delivery case IDs
- no-show or reminder exceptions
- repeated customer replies
- channel failure evidence

CS Manager drafts responses but escalates any P0 trigger.

## CS -> QA

CS Manager hands off:

- escalation card
- masked conversation summary
- proposed response
- risk reason

Coordinator/QA decides pass, revise, or Adam escalation.

## DATA -> QA

Data Analyst hands off:

- weekly KPI summary
- source list
- anomaly notes
- confidence level

Coordinator/QA reviews before external delivery.

---

## 5명 핸드오프 매트릭스 (한국어 상세)

모든 핸드오프는 `task_packet_template.md`의 양식 + 산출물의 `HANDOFF` 블록을 사용한다.

| From → To | 트리거 | 필수 전달 | 채널 |
| --- | --- | --- | --- |
| 01 김은보 → 05 정총괄 | 온보딩 패키지 완료 | 패키지(MD), 위험 신호 카드(JSON), 작업 인계서(JSON), 톤 카드(MD) | `agents/05_coordinator_qa/inbox.md` |
| 01 김은보 → 02 박실행 | 정총괄 셋업 검수 통과 후 | 정기 작업 명세 (작업코드/스케줄/채널/템플릿ID/멱등성키 패턴) | `agents/02_ops_operator/inbox.md` |
| 01 김은보 → 03 이용대 | 정총괄 셋업 검수 통과 후 | 응대 톤 카드 (호칭, 톤, 금지 표현, 즉시 에스컬레이션 키워드, VIP 여부) | `agents/03_cs_manager/memory.md` 갱신 |
| 01 김은보 → 04 최분석 | 정총괄 셋업 검수 통과 후 | KPI 측정 시작일, 비교 기준 (전월/동종 업종) | `agents/04_data_analyst/inbox.md` (`ANL-CASE-LAUNCH`) |
| 02 박실행 → 05 정총괄 | 매일 23:00 일일 요약 | 일일 실행 요약 (JSON + MD), 실패 상세 | `agents/05_coordinator_qa/inbox.md` (`QA-OPS-DAILY`) |
| 02 박실행 → 05 정총괄 | 즉시 실패/거절 발생 | 실패 알림 JSON (severity, reason, next_owner) | Telegram + `agents/05_coordinator_qa/inbox.md` |
| 02 박실행 → 03 이용대 | 발송 실패 회수 | 실패한 case_id, target_id, 채널, 사유 | `agents/03_cs_manager/inbox.md` (`CS-RECOVERY`) |
| 02 박실행 → 04 최분석 | 매주 월 09:00 | 주간 익명 집계 JSONL (개인정보 없음) | 자동 파일 드롭 |
| 03 이용대 → 05 정총괄 | P0 키워드 감지 | 에스컬레이션 카드 (JSON), 인입 원문 ref | Telegram + `agents/05_coordinator_qa/inbox.md` (`QA-CS-P0`) |
| 03 이용대 → 05 정총괄 | P1/P2 초안 작성 | 응대 초안 (MD), 톤 카드 ref, 상황 분석 | `agents/05_coordinator_qa/inbox.md` (`QA-CS-DRAFT`) |
| 03 이용대 → 05 정총괄 | P3 자동응답 발송 | 일일 묶음 발송 로그 (JSONL) | 사후 샘플 검수 (`QA-CS-POST-REVIEW`) |
| 03 이용대 → 01 김은보 | 톤 카드 외 신규 상황 | 톤 카드 보강 요청 (MD), 인입 케이스ID | `agents/01_onboarding_manager/inbox.md` (`CS-TONECARD-MISSING`) |
| 03 이용대 → 04 최분석 | 매주 월 09:30 | 응대 카테고리 집계 (P0/P1/P2/P3 건수, 카테고리 분포) | 자동 파일 드롭 |
| 04 최분석 → 05 정총괄 | 매주 월 12:00 | 주간 리포트(MD), 데이터 소스 경로, 가공 스크립트 경로 | `agents/05_coordinator_qa/inbox.md` (`QA-ANL-WEEKLY`) |
| 04 최분석 → 05 정총괄 | 커머스 송부 패키지 작성 | 익명 집계 JSON (업종/주차 단위) | `agents/05_coordinator_qa/inbox.md` (`QA-ANL-COMMERCE-FEED`) |
| 05 정총괄 → 01..04 | 보류 결정 | 재작업 요청서 (MD), 사유, 데드라인 | 해당 에이전트 `inbox.md` 갱신 |
| 05 정총괄 → Adam | 6대 케이스 발생 | 에스컬레이션 카드 (MD), 첨부 파일 ref | Telegram + 이메일 |
| 05 정총괄 → commerce-agent-team | 익명 집계 패키지 통과 | `shared/handoff_to_commerce.md` 참조 | 별도 정의 |

## 충돌 해소

5명 간 충돌이 발생하면 정총괄이 `QA-CONFLICT` 코드로 처리한다.

| 충돌 유형 | 우선 |
| --- | --- |
| 박실행 정시 실행 vs 이용대 응대 톤 (예: 새벽 알림) | 응대 톤 우선, 박실행 일정 재조정 |
| 박실행 멱등성 vs 김은보 작업 명세 변경 | 김은보 명세 갱신 후 박실행 적용 (재발송 금지) |
| 이용대 자동응답 가능 vs 최분석 데이터 부족 | 정총괄 판단 (보수적 측) |
| 최분석 결론 vs 김은보 케이스 컨텍스트 | 정총괄이 양측 통합, low confidence면 Adam |

모든 충돌의 최종 책임은 정총괄. 본인 confidence가 낮으면 Adam.

## 핸드오프 거부 조건

수신측은 다음의 경우 거부할 수 있다.

- `HANDOFF` 블록 부재 또는 필드 누락
- 식별정보 마스킹 미적용 외부 송부용 자료
- 작업 코드 미정의
- `확인 필요` 항목이 있으나 명시되지 않음

거부 시 사유 1줄과 함께 원 작성자에게 반려.
