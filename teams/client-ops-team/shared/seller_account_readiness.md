# Seller Account Readiness Checklist

판매자 계정과 채널 API 키가 아직 발급되지 않았더라도, 정산·반품·CS·개인정보 등 **계정 준비 전후의 모든 점검 항목**을 정의한다.

이 문서는 어떤 필드가 필요한지·어디에 보관해야 하는지의 **메타데이터**만 담는다. 실값(사업자번호, 계좌번호, 대표자명, API 키, 토큰)은 절대 본 저장소에 포함하지 않는다.

## 1. 공통 준비 항목 (Coupang + Amazon)

### 1.1 사업자/법인 정보 (제출 전 검증 필수)

| 항목 | 필요 시점 | 보관 위치 | 본 저장소 커밋 |
| --- | --- | --- | --- |
| 사업자등록증 사본 | 채널 가입 신청 | 외부 secure storage (회사 1Password / EC2 암호화 볼륨) | ❌ 절대 금지 |
| 대표자 성명 / 주민번호 (또는 사업자번호) | 가입 + KYC | 외부 secure storage | ❌ 절대 금지 |
| 통신판매업 신고증 (Coupang) | 채널 가입 | 외부 secure storage | ❌ 절대 금지 |
| 미국 W-9 / W-8BEN (Amazon US) | Amazon Seller 등록 | 외부 secure storage | ❌ 절대 금지 |
| 사업장 주소 | 가입 폼 입력 | 외부 secure storage | ❌ 절대 금지 |

검증 항목 (자동화 가능):

- [ ] 사업자등록증의 업태/업종이 우리가 다룰 카테고리와 일치하는가
- [ ] 통신판매업 신고 시 등재한 취급 품목이 commerce-agent-team이 발굴한 카테고리와 일치하는가
- [ ] 대표자명·사업자번호가 결제 수단(법인카드/계좌)과 동일 명의인가

### 1.2 정산 정보

| 항목 | 채널 | 본 저장소 커밋 |
| --- | --- | --- |
| 정산 은행/계좌 (KRW) | Coupang | ❌ |
| 정산 은행/계좌 (USD or 글로벌) | Amazon | ❌ |
| 계좌 명의 (사업자 명의 필수) | 양 채널 | ❌ |
| Hyperwallet / Payoneer 계정 ID (Amazon) | Amazon | ❌ |
| VAT 등록번호 (Amazon EU/UK 진출 시) | Amazon | ❌ |

검증 항목:

- [ ] 정산 계좌 명의 = 사업자 명의 (개인 명의 사용 금지)
- [ ] 환율·수수료가 마진 계산에 반영되어 있는가 (commerce-agent-team `02_margin_analyst`)

### 1.3 반품지 정보

| 항목 | 본 저장소 커밋 |
| --- | --- |
| 반품 수령 주소 (실주소) | ❌ |
| 반품 수령 담당자 연락처 (실번호) | ❌ |
| 반품 수령 가능 시간대 | ✅ (가상 예시만, 예: "평일 10:00-17:00") |
| 반품 운임 부담 정책 | ✅ (정책만, 실값 아님) |

검증 항목:

- [ ] 반품지가 사업자 주소와 동일한가 (다르면 통신판매업 신고서에 별도 표기 필요)
- [ ] 반품 운임 정책이 `channel_ops_sop.md`의 SOP와 일치하는가

### 1.4 CS 연락처

| 항목 | 본 저장소 커밋 |
| --- | --- |
| CS 대표 전화번호 | ❌ |
| CS 대표 이메일 | ❌ (실주소 금지, `support@<our-domain>` 같은 별칭만 메타 기록) |
| CS 운영 시간 | ✅ (가상 예시 가능) |
| 휴무일/공휴일 정책 | ✅ |

검증 항목:

- [ ] CS 전화/이메일이 `03_cs_manager` 톤 카드와 응대 채널이 일치하는가
- [ ] 채널이 제공하는 셀러 메시지함(Coupang WING, Amazon Buyer-Seller Messaging)에 응답 SLA가 합의되어 있는가 (Amazon은 24시간 룰)

### 1.5 배송 정책

