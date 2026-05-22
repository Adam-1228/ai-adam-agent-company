# Channel Ops SOP (Coupang / Amazon)

판매자 계정 가입부터 게시 후 클레임 처리까지의 운영 표준 절차다. 이 문서는 commerce-agent-team의 `commerce_growth_pipeline.py` (six-stage)와 맞물려 동작한다.

## 0. 책임 라인 (한 문장 요약)

- **commerce-agent-team**은 무엇을 팔지·어떻게 리스팅할지를 결정한다.
- **client-ops-team**은 그 결정이 안전하게 게시되는지·게시 후 운영이 정상인지를 책임진다.
- **Adam**은 모든 채널 게시의 최종 게이트이며, 6대 케이스(가격/계약/법적/30분 장애/신규 카탈로그/신규 LLM)의 결정자다.
- **정총괄(05)**은 commerce → client-ops로 들어오는 모든 채널 관련 산출물의 1차 검수자다.

## 1. 게시 전 Adam 승인 절차

### 1.1 commerce-agent-team 산출물 수신

Codex의 `commerce_growth_pipeline.py` stage 5가 `runtime/channel_submissions/pending/{run_id}_{candidate_id}_{channel}.json`을 생성한다. 각 패키지는 다음 상태 중 하나로 도착한다.

| `approval_status` | 의미 | 우리 측 행동 |
| --- | --- | --- |
| `adam_approval_required` | 위험 검수 통과, 사람 승인 대기 | 정총괄 1차 검수 → Adam 큐 |
| `blocked` | 위험 검수 차단 (인증/IP/이미지/마진) | 정총괄 거절 사유 1줄 + commerce에 회신 |

### 1.2 정총괄 1차 검수 (Adam에게 가기 전)

정총괄은 다음을 모두 통과한 패키지만 Adam에게 올린다. 하나라도 실패 시 commerce 팀에 `rejected_for_info`로 반려.

```text
[ ] payload.mode 필드가 "draft_only_requires_adam_approval"(Coupang) 또는
    "validation_preview_only_requires_adam_approval"(Amazon)로 명시되어 있다
[ ] payload.content.risk_review.blocked == false
[ ] payload.content.supplier_evidence가 비어있지 않다
[ ] payload.content.image_brief가 우리 권리 안의 자산만 참조한다 (타사 이미지/문구 재사용 0건)
[ ] payload.content.faq에 "환불", "변호사", "의료 자문" 등 P0 키워드가 들어가지 않는다
[ ] payload.content.description에 "성과 보장", "100% 효과" 등 forbidden_claims가 없다
[ ] sellerProductName / sku 가 `seller_account_readiness.md`의 카테고리 신청 범위 안에 있다
```

검사 통과 시 결정문:

```json
{
  "qa_id": "QA-YYYY-MM-DD-NNN",
  "subject": "channel_submission",
  "package_path": "teams/commerce-agent-team/runtime/channel_submissions/pending/...",
  "decision": "ESCALATE_TO_ADAM",
  "reason": "draft validated, no blocking risk, no forbidden claims",
  "confidence": "high",
  "next_owner": "Adam",
  "telegram_notified_at": "..."
}
```

### 1.3 Adam의 결정

Adam이 큐의 패키지를 검토하고 다음 중 하나로 결정한다.

| Adam 결정 | 후속 |
| --- | --- |
| `APPROVE_DRAFT_KEEP_DRYRUN` | Codex가 stage 5 결과를 보존, 실제 게시는 별도 명령으로 |
| `APPROVE_AND_GO_LIVE` | 운영자가 `DRY_RUN=false` 전환 + 실제 채널 게시 명령 실행 |
| `HOLD` | 정총괄에게 보류 사유 회신, commerce에 `collaboration_request` 보냄 |
| `REJECT` | 폐기, commerce에 `rejected_for_info` 보냄 |

**중요:** 본 SOP 시점에서 모든 채널은 `DRY_RUN=true`가 기본. `APPROVE_AND_GO_LIVE`는 Adam이 명시적으로 결정해야 하며 운영자가 다음 명령으로 게시:

