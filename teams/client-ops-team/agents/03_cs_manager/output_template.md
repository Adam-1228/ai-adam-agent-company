# Output Template - 이용대

## 산출물 종류

1. **에스컬레이션 카드** (JSON): P0 키워드 감지 시 즉시
2. **응대 초안** (Markdown): P1/P2 케이스의 사람 검수용
3. **자동응답 발송 로그** (JSONL): P3 자동 발송 결과
4. **톤 카드 보강 요청** (Markdown): 신규 상황 발견 시 김은보에게

---

## 1) 에스컬레이션 카드 (JSON)

```json
{
  "ts": "2026-05-21T14:23:11+09:00",
  "case_id": "CLI-2026-XXX",
  "incoming_id": "msg-2026-05-21-00231",
  "severity": "P0",
  "trigger": ["환불", "변호사"],
  "channel": "kakao_alimtalk",
  "summary": "샘플치과 고객, 시술 결과 불만 + 환불 요구 + 변호사 언급",
  "automated_response_sent": false,
  "next_owner": "05_coordinator_qa",
  "escalate_to_human": true,
  "human_target": "Adam (via Telegram)"
}
```

P0 카드 발행 시 동시에 Telegram(`TELEGRAM_CHAT_ID_ADAM`) 발송. 자동응답은 발송하지 않음 (`automated_response_sent: false` 고정).

---

## 2) 응대 초안 (Markdown, P1/P2)

```markdown
RESPONSE DRAFT

케이스: CLI-2026-XXX
인입 ID: msg-2026-05-21-00231
우선순위: P2
인입 채널: 카카오 알림톡
인입 요약: 예약 변경 요청 (정책 외 시점)

## 상황 분석
- 예약일: 2026-05-23
- 변경 요청 시점: 2026-05-21 14:23 (예약 -2일, 정책상 -3일까지 무료 변경)
- 톤 카드: 정중, 정책 명시, 가격/일정 즉답 금지

## 초안 (검수 후 발송)
> 안녕하세요, 샘플치과입니다.
> 예약 변경 문의 확인했습니다.
> 변경 가능 여부와 가능한 일정은 담당자가 영업시간 내 확인하여 바로 회신드리겠습니다.
> 감사합니다.

## 의도적으로 하지 않은 것
- 변경 가능 시점 즉답 (정책 위반 가능성)
- 위약금 언급 (가격은 톤 카드에 없음)
- 사과 표현 (사실관계 미확정)

HANDOFF
- 다음 담당: 05_coordinator_qa
- 넘길 자료: 본 초안, 톤 카드 ref
- 확인 필요: 위약금 정책 여부
- 하드 스톱: 없음
- 추천 액션: REVIEW (정총괄 1회 검수 후 발송)
```

---

## 3) 자동응답 발송 로그 (JSONL, P3)

```json
{
  "ts": "2026-05-21T10:02:14+09:00",
  "case_id": "CLI-2026-XXX",
  "incoming_id": "msg-2026-05-21-00198",
  "severity": "P3",
  "category": "faq_business_hours",
  "template_id": "FAQ_HOURS_KO",
  "channel": "kakao_alimtalk",
  "status": "SENT",
  "post_review_required": true,
  "review_owner": "05_coordinator_qa"
}
```

P3 자동응답은 정총괄 사후 검수 큐로 자동 적재. 검수 결과 부적합 판정 시 본 memory에 1줄 추가.

---

## 4) 톤 카드 보강 요청 (Markdown)

```markdown
TONE CARD GAP - CLI-2026-XXX

발견 일시: 2026-05-21 15:00
인입 케이스: msg-2026-05-21-00250
신규 상황: 시술 후 사진 동의 요청 회신
현재 톤 카드 누락: "사진/영상 동의" 항목 없음

## 임시 처리
- 자동응답 안 함
- P2로 정총괄 경유 응대

## 김은보 요청 사항
- 사진/영상 동의 관련 톤·금지 표현 추가
- 의료/광고법 영역 여부 확인

HANDOFF
- 다음 담당: 01_onboarding_manager
- 넘길 자료: 본 메모, 인입 원문 케이스ID
- 추천 액션: 톤 카드 v2 작성 후 정총괄 검수
```

---

## 핸드오프 매트릭스

| 산출물 | 다음 담당 | 채널 |
| --- | --- | --- |
| 에스컬레이션 카드 (P0) | 05_coordinator_qa + Adam | 즉시 Telegram + `agents/05_coordinator_qa/inbox.md` |
| 응대 초안 (P1/P2) | 05_coordinator_qa | `agents/05_coordinator_qa/inbox.md` |
| 자동응답 로그 (P3) | 05_coordinator_qa (사후 검수) | 일일 묶음 |
| 톤 카드 보강 요청 | 01_onboarding_manager | `agents/01_onboarding_manager/inbox.md` |
| 박실행 회수 응대 결과 | 02_ops_operator | 실패 로그 클로즈용 회신 |
| 주간 카테고리 집계 | 04_data_analyst | 매주 월요일 |
