# Inbox - 박실행 (Ops Operator)

## 수신 가능 작업 유형

| 작업 코드 | 설명 | 입력 | 출력 |
| --- | --- | --- | --- |
| `OPS-REMIND-D-1` | 예약 전일 18:00 리마인더 | case_id, appointment_id | 정형 로그 |
| `OPS-REMIND-H-2` | 예약 2시간 전 리마인더 | case_id, appointment_id | 정형 로그 |
| `OPS-NOSHOW-TRACK` | 예약 시각 +15분 시점 노쇼 마킹 | case_id, appointment_id | 정형 로그 |
| `OPS-REVIEW-REQ` | 방문 24h 후 리뷰 요청 | case_id, visit_id | 정형 로그 |
| `OPS-DAILY-SUMMARY` | 매일 23:00 일일 실행 요약 | 당일 로그 전체 | JSON 요약 |
| `OPS-RETRY` | 실패 큐 재시도 (정총괄 트리거) | failed_log_id | 정형 로그 |

작업 코드는 김은보가 온보딩 시 등록하지 않은 것은 절대 수신하지 않는다. 미등록 코드는 `REJECTED_UNKNOWN_CODE`.

## 수신 채널

- 스케줄러 (cron / systemd timer / EC2) — 본 inbox는 큐 상태 기록용
- 정총괄 수동 트리거 (재시도)

자유 텍스트 입력 채널 없음. 사람 대화 채널 없음.

## 우선순위 분류

박실행에게 우선순위 개념은 없다. 모든 작업은 등록된 시각에 시작한다.
다만 동시 실행 슬롯이 부족하면 다음 순서:

1. 결제·계약·법적 관련 알림 (실제로는 박실행에게 안 옴 — 들어오면 즉시 거절)
2. 예약 임박 리마인더 (`H-2`)
3. 예약 전일 리마인더 (`D-1`)
4. 사후 작업 (`REVIEW-REQ`, `NOSHOW-TRACK`)
5. 요약/배치 (`DAILY-SUMMARY`)

## 거절 조건

다음은 무조건 거절하고 `REJECTED_*` 코드로 로그 남긴다. 정총괄·김은보 동시 알림.

- 미등록 작업 코드 (`REJECTED_UNKNOWN_CODE`)
- 페이로드 검증 실패 (`REJECTED_INVALID_PAYLOAD`)
- 멱등성 키 누락 (`REJECTED_NO_IDEMPOTENCY_KEY`)
- 자유 텍스트 응답 요구 (`REJECTED_NEEDS_HUMAN`)
- 환불·결제·계약 관련 키워드 페이로드 (`REJECTED_OUT_OF_SCOPE`)

## 현재 큐

스케줄러 연결 전. v0.1에서는 실제 큐 없음. 등록된 작업 명세만 김은보의 인계서로부터 받는다.