```bash
# Adam 승인 후에만 실행. 운영자는 EC2 콘솔에서 직접 입력.
cd teams/commerce-agent-team
# (실제 게시 스크립트는 Codex가 별도로 제공. 본 SOP는 호출만 정의.)
```

### 1.4 게시 직후 우리 측 액션

- 김은보(01): 해당 SKU를 "신규 셀러 케이스"로 온보딩 패키지화 (`ONB-PACKAGE`)
- 박실행(02): 재고 동기, 가격 변경 알림 작업 명세 등록 (단, 첫 1주는 DRY_RUN 유지)
- 이용대(03): 톤 카드에 해당 채널·SKU별 자동응답 패턴 추가
- 최분석(04): 성과 KPI 측정 시작 (`ANL-CASE-LAUNCH`, baseline 4주 전 없음 → "현상 보고")
- 정총괄(05): 첫 1주간 모든 채널 메시지 인입에 대한 응대를 사후 검수 격상

## 2. 게시 후 CS / 환불 / 반품 / 클레임 처리

### 2.1 인입 채널

| 채널 | 인입 경로 | 우리 측 수신자 |
| --- | --- | --- |
| Coupang 고객 문의 | WING 셀러 메시지함 → webhook | 이용대(03) `inbox.md` |
| Coupang 클레임/반품 | WING 클레임 센터 → 별도 큐 | 이용대(03) + 정총괄(05) |
| Amazon Buyer-Seller Messaging | SP-API messaging → webhook | 이용대(03) (Amazon은 24h SLA 강제) |
| Amazon A-to-z Guarantee Claim | SP-API + Seller Central | 이용대(03) + 정총괄(05) + Adam |
| Amazon Negative Feedback / Review | Seller Central | 최분석(04) (집계) + 이용대(03) (필요 시 회신) |

### 2.2 자동 분류

이용대(03)의 `policy_check`(`run_agent.py` 내장)가 인입 메시지에 대해 다음 분기한다.

```text
P0 (자동 응답 절대 금지 → 즉시 정총괄 → Adam)
  - 환불, 환급, 결제 취소, 카드 분쟁, 챠지백
  - 변호사, 고소, 소송, 신고, 민원, 공정위
  - 진단, 처방, 부작용, 의약품, 의료기기
  - 주민번호, 카르테, 진료기록
  - 자해, 자살, 협박, 폭언
  - A-to-z Guarantee Claim filed (Amazon 전용)
  - Chargeback initiated (Coupang/Amazon 공통)

P1/P2 (사람 검수 후 응대)
  - 반품 요청 (정상 사유)
  - 배송 지연 클레임
  - 색상/사이즈 상이
  - 사용법 문의

P3 (자동 응답, 사후 샘플 검수)
  - 영업시간 / 배송 조회
  - 일반 FAQ
  - "잘 받았어요" 류 인사
```

### 2.3 환불 / 반품 처리 흐름

```text
1. 고객 인입 (Coupang/Amazon 메시지)
   ↓
2. 이용대(03) policy_check
   ↓
3-A. P0 환불 키워드 감지
     → 자동 응답 안 함
     → 정총괄(05) `QA-CS-P0`로 에스컬레이션 카드 발행
     → 정총괄이 Adam에 Telegram 통지 (5분 이내)
     ↓
4-A. Adam 결정
     - APPROVE_REFUND   → 운영자가 채널 콘솔에서 직접 환불 처리 (자동화 X)
     - PARTIAL_REFUND   → 운영자가 직접 처리, 사유 commerce 팀에 공유
     - DENY_REFUND      → 정총괄이 응대 초안 작성, 채널 클레임 절차 안내
     - ESCALATE_TO_LEGAL → 변호사 자문, commerce에 `seller_account_blocker` 발행
     ↓
5-A. 결과를 commerce에 `refund_or_claim_escalation` 신호로 전달
     (해당 SKU에 동일 사유 클레임이 누적되면 commerce가 카탈로그에서 제외 판단)

3-B. P1 정상 반품 요청
     → 이용대(03) 응대 초안 작성
     → 정총괄(05) 검수 통과 시 발송
     → 박실행(02) 환불/반품 알림 작업은 자동화 X (사람 처리)
     → 최분석(04) 주간 집계에 반품률 추가
```

