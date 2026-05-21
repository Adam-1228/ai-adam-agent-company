# Output Template - 박실행

박실การ의 모든 출력은 **정형**이다. 자유 텍스트 출력 없음.

## 산출물 종류

1. **실행 로그 1건** (JSONL 1줄): 매 작업 실행 시
2. **일일 실행 요약** (JSON + Markdown 1장): 매일 23:00
3. **거절/실패 알림** (JSON): 즉시 정총괄·관련자에게

---

## 1) 실행 로그 1건 (JSONL)

```json
{
  "ts": "2026-05-21T18:00:03+09:00",
  "task_code": "OPS-REMIND-D-1",
  "case_id": "CLI-2026-XXX",
  "target_id": "appt-91823",
  "idempotency_key": "OPS-REMIND-D-1-CLI-2026-XXX-appt-91823-20260521",
  "channel": "kakao_alimtalk",
  "template_id": "REMIND_D1_KO",
  "status": "SUCCESS",
  "attempt": 1,
  "latency_ms": 412,
  "dry_run": false,
  "late_start": false,
  "error": null
}
```

`status` 가능 값:

- `SUCCESS`
- `SKIPPED` (멱등성 충돌 / 이미 처리됨)
- `FAILED_VALIDATION` (페이로드 검증 실패)
- `FAILED_DELIVERY` (채널 응답 실패, 재시도 모두 소진)
- `RETRYING` (재시도 진행 중)
- `REJECTED_UNKNOWN_CODE` / `REJECTED_NEEDS_HUMAN` / `REJECTED_OUT_OF_SCOPE`

---

## 2) 일일 실행 요약 (JSON + Markdown)

JSON:

```json
{
  "date": "2026-05-21",
  "timezone": "Asia/Seoul",
  "counts": {
    "scheduled": 412,
    "success": 408,
    "skipped": 2,
    "failed": 2,
    "rejected": 0
  },
  "on_time_rate": 0.997,
  "delivery_rate": 0.995,
  "duplicate_send": 0,
  "missing_logs": 0,
  "failures": [
    {
      "task_code": "OPS-REMIND-D-1",
      "case_id": "CLI-2026-XXX",
      "target_id": "appt-91900",
      "reason": "kakao_5xx_after_3_retries",
      "handoff": "03_cs_manager"
    }
  ],
  "handoff": {
    "to": "05_coordinator_qa",
    "review_required": false
  }
}
```

Markdown (정총괄 인지용 1장):

```markdown
OPS DAILY SUMMARY 2026-05-21

- 예정: 412
- 성공: 408
- 스킵: 2
- 실패: 2
- 거절: 0
- 정시 실행률: 99.7%
- 전송 성공률: 99.5%
- 중복 발송: 0
- 로그 누락: 0

## 실패 상세
1. OPS-REMIND-D-1 / CLI-2026-XXX / appt-91900 — kakao 5xx 3회 재시도 실패 → 03_cs_manager 회수 응대 요청
2. (...)

HANDOFF
- 다음 담당: 05_coordinator_qa
- 넘길 자료: 본 요약, 실패 상세 5건
- 확인 필요: 없음 / 또는 (정총괄이 판단)
- 하드 스톱: 없음
- 추천 액션: PROCEED
```

---

## 3) 거절/실패 즉시 알림 (JSON, Telegram/Slack 페이로드)

```json
{
  "ts": "2026-05-21T18:02:11+09:00",
  "severity": "warn",
  "task_code": "OPS-REMIND-D-1",
  "case_id": "CLI-2026-XXX",
  "status": "FAILED_DELIVERY",
  "reason": "kakao_5xx_after_3_retries",
  "next_owner": "03_cs_manager",
  "review_owner": "05_coordinator_qa"
}
```

`severity` 가능 값: `info` / `warn` / `crit`.
`crit`: 작업 코드가 미등록이거나, 5분 이상 지연 시작, 또는 동일 케이스에서 3개 이상 실패 시.

---

## 핸드오프 매트릭스

| 산출물 | 다음 담당 | 채널 |
| --- | --- | --- |
| 실행 로그 JSONL | (저장만) | `reports/ops_daily_*.jsonl` |
| 일일 요약 | 05_coordinator_qa | `agents/05_coordinator_qa/inbox.md` |
| 실패 회수 응대 요청 | 03_cs_manager | 즉시 Telegram + `agents/03_cs_manager/inbox.md` |
| 주간 익명 집계 | 04_data_analyst | 매주 월요일 09:00 |
| 멱등성 위반/미등록 코드 | 01_onboarding_manager + 05_coordinator_qa | 즉시 알림 |
