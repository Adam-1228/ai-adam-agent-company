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

---

## 채널 운영 신호 (v2 canonical)

canonical 계약 `shared/handoff_contracts/commerce_client_ops_contract.md`는 `2026-05-22.v2`로 승격되었고, 다음 4가지 채널 운영 신호를 포함한다. 본 문서는 client-ops 팀의 운영 해석과 SOP 연결을 보완한다.

운영 절차 상세: `shared/channel_ops_sop.md`. 가입 준비 상세: `shared/seller_account_readiness.md`.

### 신호 1: `channel_submission_ready` (commerce → us)

| 항목 | 값 |
| --- | --- |
| 방향 | commerce → client-ops |
| 출발 에이전트 | commerce 05 ops_manager (stage 5 산출) |
| 수신 에이전트 | 05_coordinator_qa |
| 트리거 | stage 5에서 `approval_status == "adam_approval_required"` 패키지 생성 |
| 자동 동작 금지 | 정총괄 검수 전 Adam에게 직접 전달 금지 |
| SLA | 인입 후 4시간 이내 1차 검수 결정 |

페이로드 (제안):

```json
{
  "contract_version": "2026-05-22.v2",
  "handoff_id": "COM-COPS-2026-W21-channel-001",
  "direction": "commerce_to_client_ops",
  "signal_type": "channel_submission_ready",
  "summary": "Coupang 패키지 1건 + Amazon 패키지 1건, Adam 승인 대기",
  "requires_human_approval": true,
  "dry_run_only": true,
  "payload": {
    "run_id": "RUN-20260522-093000",
    "opportunity_id": "ADAM-OPP-0042",
    "package_paths": [
      "teams/commerce-agent-team/runtime/channel_submissions/pending/RUN-20260522-093000_ADAM-OPP-0042_coupang.json",
      "teams/commerce-agent-team/runtime/channel_submissions/pending/RUN-20260522-093000_ADAM-OPP-0042_amazon.json"
    ],
    "validation_status": "draft_validated_locally",
    "approval_status": "adam_approval_required",
    "risk_review": {"blocked": false, "notes": "no hard stop"},
    "forbidden_claims_present": false,
    "supplier_evidence_present": true,
    "category_match_seller_scope": true
  }
}
```

거절 사유 카탈로그: `channel_ops_sop.md §4.3` (R001~R007).

### 신호 2: `seller_account_blocker` (us → commerce)

| 항목 | 값 |
| --- | --- |
| 방향 | client-ops → commerce |
| 출발 에이전트 | 05_coordinator_qa (필요 시 01_onboarding_manager 협력) |
| 수신 에이전트 | commerce 05 ops_manager + commerce 03 risk_guardian |
| 트리거 | 셀러 계정 정지·제재 / API 키 권한 부족·만료 / 신규 카테고리 신청 미완료 / 법적 이슈 |
| SLA | 발견 즉시 (Telegram 5분 + 패킷 30분) |
| 자동 동작 금지 | 실 API 키 값 노출 금지 (존재 여부와 권한 부족 유형만 기록) |

페이로드 (제안):

```json
{
  "contract_version": "2026-05-22.v2",
  "handoff_id": "COPS-COM-2026-W21-blocker-001",
  "direction": "client_ops_to_commerce",
  "signal_type": "seller_account_blocker",
  "summary": "Coupang 셀러 권한 부족 - listing write 미허가",
  "severity": "high",
  "payload": {
    "channel": "coupang",
    "blocker_type": "permission_insufficient",
    "missing_permission": "listing.write",
    "discovered_at": "2026-05-22T10:30:00+09:00",
    "affected_opportunity_ids": ["ADAM-OPP-0042"],
    "remediation_owner": "Adam",
    "estimated_remediation_hours": 24,
    "do_not_disclose": ["api_key_value", "vendor_id_value"]
  }
}
```

`do_not_disclose` 필드는 절대 본값을 포함하지 않고 **필드명만** 기재한다.

