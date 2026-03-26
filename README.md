# AI2THOR SMART-LLM Aligned Multi-Agent System

SMART-LLM 논문의 4단계(Stage 1~4) 파이프라인을 기준으로 AI2-THOR 멀티에이전트 실행을 구현한 프로젝트입니다.

## 핵심 구성
- Stage 1: Task Decomposition
- Stage 2: Coalition Formation
- Stage 3: Task Allocation
- Stage 4: Task Execution (Primitive-action Interleaving + Retry/Local Replan)

## 디렉토리 구조
```text
ai2thor/
├── main.py
├── docker-compose.yml
├── src/smart_llm/
│   ├── config.py
│   ├── pipeline.py
│   ├── llm/
│   │   └── prompts/stage1_task_decomposition.yaml
│   ├── schemas/
│   ├── stages/
│   ├── execution/
│   ├── environment/
│   ├── metrics/
│   ├── knowledge/
│   │   └── ai2thor_world.yaml
│   └── benchmark/
├── tests/
└── docs/
```

## 빠른 시작
### 1) 가상환경 생성 및 활성화
프로젝트별로 의존성을 분리하려면 먼저 가상환경을 만드는 편이 좋습니다. 아래 예시는 macOS/Linux 기준입니다.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
```

### 2) 의존성 설치
```bash
pip install -r requirements.txt
```

### 3) `.env` 파일 생성
```bash
OPENAI_API_KEY=your_api_key_here
OPENAI_MODEL=gpt-4.1-mini
# Optional
# OPENAI_BASE_URL=https://api.openai.com/v1
# OPENAI_REASONING_EFFORT=low
```

### 4) Dry-run 실행 (AI2-THOR 없이)
```bash
python main.py "토마토를 썰어서 냉장고에 넣고, 불을 꺼줘" --provider echo --model echo --dry-run
```

### 5) GPT 기반 실행
```bash
python main.py "토마토를 썰어서 냉장고에 넣고, 불을 꺼줘" --provider openai --profile dev
```

### 6) 상단 관찰 카메라 저장
AI2-THOR의 공식 `GetMapViewCameraProperties -> AddThirdPartyCamera` 흐름을 사용해 orthographic top view 영상을 저장합니다. 즉 현재 구현은 근사치가 아니라, 원근이 제거된 공식 map-view top camera를 사용합니다.

```bash
python main.py "토마토를 썰어서 냉장고에 넣고, 불을 꺼줘" --provider openai --profile dev --record-overhead --record-dir output_videos
```

### 7) 각 agent POV + top view 동시 저장
top view와 함께 각 agent 시야 영상도 mp4로 저장합니다.

```bash
python main.py "토마토를 썰어서 냉장고에 넣고, 불을 꺼줘" --provider openai --profile dev --record-overhead --record-pov --record-dir output_videos
```

### 8) 빠른 smoke test
실제 AI2-THOR 렌더러와 멀티에이전트 스케줄링만 빠르게 확인하려면 echo provider와 `test` 프로필을 쓰면 됩니다.

```bash
python main.py "토마토를 썰어서 냉장고에 넣고, 불을 꺼줘" --provider echo --profile test --record-overhead --record-pov
```

## 실행 방식
- agent 수는 고정 3대가 아니라, Stage 1에서 나온 병렬 폭을 기준으로 이번 run에 필요한 수만 생성합니다. 예를 들어 `토마토를 썰어서 냉장고에 넣고, 불을 꺼줘`는 2 agent로 실행됩니다.
- 병렬 subtasks는 같은 `thread_group` 안에서 primitive action 단위로 interleave 됩니다. 즉 한 agent가 `MoveAhead` 또는 `Rotate` 1회 수행하면 다음 agent 차례로 넘어갑니다.
- 실제 AI2-THOR 다중 agent 제어는 `agentId`별 액션 호출 방식이라, 완전히 동일 tick의 동시 물리 실행보다는 라운드로빈에 가까운 병렬 실행입니다.
- 이동 실패 시에는 좌우 이동만 반복하지 않도록 회전, 후진, 재정렬, 다른 interactable pose 재시도를 사용합니다.
- 실패한 task를 `CounterTop` 같은 임의 목표로 바꿔 계속 진행하지 않습니다. 실패는 그대로 실패로 보고됩니다.
- 녹화 artifact에는 `overhead_video`, `agent_videos`, `agent_count`가 포함됩니다.

## 벤치마크 실행
벤치마크 실행은 단일 명령 1개를 돌리는 것이 아니라, `src/smart_llm/benchmark/tasks.json`에 들어 있는 표준 과제 묶음을 순회하면서 카테고리별 평균 지표를 계산하는 모드입니다. 현재 구현은 각 카테고리에서 unseen split을 뽑아 `Exe`, `RU`, `GCR`, `TCR`, `SR`를 집계합니다.

```bash
python main.py --benchmark --benchmark-path src/smart_llm/benchmark/tasks.json --provider openai --json
```

## 테스트
테스트는 벤치마크와 다르게 "성능 평가"가 아니라 "코드가 안 깨졌는지 확인하는 회귀 검사"입니다. `tests/` 아래의 단위/통합 테스트를 실행해서 스키마 검증, 할당 로직, 실행기 동작, 메트릭 계산, dry-run 파이프라인이 기대대로 유지되는지 확인합니다.

```bash
python -m unittest discover -s tests -v
```

## 카탈로그 갱신(선택)
카탈로그 갱신은 설치된 AI2-THOR 런타임을 스캔해서 `src/smart_llm/knowledge/ai2thor_world.yaml`의 scene/object 지식을 새로 반영하는 작업입니다. 보통 AI2-THOR 버전을 올렸거나, 프롬프트/휴리스틱이 참고하는 객체 목록을 최신화하고 싶을 때만 필요합니다. 매 실행마다 돌리는 명령은 아닙니다.

```bash
python scripts/update_ai2thor_catalog.py
```

## 문서
- 아키텍처: `docs/architecture.md`
- 실험 가이드/지표: `docs/experiments.md`
- AI2-THOR 요약: `AI2THOR_API_REFERENCE_SUMMARY.md`

## 지표
- `Exe`, `RU`, `GCR`, `TCR`, `SR`

## LLM 출력 메타데이터
- Stage 1 결과에는 `provider`, `model`, `latency_ms`, `prompt_tokens`, `completion_tokens`가 함께 기록됩니다.
