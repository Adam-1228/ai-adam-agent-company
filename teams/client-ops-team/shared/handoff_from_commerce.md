# Handoff From Commerce

```text
HANDOFF ID:
FROM: commerce-agent-team
TO:
CREATED AT:

COMMERCE SIGNAL:
- Product/category:
- Target market:
- Risk level:
- Suggested action:

CLIENT OPS USE:
- Onboarding note
- CS talking point
- Weekly report insight
- Adam approval request

GUARDRAILS:
- No revenue promise.
- No automatic customer-facing publication.
- Human approval required before external action.
```

---

## 한국어 상세 (받을 수 있는 신호 + 받았을 때의 처리)

커머스 팀이 우리 팀에 보낼 수 있는 신호는 4가지로 한정한다.

### 1. 신규 자동화 후보

운영 응대/실행을 통해 자동화할 수 있는 후보 (예: "리뷰 요청 시점을 24h → 48h로 늦추는 게 응답률이 높다").

- 수신자: 김은보 (운영 정책 갱신) + 박실행 (스케줄 변경)
- 정총괄 검수 후 적용. A/B 테스트 권고.
- 절대 자동 적용 금지.

### 2. 시장 트렌드

(예: "5월 알레르기 관련 검색 +40%, 치과·이비인후과 인입 증가 가능성")

- 수신자: 최분석 (베이스라인 보강) + 이용대 (응대 톤 준비)
- 단정형 채택 금지. 가설로만 메모리에 기록.

### 3. 신규 카탈로그 / 상품

(예: 커머스 팀이 새로 검수 완료한 상품을 우리 운영 고객 일부에 안내 권고)

- 수신자: 정총괄 → Adam (**6대 케이스 중 "신규 카탈로그"**)
- Adam 승인 없이 운영 고객에게 안내 금지.
- Adam 승인 후: 김은보가 안내 톤 카드 작성 → 이용대가 정형 문구만 사용.

### 4. 리스크 검수 결과

(예: 특정 카테고리/업종 회피 권고, 인증 리스크 관찰)

- 수신자: 김은보 (온보딩 거절 조건 갱신) + 정총괄 (운영 정책 보강)
- 즉시 반영. 진행 중 케이스 영향 시 정총괄 회고 대상.

### 받았을 때 절대 하지 않는 것

- 매출 보장 / 성과 보장 응대
- 고객을 가장한 응대
- 사람 승인 없는 외부 발송
- 타사 이미지/문구를 우리 톤 카드에 그대로 복사
- 받은 신호의 단정형 채택 ("효과 있다" 그대로 인용 금지)

### 수신 → 배포 흐름

```text
commerce-agent-team
  → 05 정총괄 (수신 게이트)
  → 카테고리에 따라 01/02/03/04에게 분배
  → 6대 케이스(신규 카탈로그)는 Adam에게
  → 적용 결과 → 정총괄 → 다음 주 회고
```

### 수신 양식 예시 (JSON)

```json
{
  "handoff_id": "COMMERCE-TO-C-OPS-2026-W21-003",
  "from": "commerce-agent-team",
  "to": "client-ops-team",
  "created_at": "2026-05-26T14:00:00+09:00",
  "signal_type": "new_automation_candidate",
  "subject": "치과 업종 리뷰 요청 발송 시점 (24h → 48h) A/B 권고",
  "evidence_ref": "commerce/reports/2026-W21-pet-noshow.md",
  "client_ops_route": ["02_ops_operator", "01_onboarding_manager"],
  "requires_human_approval": false,
  "review_owner": "05_coordinator_qa"
}
```
