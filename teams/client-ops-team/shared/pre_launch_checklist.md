# Pre-Launch Checklist

Client Ops must pass this checklist before handling real customers.

| Category | Check | Status |
| --- | --- | --- |
| Secrets | `.env` exists only on server/local and is not committed | Pending |
| Customer Data | No raw customer data stored in Git | Pending |
| Escalation | P0 trigger list reviewed by Adam | Pending |
| Outbound Safety | All outbound actions default to dry-run | Pending |
| Legal | Legal/refund/contract wording escalates to Adam | Pending |
| Medical | Medical or diagnosis language escalates to Adam | Pending |
| Privacy | Resident ID, card, health, and contact data are masked | Pending |
| QA | Coordinator/QA reviews every external deliverable | Pending |
| Logs | Runtime logs stored under ignored `reports/` | Pending |
| Commerce Handoff | Anonymized handoff format tested | Pending |
| Billing | No paid API usage without budget limit | Pending |
| Recovery | Dashboard, timers, and runbooks verified | Pending |

---

## 한국어 상세 — 12개 카테고리 점검

실운영 시작(첫 실제 고객 응대) 전 본 체크리스트의 12개 카테고리 모두 통과해야 한다. 통과 책임자는 정총괄, 최종 승인자는 Adam.

### 1. Secrets (비밀 관리)

- [ ] `.env`는 서버/로컬에만 존재, 저장소 커밋 0건
- [ ] 루트 `.gitignore`가 `.env`, `*.pem`, `*.key`, `*.p12`를 보호함 (확인 완료)
- [ ] API 키 로테이션 정책 수립 (90일 주기)

### 2. Customer Data (고객 데이터)

- [ ] 실고객 정보가 저장소 어디에도 없음 (전체 grep 1회 실행 + 결과 보관)
- [ ] 응대 본문 원본은 `reports/` 또는 외부 저장 (gitignored)
- [ ] 모든 샘플은 가상 (예: "샘플치과 OOO 원장님", "010-XXXX-XXXX")

### 3. Escalation (에스컬레이션)

- [ ] P0 키워드 사전 Adam 검토 완료
- [ ] Telegram 알림 채널 운영 테스트 1회 (DRY_RUN 모드)
- [ ] 정총괄 → Adam 통지 SLA 5분 합의

### 4. Outbound Safety (외부 발송 안전장치)

- [ ] `DRY_RUN=true` 기본값 확인
- [ ] DRY_RUN 해제 권한은 Adam 단독
- [ ] 박실행이 미등록 작업 코드 거절 동작 확인
- [ ] 카카오 알림톡 템플릿은 사전심사 통과한 ID만 사용

### 5. Legal (법적 키워드)

- [ ] "환불", "변호사", "고소", "소송", "민원", "공정위" 등 자동 차단 동작 확인
- [ ] 자동응답 발송 차단 → 정총괄 → Adam 흐름 1회 시뮬레이션

### 6. Medical (의료 키워드)

- [ ] "진단", "처방", "부작용", "의약품", "의료기기" 등 자동 차단 동작 확인
- [ ] 미용/한방/필라테스 등 회색지대 업종 톤 카드 정총괄 검수 완료

### 7. Privacy (개인정보)

- [ ] 주민번호, 카드번호, 진단명 패턴 마스킹 확인
- [ ] 사업자번호는 4자리 외 마스킹
- [ ] 응대 이력 풀텍스트가 메모리에 남지 않는 것 확인

### 8. QA (정총괄 게이트)

- [ ] 모든 외부 산출물에 정총괄 결정문 부착
- [ ] 정총괄 결정 사유 누락 0건
- [ ] 정총괄 self-review 차단 (자기 작성물 본인이 통과시키지 않음)

### 9. Logs (로그)

- [ ] `reports/` 디렉토리는 gitignored (루트 `.gitignore` 확인 완료)
- [ ] 로그 형식이 JSONL로 통일됨
- [ ] 박실행 로그 누락 0건 확인 1주 모니터링

### 10. Commerce Handoff (커머스 통합)

- [ ] `shared/handoff_to_commerce.md`의 PII 체크리스트 1회 dry-run 통과
- [ ] 커머스 팀 수신측 양식 합의 완료
- [ ] 정총괄 양방향 게이트 흐름 1회 시뮬레이션

### 11. Billing (비용 통제)

- [ ] 각 LLM 키에 월간 budget cap 설정 (Anthropic, Google, OpenAI)
- [ ] budget의 80% 도달 시 알림 채널 동작
- [ ] 박실행은 가장 저렴한 모델(Gemini Flash) 고정, 다른 모델로 fallback 금지

### 12. Recovery (복구 준비)

- [ ] 박실행 systemd timer 또는 cron이 EC2 reboot 후 자동 재시작
- [ ] 실패 큐 재시도 정책 (3회, exponential backoff) 동작 확인
- [ ] 5명 페르소나·메모리·output_template 백업 (정총괄 보관)
- [ ] 30분 이상 장애 발생 시 Adam 즉시 통지 채널 확인

---

## 통과 기록

| 카테고리 | 통과 일자 | 책임자 | 비고 |
| --- | --- | --- | --- |
| 1. Secrets | - | 05 정총괄 | - |
| 2. Customer Data | - | 05 정총괄 | - |
| 3. Escalation | - | 05 정총괄 + Adam | - |
| 4. Outbound Safety | - | 02 박실행 + 05 정총괄 | - |
| 5. Legal | - | 03 이용대 + 05 정총괄 | - |
| 6. Medical | - | 01 김은보 + 03 이용대 + 05 정총괄 | - |
| 7. Privacy | - | 01 김은보 + 05 정총괄 | - |
| 8. QA | - | 05 정총괄 + Adam | - |
| 9. Logs | - | 02 박실행 + 04 최분석 | - |
| 10. Commerce Handoff | - | 05 정총괄 + commerce-agent-team | - |
| 11. Billing | - | 05 정총괄 + Adam | - |
| 12. Recovery | - | 05 정총괄 + Adam | - |

**전체 통과 시점에 Adam이 본 문서 하단에 서명 (이름 + 날짜) 1줄 추가.**
