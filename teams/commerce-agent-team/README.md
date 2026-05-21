# AI Commerce Agent Team

상품 발굴, 마진 분석, 리스크 검수, 상세페이지 초안, 최종 운영 판단을 맡는 5명짜리 파일 기반 AI 에이전트 팀입니다.

이 프로젝트의 목적은 바로 자동 판매를 시작하는 것이 아니라, 먼저 돈이 될 가능성이 있는 후보를 안정적으로 발굴하고 사람이 승인할 수 있는 리포트로 만드는 것입니다.

## Team

| Agent | Role | Output |
| --- | --- | --- |
| `01_market_scout` | 시장/상품 발굴 | 후보 상품과 조사 메모 |
| `02_margin_analyst` | 마진/수요/경쟁 분석 | 점수표와 우선순위 |
| `03_risk_guardian` | 인증/IP/이미지/반품 리스크 검수 | 진행/보류 판단 |
| `04_listing_builder` | 상품명/상세페이지 초안 | 리스팅 초안 |
| `05_ops_manager` | 최종 조율/운영 판단 | 최종 리포트 |

## Folder Structure

```text
commerce-agent-team/
  agents/                    # 초기 참고 프롬프트
  collectors/                # 데이터 수집 레이어 설명
  config/                    # LLM 모델 설정
  dashboard/                 # 로컬/EC2 대시보드
  data/                      # 후보 상품 CSV와 수동 입력함
  docs/                      # EC2 배포 문서
  ops/systemd/               # 서버 자동 실행 서비스 예시
  prompts/                   # 점수/검수 기준
  reports/                   # 최신 리포트
  scripts/                   # 실행 스크립트
  workforce/                 # 5명 에이전트의 페르소나, inbox, outbox, runs
```

## Quick Start

```bash
cd "C:\Users\ADAM\Documents\Ai Adam Agent Company\ai-adam-agent-company\teams\commerce-agent-team"
python scripts/run_pipeline.py
python scripts/run_agents.py
python dashboard/app.py --check
```

대시보드를 켜려면:

```bash
python dashboard/app.py
```

브라우저에서 `http://127.0.0.1:8080`을 엽니다.

## Import New Candidates

새 상품 후보 CSV를 `data/manual_inbox/`에 넣은 뒤:

```bash
python scripts/import_candidates.py data/manual_inbox/new_candidates.csv
python scripts/run_agents.py
```

필수에 가까운 필드는 `product_name`, `source_market`, `target_market`, `category`입니다. 숫자 필드가 없으면 보수적인 기본값으로 채워집니다.

## Generate Scout Tasks

키워드 기반 조사 업무를 만들려면:

```bash
python scripts/generate_scout_tasks.py
```

결과는 `workforce/tasks/generated_scout_tasks.md`에 저장됩니다.

## LLM Hook

기본값은 비용이 들지 않는 mock 모드입니다.

```bash
copy .env.example .env
```

OpenAI API를 붙일 때 `.env`를 수정합니다.

```text
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-...
```

그 뒤:

```bash
python scripts/run_agents.py --use-llm
```

## EC2

배포 절차는 `docs/EC2_DEPLOY.md`를 봅니다. systemd 서비스와 타이머 예시는 `ops/systemd/`에 들어 있습니다.

## Guardrails

- 플랫폼 약관을 확인하기 전까지 자동 크롤링과 자동 게시를 하지 않습니다.
- KC, 식품, 화장품, 전기용품, 어린이용품, 의료/건강 표현 상품은 보수적으로 제외합니다.
- 타 판매자의 이미지와 상세페이지 문구를 그대로 재사용하지 않습니다.
- 첫 단계는 `후보 발굴 -> 에이전트 검수 -> 사람 승인`입니다.