### 2.4 동일 SKU 클레임 누적 임계값

| 임계 | 액션 |
| --- | --- |
| 동일 SKU 환불 ≥ 3건 / 7일 | 정총괄이 commerce에 `refund_or_claim_escalation` 발행 (severity=medium) |
| 동일 SKU 환불 ≥ 5건 / 7일 | Adam에 6대 케이스 알림 (해당 카탈로그 일시 중단 결정) |
| Amazon A-to-z Claim 발생 | severity=high 즉시 발행, Account Health 영향 가능 |
| Chargeback 발생 | severity=critical 즉시 발행, 변호사 자문 검토 |

## 3. P0 Escalation 조건 (총정리)

이용대(03)의 자동 응답이 절대 발생하지 않아야 할 케이스. 모두 정총괄(05) 경유로 Adam에게.

### 3.1 메시지 키워드 (`run_agent.P0_ESCALATION_KEYWORDS`)

기존 9개 트리거 (`preflight_check.py §7` 검증):
환불, 변호사, 고소, 소송, 진단, 처방, 주민번호, 자살, 협박.

### 3.2 채널 시스템 신호 (이번 SOP에서 추가 정의)

| 트리거 | 채널 | severity |
| --- | --- | --- |
| Coupang WING - 위반/제재 알림 | Coupang | critical |
| Coupang WING - 셀러 등급 하향 | Coupang | high |
| Coupang - 카탈로그 강제 제거 | Coupang | high |
| Amazon - A-to-z Guarantee Claim filed | Amazon | critical |
| Amazon - Account Health Rating 하향 | Amazon | critical |
| Amazon - Listing suppressed / suspended | Amazon | high |
| Amazon - Intellectual Property Complaint | Amazon | critical |
| Chargeback initiated (둘 다) | both | critical |

이 신호들은 이용대(03)의 인입 분류기에서 별도로 감지되어야 한다 (현재 v0.3까지는 텍스트 키워드만 감지 — 후속 PR에서 채널 webhook 수신부 추가 시 구현).

### 3.3 누적 임계 (위 §2.4)

3건/7일, 5건/7일, A-to-z, Chargeback.

## 4. Commerce → Client Ops Channel Submission 검수 규칙

본 절은 `shared/handoff_contracts/commerce_client_ops_contract.md` (v1)의 `Commerce → Client Ops` 섹션을 보완한다. v1에는 명시되지 않은 채널 패키지 검수를 본 SOP가 정의한다 (v2 계약 협의 시 canonical로 승격 권고).

### 4.1 수신 패키지 식별

commerce stage 5가 생성한 패키지는 다음 위치에 떨어진다:

```
teams/commerce-agent-team/runtime/channel_submissions/pending/{run_id}_{candidate_id}_{channel}.json
```

본 저장소(client-ops)에서는 패키지를 **읽기 전용**으로 접근. 직접 쓰지 않음.

### 4.2 검수 단계

```text
A. 정총괄(05)이 `commerce_growth_pipeline.py` 실행 직후 알림 수신
   (현재 v0.3까지는 폴링 또는 수동. v0.4+에서 file-watcher 가능)
   ↓
B. 위 §1.2 7개 체크리스트 실행
   ↓
C. 통과 → Adam 에스컬레이션 카드 발행 (`QA-ADAM-ESCALATION`)
   거절 → commerce에 `rejected_for_info` 회신
```

### 4.3 정총괄 자동 검수 거절 사유 카탈로그