| 항목 | 메모 |
| --- | --- |
| 출고 SLA (영업일 D+N) | `channel_ops_sop.md`와 정합 필요 |
| 사용 택배사 | Coupang은 자체 물류(로켓) vs 셀러 출고 선택. Amazon은 FBA vs FBM |
| 글로벌 배송 (Amazon) | 권장: 초기에는 단일 마켓(미국 또는 일본)부터 |
| 무료 배송 임계 금액 | `02_margin_analyst` 마진 계산과 정합 |

검증 항목:

- [ ] 배송 SLA가 통신판매 표시 광고법에 위반되지 않는가
- [ ] FBA 이용 시 inbound shipment 라벨링이 준비되었는가

### 1.6 개인정보 처리 기준

| 항목 | 메모 |
| --- | --- |
| 개인정보처리방침 페이지 URL | ✅ 메타만 (실 URL은 .env 또는 settings) |
| 개인정보 보호책임자 (CPO) 지정 | ❌ 실명 커밋 금지 — 직책만 기록 |
| 개인정보 보유 기간 | ✅ 정책만 |
| 제3자 제공 동의 (택배사) | ✅ 정책만 |
| 결제 정보 비저장 (PCI-DSS) | ✅ 정책 — 카드번호 우리 시스템에 절대 저장 안 함 |

검증 항목:

- [ ] 개인정보처리방침 페이지가 채널 가입 시 등록되었는가
- [ ] 통신판매업 신고 시 제출한 개인정보 처리방침과 채널 등록본이 동일한가
- [ ] `03_cs_manager` 톤 카드의 "주민번호/카르테/진료기록" 트리거가 채널 메시지에도 적용되는가 (`preflight_check.py §7`)

## 2. 채널별 추가 항목

### 2.1 Coupang (WING)

| 단계 | 항목 | 자동화 |
| --- | --- | --- |
| 가입 전 | 통신판매업 신고 완료 | MANUAL |
| 가입 전 | 사업자 인증 (DUNS 불요) | MANUAL |
| 가입 직후 | 셀러 ID 발급 → `.env`에 `COUPANG_VENDOR_ID` (값은 EC2에만) | MANUAL |
| API 키 발급 | Open API access_key / secret_key | MANUAL |
| 가입 후 점검 | "출고지", "반품지" 등록 완료 | MANUAL |
| 가입 후 점검 | 카테고리 신청서 (보석/식품 등 회색지대는 추가 서류) | MANUAL |
| 카탈로그 시험 | `mode=draft_only_requires_adam_approval` 으로 시뮬레이션 1회 | AUTO (`commerce-agent-team`이 stage 5에서 처리) |

본 저장소에 절대 커밋 금지 (변수명만 `.env.example`에, 실값은 EC2 `/opt/ai-adam-agent-company/teams/commerce-agent-team/.env`에만):

- `COUPANG_VENDOR_ID` 실값
- `COUPANG_ACCESS_KEY`, `COUPANG_SECRET_KEY`
- WING 로그인 비밀번호
- 통신판매업 신고증 PDF

변수명 집합은 `teams/commerce-agent-team/scripts/check_channel_readiness.py`의 `ENV_REQUIRED["coupang"]`과 정확히 1:1로 유지한다.

### 2.2 Amazon (Seller Central)

| 단계 | 항목 | 자동화 |
| --- | --- | --- |
| 가입 전 | DUNS 번호 발급 (법인) | MANUAL |
| 가입 전 | 신용카드 (대표자 명의) | MANUAL |
| 가입 전 | 세금 인터뷰 (W-8BEN, 한국 법인) | MANUAL |
| 가입 직후 | Marketplace 선택 (US/JP/EU 중 단일 진입 권장) | MANUAL |
| API 키 발급 | SP-API Refresh Token + AWS IAM Role | MANUAL |
| 가입 후 점검 | Brand Registry (자체 브랜드 보호 시) | MANUAL |
| 카탈로그 시험 | `mode=validation_preview_only_requires_adam_approval` | AUTO (`commerce-agent-team` stage 5) |

