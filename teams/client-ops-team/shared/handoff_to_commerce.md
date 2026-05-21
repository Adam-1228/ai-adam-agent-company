# Handoff To Commerce

```text
HANDOFF ID:
FROM:
TO: commerce-agent-team
CREATED AT:

ANONYMIZED SIGNAL:
- Industry:
- Region or market:
- Time window:
- Pattern:

EVIDENCE:
- Aggregated counts only.
- No raw customer messages.

REQUEST:
- Product discovery
- Listing idea
- Risk review
- Pricing research

RISK NOTES:
- Personal data removed:
- Legal/medical/tax content removed:
- Confidence:
```

---

## 한국어 상세 (PII 제거 + 업종/주차 단위 집계)

우리 팀에서 커머스 팀으로 넘기는 모든 자료는 다음 조건을 만족해야 한다.

### PII 제거 체크리스트

- 고객사 실명 / 대표자명 / 담당자명 → 케이스ID 또는 업종 라벨로 치환
- 전화번호, 이메일, 주소 → 완전 제거
- 사업자번호 → 완전 제거 (마스킹 4자리도 안 됨)
- 응대 본문 → 카테고리 라벨로 치환 (예: "예약 변경 문의 — 정책 외 시점")
- 결제 금액 절대값 → 지수 또는 베이스라인 대비 비율로 치환
- 의료/법률/세무 단어 → 카테고리만 ("의료 자문성 문의 N건"), 본문 인용 금지

### 집계 단위

- **업종 단위**: 최소 표본 5케이스 이상. 5 미만 업종은 제외 또는 "기타" 묶음.
- **시간 단위**: 주차 (ISO Week). 일 단위 송부 금지.
- **지역 단위**: 시/도 수준까지. 동/번지 금지.

### 송부 양식 예시 (JSON)

```json
{
  "handoff_id": "C-OPS-TO-COMMERCE-2026-W21",
  "from": "client-ops-team",
  "to": "commerce-agent-team",
  "created_at": "2026-05-26T12:00:00+09:00",
  "week": "2026-W21",
  "signals": [
    {
      "industry": "치과",
      "region": "서울",
      "metric": "noshow_rate",
      "value_indexed": 0.92,
      "baseline_period": "2026-W17..W20",
      "sample_size_cases": 6,
      "confidence": "medium"
    }
  ],
  "qualitative_notes": [
    "치과 업종에서 D-1 18:00 리마인더 대비 D-1 20:00 발송이 노쇼율 낮은 경향 관찰됨. 단정 아님. A/B 권고."
  ],
  "pii_check": {
    "names_removed": true,
    "contacts_removed": true,
    "business_ids_removed": true,
    "raw_messages_removed": true,
    "amounts_indexed": true,
    "medical_legal_tax_only_as_category": true
  },
  "review": {
    "owner": "05_coordinator_qa",
    "decision": "PASS",
    "decision_reason": "PII 체크리스트 전 항목 충족, 표본 ≥ 5 업종만 포함."
  }
}
```

### 거절 조건 (정총괄이 거절한다)

- PII 체크리스트 1개라도 false
- 표본 < 5 업종이 포함됨
- 결정문 또는 결정 사유 누락
- 정성 노트에 단정 표현 ("효과 있다", "줄어든다") 사용
- 일 단위 또는 케이스 단위 데이터 포함

### 송부 채널

정총괄 PASS 후 `teams/commerce-agent-team/workforce/shared/inbox/` 또는 별도 합의 경로. v0.1에서는 양 팀 합의 경로 미정, 정총괄이 ad-hoc 결정.