| 사유 코드 | 조건 |
| --- | --- |
| `R001_BLOCKED_BY_RISK` | `payload.content.risk_review.blocked == true` |
| `R002_NO_SUPPLIER_EVIDENCE` | supplier_evidence 비어있음 |
| `R003_THIRD_PARTY_ASSET` | image_brief가 타사 자산 참조 |
| `R004_FORBIDDEN_CLAIMS` | description/title에 forbidden_claims 매치 |
| `R005_PII_LEAK` | payload 어디든 PII 패턴 매치 (전화/이메일/주민번호) |
| `R006_DRY_RUN_NOT_DECLARED` | mode 필드에 `requires_adam_approval` 미명시 |
| `R007_CATEGORY_OUT_OF_SCOPE` | 셀러 가입 시 신청한 카테고리 외 |

각 거절은 commerce 팀의 해당 `run_id`와 함께 1줄 회신.

## 5. 4가지 신규 신호 (handoff_contract 후보)

본 SOP는 `commerce_integration.md`에 추가될 다음 4가지 신호의 운영 절차를 정의한다.

### 5.1 `channel_submission_ready` (commerce → us)

- **트리거**: stage 5 완료, `approval_status == "adam_approval_required"`
- **수신자**: 05 정총괄
- **SLA**: 인입 후 4시간 이내 1차 검수 결정
- **본 SOP 참조**: §1.2, §4

### 5.2 `seller_account_blocker` (us → commerce)

- **트리거**: 우리 측에서 다음 중 하나 발견:
  - 셀러 계정이 정지/제재
  - API 키 권한 부족 또는 만료
  - 신규 카테고리 신청 미완료
  - 법적 이슈 (변호사 자문 진행 중)
- **수신자**: commerce 02 / 05
- **SLA**: 발견 즉시 (5분 이내 Telegram + 패킷)
- **결과**: commerce는 해당 SKU의 stage 5 진행 중단

### 5.3 `post_publish_monitoring_request` (commerce → us)

- **트리거**: Adam이 `APPROVE_AND_GO_LIVE` 결정 후 stage 6 활성화
- **수신자**: 04 최분석 + 02 박실행 + 05 정총괄
- **SLA**: 게시 후 24시간 이내 KPI 측정 시작
- **본 SOP 참조**: §1.4 (게시 직후 우리 측 액션)

### 5.4 `refund_or_claim_escalation` (us → commerce)

- **트리거**: 위 §2.4 임계 충족 또는 P0 채널 신호
- **수신자**: commerce 03 risk_guardian + 05 ops_manager
- **SLA**: 임계 충족 즉시
- **결과**: 해당 SKU의 카탈로그 일시 중단 또는 영구 제외 판단

## 6. 검증 (preflight_check.py §13)

본 SOP의 자동 점검 가능 항목은 `preflight_check.py --section 13`에서 다음을 확인한다.

- `shared/seller_account_readiness.md` 존재 + 핵심 섹션
- `shared/channel_ops_sop.md` 존재 + 핵심 섹션
- 4가지 신규 신호가 `shared/commerce_integration.md`에 명시됨
- 어떤 실값(사업자번호, 계좌, 키)도 `shared/`나 `config/`에 grep으로 검출되지 않음

수동 점검 항목:

- 실제 셀러 가입 완료 여부 → SKIP_MANUAL
- 실제 API 키 발급 여부 → SKIP_MANUAL (존재 여부만 환경변수로 확인, 값은 절대 출력 안 함)
- 실제 정산 계좌 등록 → SKIP_MANUAL
- Adam의 첫 `APPROVE_AND_GO_LIVE` 결정 → SKIP_MANUAL

## 7. 관련 문서

- `shared/seller_account_readiness.md` — 채널별 가입 필드 + 민감정보 보관 규칙
- `shared/commerce_integration.md` — 4가지 신규 신호의 정식 정의
- `shared/handoff_contract.md` — 5명 ↔ 5명 매트릭스
- `shared/pre_launch_checklist.md §13` — 본 SOP 자동 점검 매핑
- `shared/handoff_contracts/commerce_client_ops_contract.md` (root, read-only) — v1 canonical (4가지 신호는 v2 협의 대상)
- `teams/commerce-agent-team/scripts/commerce_growth_pipeline.py` (read-only) — six-stage 발생원