본 저장소에 절대 커밋 금지 (변수명만 `.env.example`에, 실값은 EC2 `/opt/ai-adam-agent-company/teams/commerce-agent-team/.env`에만):

- `AMAZON_SELLER_ID`, `AMAZON_MARKETPLACE_ID` 실값
- `AMAZON_SP_CLIENT_ID`, `AMAZON_SP_CLIENT_SECRET`
- `AMAZON_SP_REFRESH_TOKEN`
- `AMAZON_SP_AWS_ACCESS_KEY_ID`, `AMAZON_SP_AWS_SECRET_ACCESS_KEY`
- `AMAZON_SP_ROLE_ARN`
- W-8BEN 양식, DUNS 인증서

변수명 집합은 `teams/commerce-agent-team/scripts/check_channel_readiness.py`의 `ENV_REQUIRED["amazon"]`과 정확히 1:1로 유지한다. 추가/변경 시 양 팀 동시 갱신 (canonical 변경 PR + client-ops 본 문서 + `.env.example` + `preflight_check.py` CHANNEL_KEY_VARS).

## 3. API 키 발급 전후 체크리스트

### 3.1 발급 전

- [ ] 위 1.1~1.6 모든 META 항목이 운영자 secure storage에 보관되었다
- [ ] `channel_ops_sop.md`의 Adam 승인 절차를 운영자가 숙지했다
- [ ] `.env.example`에 키 변수명만 (값 없이) 등재되어 있다 — 실값 없는 채로 commit 가능
- [ ] `preflight_check.py --section 13`이 모든 AUTO 항목 PASS로 응답한다 (실값 없이도 가능)
- [ ] Codex의 `commerce_growth_pipeline.py`가 mock 데이터로 stage 5 채널 패키지를 생성할 수 있다

### 3.2 발급 직후 (운영자 책임)

- [ ] 키를 EC2의 **`/opt/ai-adam-agent-company/teams/commerce-agent-team/.env`** 한 곳에만 저장 (이 파일이 commerce-agent-team과 client-ops-team이 공유하는 단일 source of truth — `llm_client.py`가 양 팀에서 이 경로를 fallback으로 읽음)
- [ ] 변수명은 `teams/commerce-agent-team/scripts/check_channel_readiness.py`의 `ENV_REQUIRED`와 1:1 일치 (Coupang 3개 + Amazon 8개 = 11개)
- [ ] 권한 최소화: SP-API role은 Inventory/Listings READ + Catalog WRITE만, 그 외 거절
- [ ] Coupang 셀러 권한도 동일하게 최소 범위
- [ ] 키 로테이션 정책 등재 (90일)
- [ ] 모든 발급 키의 `last_rotated_at` 메타를 별도 secure log에 기록 (저장소 X)
- [ ] `python teams/commerce-agent-team/scripts/check_channel_readiness.py`가 `status=ready` 또는 `not_ready` 이외 값을 반환하지 않는다 (`unsafe_config` 발생 시 즉시 키 로테이션)

### 3.3 발급 후 첫 1주

- [ ] DRY_RUN=true 상태에서 stage 5 → Adam 승인 큐 흐름이 정상 동작 (`commerce_growth_pipeline.py`)
- [ ] Adam이 명시적으로 `DRY_RUN=false`로 전환할 때까지 실제 채널 게시는 절대 발생하지 않음
- [ ] `03_cs_manager`가 Coupang WING / Amazon Buyer-Seller 메시지함을 수신할 수 있는 설정 확인 (`channel_ops_sop.md` §3)
- [ ] 첫 환불/반품 사례 발생 시 `refund_or_claim_escalation` 핸드오프가 정총괄 큐로 들어오는지 확인

## 4. 절대 커밋 금지 민감정보 (총정리)

### 4.1 신원/법인

- 사업자번호 (4자리 외 마스킹도 본 저장소에는 금지)
- 대표자 성명, 주민번호 일부, 여권번호
- 통신판매업 신고증 PDF/이미지
- DUNS 번호 본값 (메타데이터로 "DUNS 발급됨"만 가능)
- W-8BEN, W-9 양식

### 4.2 결제/정산

