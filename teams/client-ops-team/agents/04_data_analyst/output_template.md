# Output Template - 최분석

## 산출물 종류

1. **주간 리포트** (Markdown → PDF): TL;DR + 표 + 출처
2. **일일 KPI 스냅샷** (JSON): 자동 적재용
3. **익명 집계 패키지** (JSON, 커머스팀용): 업종/주차 단위
4. **현상 보고서** (Markdown): 표본 부족 시

---

## 1) 주간 리포트 (Markdown)

```markdown
WEEKLY REPORT — 2026-W21 (5/18 ~ 5/24)

## TL;DR

- 정시 실행률: 99.7% (직전 4주 평균 99.5%, +0.2pp)
- 전송 성공률: 99.5% (직전 4주 평균 99.4%, +0.1pp)
- CS 자동응답 사후 부적합: 1건 / 312건 (0.3%)
- P0 에스컬레이션: 4건 (직전 4주 평균 3.5건)
- 신규 케이스: 2건 (둘 다 정총괄 1차 검수 통과)

원인은 단정하지 않습니다. 가설은 본문 4절 참조.

## 1. 운영 실행 (박실행 데이터)

| 지표 | 이번 주 | 직전 4주 평균 | 변화 |
| --- | --- | --- | --- |
| 정시 실행률 | 99.7% | 99.5% | +0.2pp |
| 전송 성공률 | 99.5% | 99.4% | +0.1pp |
| 중복 발송 | 0 | 0 | 변화 없음 |
| 로그 누락 | 0 | 0 | 변화 없음 |

출처: `reports/raw_ops_2026-W21.jsonl`

## 2. CS 응대 (이용대 데이터)

| 우선순위 | 건수 | 직전 4주 평균 | 변화 |
| --- | --- | --- | --- |
| P0 (즉시 에스컬레이션) | 4 | 3.5 | +0.5 |
| P1 | 23 | 24.0 | -1.0 |
| P2 | 87 | 82.5 | +4.5 |
| P3 (자동응답) | 312 | 298.0 | +14.0 |

자동응답 사후 부적합: 1건 (FAQ 영업시간 안내 중 휴무일 누락). 정총괄 사후 검수 결과 반영, 톤 카드 보강 요청 발생.

출처: `reports/raw_cs_2026-W21.jsonl`

## 3. 신규 케이스 (김은보 데이터)

- 신규 등록: CLI-2026-014 (샘플치과), CLI-2026-015 (샘플미용실)
- 정총괄 1차 검수 통과율: 2/2 (100%)
- 권한 과잉 사후 발견: 0건

출처: `tasks/done.md` ONB 섹션

## 4. 현상 가설 (단정 아님)

P0가 +0.5건 늘었다. 4건의 원인 분포:
- 환불 키워드 2건 (다른 케이스)
- 의료 자문 키워드 1건
- 변호사 언급 1건

가설:
1. 5월 가정의 달 마케팅 시즌 종료 후 결제 리뷰가 늘어난 가능성
2. 신규 케이스 1건의 톤 카드가 의료 회색지대를 충분히 못 막았을 가능성
3. 표본 4건은 결론을 내리기에 부족 (직전 4주 표본 합계 14건)

다음 주 추적 필요: 위 가설 중 (2)는 정총괄에게 톤 카드 v2 검수 요청 권고.

## 5. 다음 주 자동 관찰 항목

- P0 인입 카테고리 분포
- 신규 케이스 CLI-2026-015의 첫 주 정시 실행률
- 알림톡 → SMS 폴백 비율

HANDOFF
- 다음 담당: 05_coordinator_qa
- 넘길 자료: 본 리포트(Markdown), 데이터 소스 경로 3건, 가공 스크립트 경로
- 확인 필요: 4절 가설 (2) 관련 정총괄 의견
- 하드 스톱: 없음
- 추천 액션: REVIEW
```

---

## 2) 일일 KPI 스냅샷 (JSON)

```json
{
  "date": "2026-05-21",
  "ops": {
    "on_time_rate": 0.997,
    "delivery_rate": 0.995,
    "duplicate_send": 0,
    "missing_logs": 0
  },
  "cs": {
    "p0": 1,
    "p1": 3,
    "p2": 12,
    "p3": 47,
    "post_review_fail": 0
  },
  "new_cases": 0,
  "data_sources": [
    "reports/raw_ops_2026-05-21.jsonl",
    "reports/raw_cs_2026-05-21.jsonl"
  ],
  "review_required": false
}
```

---

## 3) 익명 집계 패키지 (JSON, 커머스팀용)

```json
{
  "week": "2026-W21",
  "industries": [
    {
      "industry": "치과",
      "ops_on_time_rate": 0.998,
      "cs_p0_per_1000_msgs": 1.2,
      "noshow_rate": 0.041,
      "review_request_response_rate": 0.18,
      "sample_size_cases": 6
    },
    {
      "industry": "미용실",
      "ops_on_time_rate": 0.996,
      "cs_p0_per_1000_msgs": 0.9,
      "noshow_rate": 0.067,
      "review_request_response_rate": 0.22,
      "sample_size_cases": 4
    }
  ],
  "notes": "케이스 단위 식별 불가, 업종/주차 집계만. 샘플 < 5 업종은 제외.",
  "next_owner": "commerce-agent-team / 02_margin_analyst"
}
```

---

## 4) 현상 보고서 (Markdown, 표본 부족 시)

```markdown
PHENOMENON REPORT — 2026-W21 / 신규 업종 "필라테스"

표본: 케이스 2건, 주간 응대 18건.

## 관찰
- 정시 실행률 99.4% (표본 부족, 결론 금지)
- P0 0건
- 노쇼율 8.3% (직전 베이스라인 없음)

## 결론
이번 주 표본은 결론에 부족합니다. 4주 누적 후 다시 평가합니다.

## 다음 측정 시점
2026-W24 (누적 4주차)

HANDOFF
- 다음 담당: 05_coordinator_qa
- 추천 액션: PROCEED (보관만)
```

---

## 핸드오프 매트릭스

| 산출물 | 다음 담당 | 채널 |
| --- | --- | --- |
| 주간 리포트 | 05_coordinator_qa → Adam | `agents/05_coordinator_qa/inbox.md` |
| 일일 KPI 스냅샷 | 05_coordinator_qa (자동 적재) | `reports/daily_snapshot_*.json` |
| 익명 집계 패키지 | commerce-agent-team | `shared/handoff_to_commerce.md` 참고 |
| 현상 보고서 | 05_coordinator_qa | 보관만 |
| 톤 카드 보강 권고 | 01_onboarding_manager | 리포트 본문 4절 발견 시 |
