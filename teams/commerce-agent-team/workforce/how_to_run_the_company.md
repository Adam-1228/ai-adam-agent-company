# How To Run The Five-Agent Company

이 문서는 5명의 에이전트에게 실제로 일을 시키는 방법입니다.

## 1. 업무를 정한다

좋은 업무 예시:

- 쿠팡 사무용품 카테고리에서 저위험 상품 후보 20개 찾기
- 반려동물 소모품 후보 10개를 마진 기준으로 분석하기
- USB 미니 가습기 상품군의 인증/반품 리스크 검토하기
- 케이블 정리 클립 세트 상세페이지 초안 만들기
- 이번 주 상품 후보 최종 리포트 만들기

나쁜 업무 예시:

- 돈 되는 상품 아무거나 찾아줘
- 알아서 판매 등록까지 해줘
- 타 판매자 상세페이지를 똑같이 만들어줘

## 2. 에이전트에게 배정한다

```powershell
cd "C:\Users\ADAM\Documents\Ai Adam Agent Company\ai-adam-agent-company\teams\commerce-agent-team"
python scripts\assign_task.py 01_market_scout "쿠팡 사무용품 카테고리에서 저위험 상품 후보 20개 찾기" P1
```

배정된 업무는 아래 두 곳에 기록됩니다.

- `workforce/agents/01_market_scout/inbox.md`
- `workforce/tasks/active.md`

## 3. 에이전트 실행 방식

현재는 각 에이전트의 `persona.md`, `memory.md`, `output_template.md`를 프롬프트로 사용합니다.

실행 프롬프트 예시:

```text
너는 workforce/agents/01_market_scout/persona.md의 에이전트다.
memory.md의 주의사항을 따른다.
inbox.md의 최신 TASK를 수행한다.
output_template.md 형식으로 결과를 작성한다.
완료 후 HANDOFF를 남긴다.
```

## 4. 인수인계한다

각 에이전트 결과 마지막의 `HANDOFF`를 보고 다음 담당자에게 업무를 배정합니다.

기본 흐름:

```text
01_market_scout
-> 02_margin_analyst
-> 03_risk_guardian
-> 04_listing_builder
-> 05_ops_manager
```

Risk Guardian이 `HOLD` 또는 `KILL`을 내리면 Listing Builder로 넘기지 않고 Ops Manager에게 넘깁니다.

## 5. 최종 판단

Ops Manager는 최종 리포트를 만들지만, 실제 진행 결정은 Adam이 합니다.

사람 승인 전 금지:

- 상품 구매
- 상품 등록
- 고객 연락
- 광고 집행
- 자동 가격 변경
- 타 사이트 게시

## 6. 다음 자동화 단계

이 구조가 안정되면 다음을 붙입니다.

1. CSV 자동 입력
2. 쿠팡/네이버/아마존 후보 수집기
3. OpenAI API 기반 에이전트 실행
4. Google Sheets 업무함
5. 웹 대시보드
