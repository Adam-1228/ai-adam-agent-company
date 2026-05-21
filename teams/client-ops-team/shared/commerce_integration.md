# Commerce Integration

This file defines how `client-ops-team` and `commerce-agent-team` cooperate.

## Client Ops -> Commerce

Client Ops may send:

- anonymized industry demand signals
- recurring customer questions
- no-show, review, and repeat-purchase patterns
- anonymized service package ideas

Client Ops must not send:

- customer names
- phone numbers or emails
- contracts
- raw chat/email bodies
- medical, legal, tax, or payment details

## Commerce -> Client Ops

Commerce may send:

- product opportunity summaries
- risk-reviewed listing drafts
- category trend notes
- human-approval requests

Commerce must not ask Client Ops to:

- promise revenue
- impersonate a customer
- post marketplace listings without approval
- reuse third-party images or page text

---

## 한국어 상세

### 두 팀의 관계 (한 줄)

`commerce-agent-team`은 무엇을 팔 수 있는지를 발굴/검수하고, `client-ops-team`은 운영 고객과 회사 시스템 사이의 일상을 책임진다. 둘은 같은 모노레포에 있지만 책임 라인은 분리되어 있다.

### 정총괄 = 양방향 게이트

우리 팀에서 커머스 팀으로 나가는 모든 자료는 **정총괄 게이트**를 거친다. 반대 방향(커머스 → 우리)도 정총괄이 받아서 5명에게 배포한다. 직접 채널 없음.

### 우리 → 커머스로 보낼 수 있는 자료

- 업종별 / 주차별 익명 집계 (`shared/handoff_to_commerce.md` 양식)
- 운영 현장에서 본 신규 자동화 후보 (예: "치과 업종에서 노쇼 24h 사전 콜이 효과 있어 보임 — A/B 권고")
- 시장 시그널 (예: "5월 가정의 달 직후 결제 분쟁 인입 +30%")
- 우리 팀 운영 정책의 변경 (커머스 팀이 알아야 할 응대 톤·금지 표현 등)

### 우리 → 커머스로 보내면 안 되는 자료

- 고객사 실명, 실주소, 대표자명
- 응대 본문 풀텍스트
- 계약 조건, 결제 금액 절대값
- 의료/법률/세무 컨텍스트
- 케이스 단위 식별 가능한 횡단 데이터 (반드시 업종/주차 집계)

### 커머스 → 우리로 받을 수 있는 자료

- 신규 상품/카탈로그 (운영 고객에게 안내 시점·문구 권고 동반)
- 시장 트렌드 노트 (운영 응대 톤 보강 입력)
- 리스크 검수 결과 (특정 카테고리 회피 권고)
- Adam 승인 필요 사항 (정총괄 경유 후 Adam에게)

### 커머스 → 우리에게 요구하면 안 되는 것

- 매출 보장, 성과 보장
- 고객을 가장한 응대
- 사람 승인 없는 외부 발송
- 타사 이미지/문구 재사용
- 운영 시스템에 카탈로그 직접 쓰기 권한

### 갱신 주기

- 우리 → 커머스: 매주 월 12:00 (최분석 익명 집계 + 정총괄 검수 통과 후)
- 커머스 → 우리: ad-hoc (커머스 팀 일정에 따름, 정총괄이 받음)
- 본 통합 문서 변경: 양 팀 합의 + Adam 승인
