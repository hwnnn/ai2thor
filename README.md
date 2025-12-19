# AI2THOR iTHOR 개발 환경

AI2THOR iTHOR 환경과 **GPT-4 기반 멀티-에이전트 시스템**이 설정되었습니다.

## 🎯 주요 기능

### 1. 기본 AI2THOR 환경
- 표준 AI2THOR iTHOR 씬 탐색 및 상호작용

### 2. 멀티-에이전트 시스템 (🌟)
- **GPT-4 또는 로컬 gpt-oss** 지원
- **최소 agent 개수 자동 결정**
- **한국어 명령어 지원**
- 병렬 작업 실행

### 3. 로컬 LLM 지원 (💎)
- **완전 무료** - API 비용 0원
- **API 키 불필요** - Ollama 사용
- **오프라인 가능** - 인터넷 연결 불필요
- **프라이버시 보장** - 데이터가 로컬에만 존재

### 4. 실시간 시각화 (📹 NEW!)
- **탑뷰 카메라** - 모든 에이전트를 위에서 내려다보는 시점
- **에이전트 POV** - 각 에이전트의 1인칭 시점
- **통합 뷰** - 탑뷰 + 모든 POV를 한 화면에
- **자동 비디오 녹화** - MP4 형식으로 저장

자세한 내용:
- 📖 [QUICKSTART.md](QUICKSTART.md) - 빠른 시작
- 📖 [GPT_OSS_LOCAL_SETUP.md](GPT_OSS_LOCAL_SETUP.md) - 로컬 LLM 설치
- 📖 [README_MultiAgent.md](README_MultiAgent.md) - 멀티-에이전트 시스템
- 📖 [VISUALIZATION_GUIDE.md](VISUALIZATION_GUIDE.md) - 시각화 가이드

## 설치된 환경

- **Python**: 3.13.2 (Virtual Environment)
- **AI2THOR**: 5.0.0
- **OpenAI**: GPT-4 (멀티-에이전트 시스템용)
- **위치**: `/Users/jaehwan/Desktop/JaeHwan/workspace/ai2thor`

## 의존성 설치

```bash
pip install -r requirements.txt
```

필수 패키지:
- `ai2thor==5.0.0` - AI2THOR 시뮬레이터
- `openai>=1.0.0` - GPT-4 API (멀티-에이전트용)
- `pillow`, `matplotlib`, `numpy` - 시각화

## 요구사항

- OS: macOS 10.9+ 또는 Ubuntu 14.04+
- Python: 3.5+
- CPU: SSE2 instruction set 지원
- Graphics Card: DX9 (shader model 3.0) 또는 DX11 with feature level 9.3

## 파일 설명

### `test_setup.py`
설치가 올바르게 되었는지 확인하는 테스트 스크립트입니다.

실행:
```bash
/Users/jaehwan/Desktop/JaeHwan/workspace/ai2thor/.venv/bin/python test_setup.py
```

## 파일 설명

### `korean_commands.py` (🌟)
**GPT-4 기반 한국어 자연어 명령어** 시스템입니다.

실행:
```bash
# API 키 설정
export OPENAI_API_KEY="your-key"

# 순차적 작업 (1개 agent)
python korean_commands.py 1

# 병렬 작업 (여러 agent)
python korean_commands.py 2

# 모든 예제 실행
python korean_commands.py all
```

### `local_llm.py` (💎)
**로컬 LLM (gpt-oss) 기반 - 완전 무료, API 키 불필요!**

실행:
```bash
# 1. Ollama 설치 및 시작
brew install ollama  # macOS
ollama serve

# 2. gpt-oss 모델 다운로드
ollama pull gpt-oss:20b

# 3. 예제 실행 (API 키 불필요!)
python local_llm.py 1        # 순차적 작업
python local_llm.py 2        # 병렬 작업
python local_llm.py compare  # 비교표
python local_llm.py setup    # 설치 안내
```

예제 명령어:
- "scene 1에서 토마토를 썰고, 불을 켜고 닫고, 냉장고에 토마토를 넣어."
- "agent 1은 주방에서 사과를 찾아서 가져오고, agent 2는 거실에서 TV를 켜."

### `multi_agent_visualizer.py` (📹)
**멀티-에이전트 동작 시각화 시스템**

기능:
- 탑뷰 카메라: 모든 에이전트를 위에서 내려다보는 시점
- 에이전트 POV: 각 에이전트의 1인칭 시점
- 통합 뷰: 탑뷰 + 모든 POV를 한 화면에

사용:
```python
from multi_agent_visualizer import visualize_multi_agent_execution

visualize_multi_agent_execution(
    agents=orchestrator.agents,
    scene="FloorPlan1",
    duration_seconds=30
)
```