- 은행 계좌번호, BIC/SWIFT
- 카드번호 (전체 또는 마스킹된 6+4 포함 — 본 저장소에 어떤 형태로도 금지)
- Hyperwallet/Payoneer 계정 ID
- VAT 등록번호

### 4.3 API 키 / 토큰

- 모든 `*_API_KEY`, `*_SECRET_KEY`, `*_REFRESH_TOKEN`, `*_ACCESS_TOKEN`, `*_ROLE_ARN`
- Amazon SP-API: `AMAZON_SP_CLIENT_ID` / `AMAZON_SP_CLIENT_SECRET` / `AMAZON_SP_REFRESH_TOKEN` / `AMAZON_SP_AWS_ACCESS_KEY_ID` / `AMAZON_SP_AWS_SECRET_ACCESS_KEY` / `AMAZON_SP_ROLE_ARN`
- Coupang: `COUPANG_VENDOR_ID` / `COUPANG_ACCESS_KEY` / `COUPANG_SECRET_KEY`
- 위 변수명은 `teams/commerce-agent-team/scripts/check_channel_readiness.py`의 `ENV_REQUIRED`가 canonical. 실값은 EC2 `/opt/ai-adam-agent-company/teams/commerce-agent-team/.env` 한 곳에만.
- WING/Seller Central 로그인 비밀번호
- MFA seed/QR

### 4.4 고객 데이터

- 실고객 이름, 전화번호, 이메일 풀텍스트
- 배송지 주소 (실주소)
- 의료기록, 진단명, 처방내역 (서비스 고객사 인입 케이스)
- 카드 분쟁 케이스의 카드번호/Last4
- 채팅 본문 풀텍스트 (해시 + 카테고리만 허용)

### 4.5 운영 보안

- SSH `.pem` private key
- EC2 instance ID (메타데이터로만, 실값은 .env로)
- 내부 Slack/Telegram 토큰 (위와 동일)

본 저장소의 모든 자동 점검 (`preflight_check.py §1.3`)이 위 패턴을 grep으로 검출하므로, 실수로 추가되면 즉시 FAIL 처리되어야 한다.

## 5. 운영자 액션 매트릭스

| 누가 | 무엇을 | 언제 |
| --- | --- | --- |
| Adam | 위 §1~§4 모든 항목을 secure storage에 보관 | 채널 가입 신청 전 |
| Adam | API 키 발급, `.env` 등록, 권한 최소화 | 가입 직후 |
| Adam | `DRY_RUN=false` 전환 결정 | 첫 채널 패키지 검토 후 |
| 정총괄 (05) | `preflight_check.py --section 13` 통과 확인 | API 키 발급 직전 |
| 정총괄 (05) | Adam 승인 큐 (Codex stage 5)의 모든 패키지 1차 검수 | stage 5 발생 시 |
| 김은보 (01) | 새 셀러 계정 등록 = 신규 "계정 케이스" 온보딩 패키지 작성 | 가입 직후 |
| 이용대 (03) | Coupang/Amazon 메시지함 응대 톤 카드 v2 작성 | 가입 직후 |
| 박실행 (02) | 게시 후 일일 작업 (재고 동기, 가격 알림) — DRY_RUN 우선 | `DRY_RUN=false` 전환 후 |
| 최분석 (04) | 게시 후 성과 KPI 측정 시작 | `commerce_growth_pipeline.py` stage 6 활성화 후 |

## 6. 관련 문서

- `shared/channel_ops_sop.md` — 게시 전 Adam 승인 절차, 게시 후 CS/환불/클레임 흐름
- `shared/handoff_contract.md` — 5명 ↔ 5명 핸드오프 매트릭스
- `shared/commerce_integration.md` — commerce-agent-team과의 4가지 신호 송수신 규약
- `shared/pre_launch_checklist.md §13` — 본 문서의 자동 점검 항목 매핑
- `teams/commerce-agent-team/scripts/commerce_growth_pipeline.py` (read-only) — stage 5/6 채널 패키지/성과 트래킹 생성기
- `shared/handoff_contracts/commerce_client_ops_contract.md` (read-only) — 양 팀 canonical contract v1
