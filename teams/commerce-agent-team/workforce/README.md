# Five-Agent Commerce Workforce

이 폴더는 `commerce-agent-team`의 정식 AI 직원 조직입니다.

목표는 5명의 에이전트가 각자 독립 업무를 수행하면서도, 최종적으로 하나의 상품 발굴/검수 리포트로 합쳐지게 만드는 것입니다.

## 조직도

1. `01_market_scout` - 시장/상품 발굴 담당
2. `02_margin_analyst` - 마진/수요/경쟁 분석 담당
3. `03_risk_guardian` - 인증/상표/IP/플랫폼 정책 검수 담당
4. `04_listing_builder` - 상품명/상세페이지/키워드 제작 담당
5. `05_ops_manager` - 업무 배분/최종 판단/리포트 총괄 담당

## 운영 방식

각 에이전트는 자기 폴더 안에 다음 파일을 가집니다.

- `persona.md`: 성격, 역할, 판단 기준
- `inbox.md`: 배정된 업무
- `memory.md`: 누적 학습/주의사항
- `output_template.md`: 산출물 양식

## 업무 흐름

```text
Ops Manager
-> Market Scout
-> Margin Analyst
-> Risk Guardian
-> Listing Builder
-> Ops Manager 최종 리포트
```

중요한 원칙:

- Risk Guardian이 `하드 스톱`을 걸면 Listing Builder는 상세페이지를 만들지 않습니다.
- 자동 게시/자동 판매는 금지합니다. 사람이 최종 승인합니다.
- 모든 에이전트는 자신이 모르는 것을 추측으로 확정하지 않습니다.
- 각 에이전트의 결과는 `handoff` 형식으로 다음 에이전트에게 넘깁니다.

## 업무 배정

수동으로 배정하려면 각 에이전트의 `inbox.md`에 업무를 적습니다.

스크립트로 배정하려면:

```powershell
cd "C:\Users\ADAM\Documents\Ai Adam Agent Company\ai-adam-agent-company\teams\commerce-agent-team"
python scripts\assign_task.py 01_market_scout "쿠팡 사무용품 후보 20개 조사"
```

## 지금 단계

이 구조는 API 실행 전 준비 단계입니다.  
나중에 OpenAI API, Codex, Claude, Gemini, n8n, Make, Zapier, GitHub Actions 같은 실행 환경을 붙이면 각 에이전트를 실제 자동 작업자로 바꿀 수 있습니다.
