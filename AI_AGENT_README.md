# AI-Powered Multi-Agent Task Executor

AI2-THOR 시뮬레이션에서 자연어 명령을 분석하여 자동으로 작업을 분할하고, 최소한의 에이전트를 생성하여 병렬로 작업을 수행하는 시스템입니다.

## 주요 기능

### 1. 진정한 병렬 실행 (Interleaving)
- 여러 에이전트가 동시에 한 스텝씩 번갈아 실행
- 순차 실행이 아닌 실제 병렬 처리

### 2. 동적 에이전트 생성
- 작업 수에 따라 필요한 최소 에이전트만 생성 (최대 4명)
- 리소스 효율적 운영

### 3. 동적 작업 할당 (Task Queue)
- 작업 큐 시스템으로 유연한 작업 관리
- 에이전트가 작업을 완료하면 자동으로 다음 작업 할당

### 4. Ollama LLM 기반 자연어 분석
- 로컬 LLM으로 사용자 명령 분석
- 자동 작업 분할 및 파라미터 추출

## 파일 구조

```
multi_agent_parallel.py     # 병렬 실행 엔진 (하드코딩된 작업)
ai_multi_agent.py           # AI 기반 자연어 명령 처리
```

## 설치

### 1. Ollama 설치
```bash
# macOS
brew install ollama

# 모델 다운로드
ollama pull llama3.2:3b
```

### 2. Ollama 서버 시작
```bash
ollama serve
```

### 3. Python 패키지
```bash
pip install ai2thor opencv-python requests
```

## 사용 방법

### A. 병렬 실행 엔진 (하드코딩)
```bash
python multi_agent_parallel.py
```

4개의 작업이 하드코딩되어 있습니다:
- Agent 0: 토마토를 썰어서 냉장고에 넣기
- Agent 1: 불 끄기
- Agent 2: 빵 데우기
- Agent 3: 접시 씻기

### B. AI 기반 자연어 처리
```bash
python ai_multi_agent.py
```

명령 예시:
- "토마토를 썰어서 냉장고에 넣고, 불을 꺼줘"
- "빵을 데우고, 접시를 씻고, 감자를 썰어서 냉장고에 넣어줘"
- "불을 켜고, 사과를 썰어서 냉장고에 넣어줘"

## 지원 작업 타입

### 1. slice_and_store
물건을 자르고 보관
```python
{
    'type': 'slice_and_store',
    'source_object': 'Tomato',  # 자를 물건
    'target_object': 'Fridge'   # 보관할 곳
}
```

### 2. toggle_light
전등 켜기/끄기
```python
{
    'type': 'toggle_light',
    'action': '켜기'  # 또는 '끄기'
}
```

### 3. heat_object
전자레인지로 데우기
```python
{
    'type': 'heat_object',
    'object': 'Bread'
}
```

### 4. clean_object
싱크대에서 씻기
```python
{
    'type': 'clean_object',
    'object': 'Plate'
}
```

## 시스템 아키텍처

```
사용자 명령
    ↓
Ollama LLM 분석
    ↓
작업 분할 + 에이전트 수 결정
    ↓
TaskQueue 생성
    ↓
MultiAgentTaskExecutor 생성 (각 에이전트)
    ↓
병렬 실행 (Interleaving)
    ↓
작업 완료 → 다음 작업 자동 할당
```

## 병렬 실행 예시

```
Iteration 1:
  Agent0: Tomato로 이동 (스텝 1)
  Agent1: LightSwitch로 이동 (스텝 1)
  Agent2: Bread로 이동 (스텝 1)
  Agent3: Plate로 이동 (스텝 1)

Iteration 2:
  Agent0: Tomato로 이동 (스텝 2)
  Agent1: LightSwitch 보기
  Agent2: Bread로 이동 (스텝 2)
  Agent3: Plate로 이동 (스텝 2)

...

Agent1이 먼저 완료되면 자동으로 다음 작업 할당
```

## 출력

### 비디오 파일
- `parallel_agent0_YYYYMMDD_HHMMSS.mp4` - Agent 0 POV
- `parallel_agent1_YYYYMMDD_HHMMSS.mp4` - Agent 1 POV
- `ai_agent0_YYYYMMDD_HHMMSS.mp4` - AI 모드 Agent 0 POV
- ...

### 콘솔 출력
```
============================================================
AI-Powered Multi-Agent Task Executor
============================================================

🤔 LLM 분석 중...
✓ 분석 완료
  - 작업 수: 3개
  - 필요 에이전트: 3명
  - 분석: Three independent tasks with no dependencies

============================================================
📋 실행 계획:
  1. 토마토를 썰어서 냉장고에 넣기
  2. 접시 씻기
  3. 불 끄기

🤖 에이전트 수: 3명
============================================================

[Agent0] 📋 Tomato를 썰어서 Fridge에 넣기
[Agent1] 📋 Plate를 씻기
[Agent2] 📋 LightSwitch 끄기

...

============================================================
📊 작업 결과:
  1. 토마토를 썰어서 냉장고에 넣기 (Agent 0) - ✓ 성공
  2. 접시 씻기 (Agent 1) - ✓ 성공
  3. 불 끄기 (Agent 2) - ✓ 성공
============================================================
```

## LLM 프롬프트 구조

시스템은 다음 정보를 LLM에 제공합니다:
- 사용 가능한 작업 타입 설명
- FloorPlan1의 사용 가능한 물건 목록
- 작업 예시 (few-shot learning)
- JSON 출력 형식 지정

LLM은 다음을 반환합니다:
- 개별 작업 목록 (type + parameters)
- 필요한 최소 에이전트 수
- 작업 분할 이유 (reasoning)

## 확장 가능성

### 새로운 작업 타입 추가
`MultiAgentTaskExecutor` 클래스에 `_step_new_task()` 메서드 추가:
```python
def _step_new_task(self, task):
    if self.task_step == 0:
        # 초기화
        ...
    elif self.task_step == 1:
        # 실행 단계
        ...
```

### 다른 LLM 모델 사용
```python
query_ollama(prompt, model="gemma2:2b")  # 더 가벼운 모델
query_ollama(prompt, model="qwen2.5:7b") # 더 강력한 모델
```

### 다른 씬 사용
```python
Controller(scene="FloorPlan28", ...)  # Kitchen
Controller(scene="FloorPlan201", ...) # Living Room
```

## 성능 최적화

- **작업 순서**: LLM이 자동으로 병렬화 가능한 작업 파악
- **에이전트 수**: 작업 수와 의존성을 고려하여 최소 에이전트 할당
- **리소스 관리**: 불필요한 에이전트 생성 방지

## 문제 해결

### Ollama 연결 오류
```bash
# Ollama 서버가 실행 중인지 확인
ollama serve

# 다른 터미널에서 테스트
curl http://localhost:11434/api/generate -d '{"model":"llama3.2:3b","prompt":"test"}'
```

### 작업 실패
- AI2-THOR 시뮬레이션의 물리 엔진 제약으로 가끔 실패 가능
- 재시도 로직이 필요한 경우 추가 구현 가능

### 비디오 파일 재생 안 됨
- macOS: QuickTime Player 또는 VLC 사용
- H.264 코덱(avc1) 사용으로 대부분의 플레이어에서 재생 가능
