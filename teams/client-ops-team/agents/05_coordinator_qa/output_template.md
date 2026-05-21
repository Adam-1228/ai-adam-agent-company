# Output Template - 정총괄

## 산출물 종류

1. **검수 결정문** (JSON + 1줄 사유): 통과 / 보류 / 사람 결정 필요
2. **재작업 요청서** (Markdown): 보류 시 4명 중 1명에게
3. **Adam 에스컬레이션 카드** (Markdown): 6대 케이스 즉시 통지
4. **주간 회고** (Markdown): 매주 금 17:00, 사후 부적합 + 에스컬레이션 정확도

---

## 1) 검수 결정문 (JSON)

```json
{
  "ts": "2026-05-21T15:42:08+09:00",
  "qa_id": "QA-2026-05-21-0042",
  "subject_owner": "03_cs_manager",
  "subject_artifact": "response_draft_msg-2026-05-21-00231",
  "decision": "PASS",
  "reason": "톤 카드 준수, 가격/일정 즉답 없음, 정책 명시 적절.",
  "confidence": "high",
  "next_owner": "03_cs_manager",
  "next_action": "발송 진행"
}
```

`decision` 가능 값:

- `PASS` — 통과, 다음 단계 진행
- `HOLD` — 보류, 수정 요청
- `ESCALATE_TO_ADAM` — Adam 결정 필요 (6대 케이스)
- `OWN_DECISION` — 정총괄 본인 결정으로 진행 (사유 명시)

`confidence` 가능 값: `high` / `medium` / `low`. `low`인 경우 결정 무엇이든 Adam에게도 통지.

---

## 2) 재작업 요청서 (Markdown)

```markdown
REWORK REQUEST

QA ID: QA-2026-05-21-0042
대상: 03_cs_manager / response_draft_msg-2026-05-21-00231
결정: HOLD

## 사유
- 톤 카드 §2 "가격 즉답 금지" 위반: "30분 이내 답변드리겠습니다" → 일정 약속에 해당.

## 요청 사항
1. 위 문장을 "담당자가 영업시간 내 확인 후 회신드리겠습니다"로 수정
2. 수정 후 재검수 요청

## 데드라인
2026-05-21 16:30 (응대 SLA 내)

HANDOFF
- 다음 담당: 03_cs_manager
- 추천 액션: REWORK
```

---

## 3) Adam 에스컬레이션 카드 (Markdown)

```markdown
ESCALATION TO ADAM

QA ID: QA-2026-05-21-0099
긴급도: P0 (즉시)
카테고리: 법적 이슈

## 사실 관계
- 케이스: CLI-2026-XXX (샘플치과)
- 인입: 2026-05-21 14:23, 카카오 알림톡
- 키워드 감지: "환불", "변호사"
- 이용대 자동응답: 보내지 않음 (정상)
- 박실행 추가 작업: 없음
- 현재까지 외부 발송: 없음

## 본인 의견 (정총괄)
법적 절차 언급 + 환불 요구 동시 발생. 자동응답 절대 불가. Adam 직접 응대 권고.

## 권한 안 함
- 변호사 선임 결정 (Adam)
- 환불 결정 (Adam)
- 의료기관 측 대응 톤 (Adam + 고객사 본인)

## 첨부
- 인입 원문: reports/escalations/CLI-2026-XXX/msg-2026-05-21-00231.txt (gitignore)
- 톤 카드: agents/03_cs_manager/tone_cards/CLI-2026-XXX.md
- 최근 7일 응대 이력: reports/cs_log_2026-05-1{4..20}.jsonl

HANDOFF
- 다음 담당: Adam
- 통지 채널: Telegram + 본 카드
- 추천 액션: ADAM_DECIDE
```

---

## 4) 주간 회고 (Markdown)

```markdown
QA WEEKLY REVIEW — 2026-W21

## 1. 처리 건수
- 검수 PASS: 312
- 검수 HOLD: 14
- 검수 OWN_DECISION: 8
- ESCALATE_TO_ADAM: 3

## 2. 사후 부적합
- 1건 / 312건 PASS (0.3%)
- 대상: 이용대 P3 FAQ "영업시간 안내" — 휴무일 누락
- 조치: 톤 카드 보강 요청 (01) + 동일 유형 1주 전수 검수 격상

## 3. Adam 에스컬레이션 정확도
- 3건 모두 Adam이 직접 결정 필요했음 → 정확도 100%
- 올리지 않았으나 올렸어야 한 케이스: 0건 (사후 점검 결과)

## 4. 낮은 confidence 결정
- 2건. 둘 다 Adam에게 동시 통지함. 결과적으로 1건은 Adam도 OWN_DECISION 동의, 1건은 보류 권고로 전환.

## 5. 프로토콜 갱신 제안
- 없음 (이번 주)

HANDOFF
- 다음 담당: Adam
- 추천 액션: 회고 1장 공유, 다음 주 운영 변경 사항 0건
```

---

## 핸드오프 매트릭스

| 결정 | 다음 담당 | 채널 |
| --- | --- | --- |
| `PASS` | 원 작성자 / 다음 파이프라인 | 자동 진행 |
| `HOLD` | 원 작성자 | 재작업 요청서 + inbox 갱신 |
| `ESCALATE_TO_ADAM` | Adam | Telegram + 에스컬레이션 카드 |
| `OWN_DECISION` | 원 작성자 + Adam (참조) | 결정 사유 1줄 + 주간 회고 누적 |
| `LOW_CONFIDENCE` | 결정 무엇이든 + Adam 동시 통지 | Telegram + 본 결정문 |
