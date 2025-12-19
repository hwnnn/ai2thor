# 🎬 멀티-에이전트 시각화 시스템

여러 AI2THOR 에이전트의 동작을 실시간으로 시각화하는 시스템입니다.

## 🌟 주요 기능

### 1. 탑뷰 카메라 (Top View)
- 씬 전체를 위에서 내려다보는 시점
- 모든 에이전트의 위치를 실시간으로 표시
- 색상으로 각 에이전트 구분

### 2. 에이전트 1인칭 뷰 (Agent POV)
- 각 에이전트의 시점에서 보는 화면
- 독립적인 비디오 파일로 저장
- 최대 5개 에이전트 동시 지원

### 3. 통합 뷰 (Combined View)
- 탑뷰 + 모든 에이전트 POV를 한 화면에
- 1920x1080 고해상도
- 실시간 프레임 카운터

## 📹 생성되는 비디오 파일

```
output_videos/
├── topview_20231219_143022.mp4      # 탑뷰 (모든 agent 위치)
├── agent_1_pov_20231219_143022.mp4  # Agent 1 1인칭 시점
├── agent_2_pov_20231219_143022.mp4  # Agent 2 1인칭 시점
├── agent_3_pov_20231219_143022.mp4  # Agent 3 1인칭 시점
└── combined_20231219_143022.mp4     # 통합 뷰
```

## 🚀 빠른 시작

### 방법 1: 간단한 데모

```bash
python visualization_demo.py local
```

### 방법 2: Python 코드에서 사용

```python
from multi_agent_system import (
    FunctionDatabase, 
    LLMTaskPlanner, 
    MultiAgentOrchestrator
)

# 시스템 초기화
function_db = FunctionDatabase()
llm_planner = LLMTaskPlanner(function_db, use_local=True)
orchestrator = MultiAgentOrchestrator(function_db, llm_planner)

# 시각화 활성화
orchestrator.enable_visualization()

# 명령어 실행 (비디오 녹화)
result = orchestrator.execute_natural_language_command(
    command="3개의 에이전트가 각각 다른 방향으로 탐색해.",
    scene="FloorPlan1",
    enable_video=True,
    video_duration=30  # 30초 녹화
)

# 종료
orchestrator.shutdown_all_agents()
```

## 📊 사용 예제

### 예제 1: 병렬 탐색

```python
command = """
3개의 에이전트를 생성해서 병렬로 탐색해.
agent 1은 주방을 탐색하고,
agent 2는 거실을 탐색하고,
agent 3는 침실을 탐색해.
"""

result = orchestrator.execute_natural_language_command(
    command=command,
    scene="FloorPlan1",
    enable_video=True,
    video_duration=30
)
```

### 예제 2: 순차적 작업

```python
command = """
2개의 에이전트가 순차적으로 작업해.
agent 1이 먼저 토마토를 자르고,
agent 2가 그 다음에 접시에 담아.
"""

result = orchestrator.execute_natural_language_command(
    command=command,
    scene="FloorPlan1",
    enable_video=True,
    video_duration=20
)
```

### 예제 3: 시각화 없이 실행

```python
# 시각화를 원하지 않으면 enable_video=False
result = orchestrator.execute_natural_language_command(
    command="에이전트가 전진하고 회전해.",
    scene="FloorPlan1",
    enable_video=False  # 비디오 녹화 비활성화
)
```

## ⚙️ 설정 옵션

### MultiAgentOrchestrator.execute_natural_language_command()

| 파라미터 | 타입 | 기본값 | 설명 |
|---------|------|--------|------|
| `command` | str | 필수 | 자연어 명령어 |
| `scene` | str | "FloorPlan1" | AI2THOR 씬 이름 |
| `max_agents` | int | 5 | 최대 에이전트 수 |
| `enable_video` | bool | False | 비디오 녹화 활성화 |
| `video_duration` | int | 30 | 녹화 시간 (초) |

### MultiAgentVisualizer 설정

```python
visualizer = MultiAgentVisualizer(output_dir="output_videos")
visualizer.fps = 10  # 초당 프레임 수 (기본: 10)
```

