# Output Template - 김은보

## 산출물 종류

1. **온보딩 패키지** (Markdown): 신규 고객 1건당 1장 요약
2. **위험 신호 카드** (JSON): 정총괄 검수 인풋
3. **정기 작업 인계서** (JSON): 박실행에게 넘기는 작업 명세
4. **응대 톤 카드** (Markdown): 이용대에게 넘기는 고객별 응대 가이드

---

## 1) 온보딩 패키지 (Markdown)

```markdown
ONBOARDING PACKAGE

고객 ID: CLI-2026-XXX
업종: (예: 치과 / 미용실 / 학원)
운영 시작 예정일:
계약 요금제 / 주기:
담당자: 샘플치과 OOO 원장님 (010-XXXX-XXXX, 마스킹)

## 1. 확인된 항목
- 사업자번호: 검증 완료 (YYYY-MM-DD, 외부 API)
- 결제 수단: 본인 명의 카드 확인 완료
- 운영 채널: 카카오 알림톡, SMS 폴백

## 2. 확인 필요 항목
- (없으면 "없음")

## 3. 우리가 하지 않을 업무
- (예: 진료 결과 안내, 처방 관련 응대 — 의료법 영역)

## 4. API/권한 감사
- 외부 시스템: (예: 예약 시스템 X사)
- 요청 권한: 예약 조회/생성 (쓰기 일부)
- 과잉 권한: 없음 / 또는 (예: 환자 카르테 읽기 — 거절함)

## 5. 첫 30일 운영 계획
- 박실행 정기 작업: 예약 전일 리마인더 (매일 18:00), 노쇼 후 24h 리뷰 요청
- 이용대 응대: 카카오 알림톡 자동회신 + 한 단계 에스컬레이션
- 최분석 KPI 측정 시작일: 운영 시작 +7일부터

## 6. 위험 신호
- (예: 시술 메뉴 중 회색지대 1건, 정총괄 검수 후 결정)

HANDOFF
- 다음 담당: 05_coordinator_qa
- 넘길 자료: 본 패키지, 위험 신호 카드(JSON), 정기 작업 인계서(JSON), 응대 톤 카드
- 확인 필요: (확인 필요 항목 목록)
- 하드 스톱: (있다면 명시, 없으면 "없음")
- 추천 액션: PROCEED / REVIEW / HOLD
```

---

## 2) 위험 신호 카드 (JSON)

```json
{
  "case_id": "CLI-2026-XXX",
  "industry": "치과",
  "risk_signals": [
    {
      "category": "scope",
      "level": "medium",
      "note": "시술 메뉴에 일반 관리와 의료 행위 혼재 가능성"
    }
  ],
  "blocking": false,
  "requires_human_approval": false,
  "next_owner": "05_coordinator_qa"
}
```

---

## 3) 정기 작업 인계서 (JSON, 박실행용)

```json
{
  "case_id": "CLI-2026-XXX",
  "tasks": [
    {
      "task_code": "OPS-REMIND-D-1",
      "schedule_cron": "0 18 * * *",
      "channel": "kakao_alimtalk",
      "idempotency_key_pattern": "remind-{case_id}-{appointment_id}-D1",
      "payload_template_id": "REMIND_D1_KO",
      "dry_run_until": "2026-XX-XX"
    }
  ],
  "owner": "02_ops_operator",
  "review_owner": "05_coordinator_qa"
}
```

---

## 4) 응대 톤 카드 (Markdown, 이용대용)

```markdown
TONE CARD - CLI-2026-XXX (샘플치과)

- 호칭: "원장님" / 고객 측 응대자 직급 사용
- 톤: 정중·간결, 의료 안내 톤 금지 (예약/일정/결제 한정)
- 금지 표현: 진료 결과, 치료 효과, 의약 효능, 가격 확정
- 즉시 에스컬레이션 키워드: "환불", "변호사", "고소", "진단", "처방", "보험"
- VIP 여부: 일반
```

---

## 핸드오프 매트릭스

| 산출물 | 다음 담당 | 채널 |
| --- | --- | --- |
| 온보딩 패키지 | 05_coordinator_qa | `agents/05_coordinator_qa/inbox.md` |
| 정기 작업 인계서 | 02_ops_operator | `agents/02_ops_operator/inbox.md` (QA 통과 후) |
| 응대 톤 카드 | 03_cs_manager | `agents/03_cs_manager/memory.md` 갱신 (QA 통과 후) |
| KPI 측정 시작 통지 | 04_data_analyst | `agents/04_data_analyst/inbox.md` (QA 통과 후) |
