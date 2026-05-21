# Backlog

Public-safe task queue for planned client-ops work.

Do not place real customer names, phone numbers, emails, contracts, medical/legal details, API keys, or raw message bodies here. Use case IDs and masked summaries only.

## Sample

| ID | Owner | Priority | Summary | Status |
| --- | --- | --- | --- | --- |
| ONB-SAMPLE-001 | 01_onboarding_manager | P2 | Prepare onboarding packet template for a sample clinic | Ready |

---

## 대기 큐 (한국어 샘플)

식별정보 없는 가상 케이스만 기록. `case_id` 형식은 `CLI-YYYY-NNN`.

| Task ID | 작업 코드 | Owner | P | 요청 | 상태 |
| --- | --- | --- | --- | --- | --- |
| TASK-2026-05-21-002 | `ONB-PACKAGE` | 01_onboarding_manager | P1 | 샘플치과 (CLI-2026-014) 온보딩 패키지 v1 작성 | TODO |
| TASK-2026-05-21-003 | `ONB-PERMSCAN` | 01_onboarding_manager | P2 | 샘플미용실 (CLI-2026-015) 예약 시스템 권한 감사 | TODO |
| TASK-2026-05-22-001 | `OPS-REMIND-D-1` | 02_ops_operator | P1 | CLI-2026-014 예약 전일 리마인더 정기 작업 등록 (정총괄 통과 후) | BLOCKED (정총괄 검수 대기) |
| TASK-2026-05-22-002 | `CS-TONECARD-MISSING` | 01_onboarding_manager | P2 | 샘플필라테스 (CLI-2026-013) 톤 카드에 "사진 동의" 항목 추가 | TODO |
| TASK-2026-05-22-003 | `ANL-CASE-LAUNCH` | 04_data_analyst | P3 | CLI-2026-014 KPI 측정 시작일 등록 (운영 시작 +7일) | TODO |
| TASK-2026-05-23-001 | `ANL-WEEKLY` | 04_data_analyst | P2 | 2026-W21 주간 리포트 초안 작성 | TODO |
| TASK-2026-05-23-002 | `QA-ANL-WEEKLY` | 05_coordinator_qa | P2 | 2026-W21 주간 리포트 검수 → Adam 보고 | BLOCKED (ANL-WEEKLY 선행) |
| TASK-2026-05-24-001 | `ONB-RENEW` | 01_onboarding_manager | P3 | CLI-2025-011 (샘플학원 OOO 원장님) 1년 갱신 재검증 | TODO |

### 생성 시 주의

- 실고객명, 실주소, 사업자번호, 카드번호 금지
- 가상 식별자: `샘플치과 OOO 원장님`, `010-XXXX-1234`, `사업자번호 ***-**-XXXX`
- 작업 코드는 `shared/task_packet_template.md` 카탈로그에 등재된 것만