### 신호 3: `post_publish_monitoring_request` (commerce → us)

| 항목 | 값 |
| --- | --- |
| 방향 | commerce → client-ops |
| 출발 에이전트 | commerce 05 ops_manager (stage 6 활성화 시점) |
| 수신 에이전트 | 04_data_analyst + 02_ops_operator + 05_coordinator_qa |
| 트리거 | Adam이 `APPROVE_AND_GO_LIVE` 결정 후 stage 6 활성화 |
| SLA | 게시 후 24시간 이내 KPI 측정 시작 |

페이로드 (제안):

```json
{
  "contract_version": "2026-05-22.v2",
  "handoff_id": "COM-COPS-2026-W21-monitor-001",
  "direction": "commerce_to_client_ops",
  "signal_type": "post_publish_monitoring_request",
  "summary": "ADAM-OPP-0042 Coupang 게시 후 1주 모니터링 요청",
  "payload": {
    "opportunity_id": "ADAM-OPP-0042",
    "sku": "ADAM-ADAM-OPP-0042",
    "channels_live": ["coupang"],
    "live_since": "2026-05-22T14:00:00+09:00",
    "metrics_to_track": [
      "views", "clicks", "orders_count", "revenue_indexed",
      "returns_count", "negative_review_count", "claim_count"
    ],
    "baseline_period": "no_baseline_first_week",
    "report_cadence": "daily_first_7_days_then_weekly",
    "client_ops_routes": ["04_data_analyst", "02_ops_operator"]
  }
}
```

### 신호 4: `refund_or_claim_escalation` (us → commerce)

| 항목 | 값 |
| --- | --- |
| 방향 | client-ops → commerce |
| 출발 에이전트 | 05_coordinator_qa (이용대 03 P0 인입 → 정총괄 → commerce) |
| 수신 에이전트 | commerce 03 risk_guardian + commerce 05 ops_manager |
| 트리거 | 환불 ≥ 3건/7일 / A-to-z Claim / Chargeback / 동일 SKU 채널 제재 |
| SLA | 임계 충족 즉시 |
| 자동 동작 금지 | 고객 식별정보 일체 금지. 케이스 ID·집계·카테고리만 |

페이로드 (제안):

```json
{
  "contract_version": "2026-05-22.v2",
  "handoff_id": "COPS-COM-2026-W21-claim-001",
  "direction": "client_ops_to_commerce",
  "signal_type": "refund_or_claim_escalation",
  "summary": "ADAM-OPP-0042 (Coupang) 환불 5건/7일 임계 도달",
  "severity": "high",
  "payload": {
    "opportunity_id": "ADAM-OPP-0042",
    "channel": "coupang",
    "trigger_type": "refund_threshold_5_in_7d",
    "claim_breakdown": {
      "size_mismatch": 2,
      "quality_complaint": 2,
      "shipping_damage": 1
    },
    "case_ids_anonymized": ["CASE-A1", "CASE-A2", "CASE-A3", "CASE-A4", "CASE-A5"],
    "raw_customer_messages_included": false,
    "recommended_commerce_action": "review_catalog_or_exclude",
    "qa_decision": "ESCALATE_TO_ADAM",
    "qa_owner": "05_coordinator_qa"
  }
}
```

### v2 검증 매트릭스 (preflight_check.py §13)

본 4가지 신호의 운영 가능 여부는 다음을 통해 자동 점검된다.

| 항목 | 자동화 | 점검 명령 |
| --- | --- | --- |
| 4가지 신호가 본 파일에 정의됨 | AUTO | `python scripts/preflight_check.py --section 13` |
| `channel_ops_sop.md`와 정합 | AUTO | 동일 명령 |
| `seller_account_readiness.md` 존재 | AUTO | 동일 명령 |
| v2 canonical 승격 | AUTO | `shared/handoff_contracts/commerce_client_ops_contract.md` version `2026-05-22.v2` 확인 |
| 실 API 키 grep | AUTO | `python scripts/preflight_check.py --section 1` (기존 §1.3) |
