# Active

Current public-safe work-in-progress queue.

## Rules

- Use case IDs only.
- Store raw customer data outside Git.
- Escalate P0 items to Adam before any outbound action.

---

## 진행 중 (한국어 샘플)

| Task ID | 작업 코드 | Owner | P | 요청 | 상태 | 갱신 |
| --- | --- | --- | --- | --- | --- | --- |
| TASK-2026-05-21-001 | `ONB-PACKAGE` | 01_onboarding_manager | P1 | 샘플치과 (CLI-2026-014) 온보딩 패키지 작성 | IN_PROGRESS | 2026-05-21 14:20 김은보, "확인 필요" 1건 잔존 |
| TASK-2026-05-21-099 | `QA-CS-P0` | 05_coordinator_qa | P0 | CLI-2026-XXX 환불+변호사 키워드 에스컬레이션 | IN_PROGRESS | 2026-05-21 14:23 인입, Adam 통지 완료 14:24 |

각 라인은 한 줄 갱신이 원칙. 상세는 해당 에이전트의 inbox.md 참고.

## 박실행은 본 큐를 쓰지 않는다

박실행은 정형 스케줄러에서 직접 실행되며, 본 `active.md`에는 박실행 작업이 표시되지 않는다. 박실행의 실행 상태는 `reports/ops_daily_*.jsonl` (gitignored)에서 확인.