## 🎨 비디오 해상도

| 비디오 타입 | 해상도 | 설명 |
|------------|--------|------|
| 탑뷰 | 1920x1080 | 전체 씬 오버뷰 |
| Agent POV | 800x600 | 각 에이전트 시점 |
| 통합 뷰 | 1920x1080 | 탑뷰(좌) + POV(우) |

## 🎯 에이전트 색상 코드

- **Agent 1**: 초록 (Green)
- **Agent 2**: 파랑 (Blue)
- **Agent 3**: 빨강 (Red)
- **Agent 4**: 청록 (Cyan)
- **Agent 5**: 마젠타 (Magenta)

## 💡 활용 예시

### 1. 연구 논문용
- 멀티-에이전트 협업 연구
- 에이전트 행동 분석
- 알고리즘 성능 비교

### 2. 교육용
- AI2THOR 사용법 데모
- 멀티-에이전트 개념 설명
- 시각적 프레젠테이션

### 3. 디버깅
- 에이전트 경로 확인
- 충돌 문제 분석
- 작업 할당 검증

## 🔧 시스템 요구사항

### 최소 요구사항
- Python 3.8+
- RAM: 8GB 이상
- GPU: 선택사항 (CPU 가능)
- 디스크: 2GB 여유 공간

### 권장 사항
- Python 3.10+
- RAM: 16GB 이상
- GPU: NVIDIA (CUDA 지원)
- SSD

## 📝 예제 명령어

```python
# 간단한 탐색
"3개의 에이전트가 각각 다른 방향으로 탐색해."

# 객체 찾기
"agent 1은 사과를 찾고, agent 2는 컵을 찾아."

# 복잡한 작업
"주방에서 요리를 준비해. agent 1은 재료를 모으고, agent 2는 썰고, agent 3는 요리해."

# 순차적 작업
"agent 1이 먼저 냉장고를 열고, agent 2가 음식을 꺼내고, agent 3가 냉장고를 닫아."
```

## 🐛 문제 해결

### 비디오가 생성되지 않음
```python
# 시각화가 활성화되었는지 확인
orchestrator.enable_visualization()

# enable_video=True 확인
result = orchestrator.execute_natural_language_command(
    command="...",
    enable_video=True  # 이것을 True로!
)
```

### 프레임이 끊김
```python
# FPS를 낮춰보세요
visualizer.fps = 5  # 기본 10에서 5로
```

### 에이전트 위치가 안 보임
```python
# 탑뷰 카메라 높이 조정
self.top_view_controller.step(
    action='Teleport',
    position=dict(x=center_x, y=4.0, z=center_z),  # y 값 증가
    rotation=dict(x=90, y=0, z=0)
)
```

### OpenCV 에러
```bash
pip install opencv-python
```

## 📚 관련 문서

- [README.md](README.md) - 프로젝트 개요
- [QUICKSTART.md](QUICKSTART.md) - 빠른 시작
- [multi_agent_system.py](multi_agent_system.py) - 시스템 코어
- [multi_agent_visualizer.py](multi_agent_visualizer.py) - 시각화 클래스

## 🎥 비디오 예제

실행 후 `output_videos/` 디렉토리를 확인하세요:

```bash
ls -lh output_videos/
```

결과:
```
-rw-r--r--  topview_20231219_143022.mp4       (25MB)
-rw-r--r--  agent_1_pov_20231219_143022.mp4   (15MB)
-rw-r--r--  agent_2_pov_20231219_143022.mp4   (15MB)
-rw-r--r--  agent_3_pov_20231219_143022.mp4   (15MB)
-rw-r--r--  combined_20231219_143022.mp4      (45MB)
```

## 🚦 시작하세요!

```bash
# 1. 로컬 LLM 데모 (무료)
python visualization_demo.py local

# 2. GPT-4 데모 (유료, 고품질)
export OPENAI_API_KEY="sk-..."
python visualization_demo.py gpt4

# 3. 간단한 테스트
python visualization_demo.py simple
```

---

**Happy Visualizing! 🎬**