### `multi_agent_system.py` (NEW! 🌟)
GPT-4 기반 멀티-에이전트 시스템 코어입니다.

주요 클래스:
- `FunctionDatabase`: AI2THOR 함수 데이터베이스
- `LLMTaskPlanner`: GPT-4 기반 작업 계획기
- `AI2THORAgent`: 독립적인 에이전트
- `MultiAgentOrchestrator`: 멀티-에이전트 조정자

### `visualize_simple.py`
에이전트의 시야를 이미지로 캡처하고 그리드로 시각화합니다.

실행:
```bash
.venv/bin/python visualize_simple.py
```

출력: `output_images/` 폴더에 개별 프레임과 통합 이미지 저장

### `visualize_video.py`
에이전트의 움직임을 MP4 영상으로 녹화합니다.

실행:
```bash
.venv/bin/python visualize_video.py
```

대화형 모드:
```bash
.venv/bin/python visualize_video.py interactive
```

출력: `output_videos/` 폴더에 MP4 영상 저장

## 주요 기능

### 1. Controller 초기화
```python
from ai2thor.controller import Controller
controller = Controller()
```

### 2. 헤드리스 모드 (서버 환경)
화면 없이 실행하려면:
```python
from ai2thor.controller import Controller
from ai2thor.platform import CloudRendering

controller = Controller(platform=CloudRendering)
```

### 3. 특정 씬 로드
```python
controller = Controller(scene="FloorPlan1")
```

### 4. 액션 실행
```python
event = controller.step("MoveAhead")
event = controller.step("RotateRight")
event = controller.step("LookUp")
```

## 첫 실행 시 주의사항

- 첫 Controller 초기화 시 약 **500MB**의 게임 환경이 `~/.ai2thor`에 다운로드됩니다.
- 다운로드는 최초 1회만 진행됩니다.

## 유용한 링크

- [공식 문서

### 기본 AI2THOR 학습
1. `example_basic.py` 실행하여 기본 네비게이션 이해
2. `visualize_simple.py`로 에이전트 시야 확인
3. `visualize_video.py`로 움직임 녹화

### 멀티-에이전트 시스템 사용

#### 옵션 1: OpenAI GPT-4 사용 (유료)
```python
from multi_agent_system import *

function_db = FunctionDatabase()
llm_planner = LLMTaskPlanner(function_db, use_local=False)  # GPT-4
orchestrator = MultiAgentOrchestrator(function_db, llm_planner)

result = orchestrator.execute_natural_language_command(
    command="scene 1에서 토마토를 썰고, 불을 켜고 닫고, 냉장고에 토마토를 넣어.",
    scene="FloorPlan1"
)

orchestrator.shutdown_all_agents()
```

#### 옵션 2: 로컬 gpt-oss 사용 (무료!) 🌟
```python
from multi_agent_system import *

function_db = FunctionDatabase()
llm_planner = LLMTaskPlanner(function_db, use_local=True)  # 로컬 gpt-oss
**자세한 멀티-에이전트 문서**: [README_MultiAgent.md](README_MultiAgent.md)

## 🎯 Quick Examples

### 단순 네비게이션
```python
from ai2thor.controller import Controller

controller = Controller(scene="FloorPlan1")
controller.step("MoveAhead")
controller.step("RotateRight")
```

### 한국어 자연어 명령 (멀티-에이전트)
```python
from multi_agent_system import *

function_db = FunctionDatabase()
llm_planner = LLMTaskPlanner(function_db)
orchestrator = MultiAgentOrchestrator(function_db, llm_planner)

result = orchestrator.execute_natural_language_command(
    command="scene 1에서 토마토를 썰고, 불을 켜고 닫고, 냉장고에 토마토를 넣어.",
    scene="FloorPlan1"
)

orchestrator.shutdown_all_agents()
```](https://ai2thor.allenai.org/ithor/documentation/)
- [API 참조](https://ai2thor.allenai.org/ithor/documentation/)
- [데모](https://ai2thor.allenai.org/demo)
- [GitHub](https://github.com/allenai/ai2thor)
- [Google Colab 버전](https://github.com/allenai/ai2thor-colab)

## 다음 단계

1. `test_setup.py`를 실행하여 설치 확인
2. `example_basic.py`로 기본 사용법 학습
3. [공식 문서](https://ai2thor.allenai.org/ithor/documentation/)에서 더 많은 기능 탐색

## 추가 설정

### 특정 커밋 버전 설치
```bash
pip install --extra-index-url https://ai2thor-pypi.allenai.org ai2thor==0+COMMIT_ID
```

### Docker 사용
[AI2-THOR Docker](https://github.com/allenai/ai2thor-docker) 참조
