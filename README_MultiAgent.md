# AI2THOR Multi-Agent System with LLM-based Task Planning

자연어 명령어를 입력하면 LLM(Claude Sonnet)이 작업을 분석하여 여러 AI2THOR 에이전트를 생성하고, 각 에이전트에게 작업을 할당하여 병렬로 실행하는 시스템입니다.

## 🎯 주요 기능

### 1. **AI2THOR API 함수 데이터베이스**
- 모든 AI2THOR 함수를 카테고리별로 정리
- Navigation, Interaction, Object Manipulation, Scene Control 등
- 150+ 개의 함수와 파라미터 정보 포함

### 2. **LLM 기반 작업 계획**
- 자연어 명령어를 AI2THOR 액션으로 자동 변환
- Claude Sonnet 4를 사용한 지능형 작업 분해
- 에이전트 수, 작업 우선순위, 의존성 자동 결정

### 3. **멀티-에이전트 병렬 실행**
- 여러 에이전트가 동시에 독립적으로 작업 수행
- ThreadPoolExecutor를 사용한 효율적인 병렬 처리
- 각 에이전트는 독립적인 AI2THOR Controller 보유

### 4. **작업 조정 및 의존성 관리**
- 작업 간 의존성 자동 처리
- 우선순위 기반 작업 스케줄링
- 실시간 실행 로그 및 결과 추적

## 📁 프로젝트 구조

```
ai2thor/
├── ai2thor_functions_db.json          # AI2THOR 함수 데이터베이스
├── multi_agent_system.py              # 멀티-에이전트 시스템 메인 코드
├── example_multi_agent_scenarios.py   # 다양한 사용 예제
├── requirements.txt                    # 의존성 패키지
├── README.md                          # 이 파일
└── results/                           # 실행 결과 저장 디렉토리
    ├── example_1_exploration.json
    ├── example_2_gathering.json
    └── ...
```

## 🚀 설치 및 설정

### 1. 필수 패키지 설치

```bash
pip install ai2thor anthropic
```

또는 requirements.txt 사용:

```bash
pip install -r requirements.txt
```

### 2. Anthropic API 키 설정

```bash
export ANTHROPIC_API_KEY="your-api-key-here"
```

또는 코드에서 직접 설정:

```python
llm_planner = LLMTaskPlanner(function_db, api_key="your-api-key")
```

## 💡 사용 방법

### 기본 사용법

```python
from multi_agent_system import (
    FunctionDatabase, 
    LLMTaskPlanner, 
    MultiAgentOrchestrator
)

# 시스템 초기화
function_db = FunctionDatabase()
llm_planner = LLMTaskPlanner(function_db)
orchestrator = MultiAgentOrchestrator(function_db, llm_planner)

# 자연어 명령어 실행
command = """
Create 3 agents. 
Agent 1 should move to the kitchen and pick up an apple.
Agent 2 should go to the living room and turn on the TV.
Agent 3 should explore the bedroom and open all drawers.
"""

result = orchestrator.execute_natural_language_command(
    command=command,
    scene="FloorPlan1",
    max_agents=5
)

# 정리
orchestrator.shutdown_all_agents()
```

### 예제 실행

#### 단일 예제 실행
```bash
# 예제 1: 병렬 탐색
python example_multi_agent_scenarios.py 1

# 예제 2: 객체 수집
python example_multi_agent_scenarios.py 2

# 예제 3: 순차 작업
python example_multi_agent_scenarios.py 3
```

#### 모든 예제 실행
```bash
python example_multi_agent_scenarios.py all
```

## 📖 예제 시나리오

### 예제 1: 병렬 탐색
여러 에이전트가 동시에 다른 영역을 탐색하고 객체를 보고합니다.

```python
command = """
Create 3 exploration agents. 
Agent 1 should explore the kitchen area.
Agent 2 should explore the living room.
Agent 3 should survey the entire room by rotating 360 degrees.
"""
```

### 예제 2: 객체 수집
에이전트들이 협력하여 여러 객체를 수집하고 배치합니다.

```python
command = """
Agent 1: Find and pick up an apple, place it on the dining table.
Agent 2: Find a mug, fill it with water, place it on the counter.
"""
```

### 예제 3: 순차 작업
의존성이 있는 작업들을 순서대로 수행합니다.

```python
command = """
Agent 1: Open the refrigerator first.
Agent 2: After Agent 1 finishes, pick up an egg from the fridge.
Agent 1: Then close the refrigerator.
Agent 2: Take the egg to the microwave.
"""
```

### 예제 4: 환경 조작
여러 에이전트가 동시에 환경을 변경합니다.

```python
command = """
Agent 1: Turn on all lights.
Agent 2: Open all cabinets and drawers.
Agent 3: Clean any dirty objects.
"""
```

### 예제 5: 검색 및 보고
각 에이전트가 특정 카테고리의 객체를 찾아 보고합니다.

```python
command = """
Agent 1: Search for fruit.
Agent 2: Search for electronic devices.
Agent 3: Search for books.
Agent 4: Search for cleaning supplies.
"""
```

### 예제 6: 복잡한 조정
여러 에이전트가 복잡한 요리 준비 작업을 조정합니다.

```python
command = """
Agent 1: Gather ingredients from the fridge.
Agent 2: Prepare and slice items.
Agent 3: Clean the workspace before and after.
Agents should coordinate in the correct order.
"""
```

## 🏗️ 시스템 아키텍처

### 1. FunctionDatabase
- AI2THOR의 모든 함수 정보를 관리
- 키워드 기반 검색 기능
- 함수 파라미터 및 설명 제공

### 2. LLMTaskPlanner
- Claude Sonnet을 사용한 자연어 처리
- 명령어를 TaskPlan 객체로 변환
- 에이전트 수와 작업 배분 결정

### 3. AI2THORAgent
- 개별 에이전트 클래스
- 독립적인 Controller 보유
- 액션 실행 및 로깅

### 4. MultiAgentOrchestrator
- 전체 시스템 조정
- 에이전트 생성 및 관리
- 병렬 실행 및 결과 집계

## 📊 실행 결과 형식

실행 결과는 JSON 형식으로 저장됩니다:

```json
{
  "command": "원본 명령어",
  "analysis": "LLM의 작업 분석",
  "num_agents": 3,
  "num_tasks": 5,
  "task_results": [
    {
      "agent_id": "agent_1",
      "task_description": "작업 설명",
      "total_actions": 10,
      "successful_actions": 9,
      "failed_actions": 1,
      "results": [...],
      "execution_log": [...]
    }
  ],
  "agent_final_states": {
    "agent_1": {
      "agent_position": {"x": 1.0, "y": 0.9, "z": -1.5},
      "objects_in_view": [...]
    }
  }
}
```

## 🔧 고급 사용법

### 컨텍스트 제공

```python
context = {
    "scene_info": "Kitchen with modern appliances",
    "available_objects": ["apple", "mug", "knife"],
    "constraints": "Avoid breaking fragile objects"
}

result = orchestrator.execute_natural_language_command(
    command=command,
    scene="FloorPlan1",
    context=context
)
```

### 에이전트 설정 커스터마이징

```python
from multi_agent_system import AgentConfig, AI2THORAgent

config = AgentConfig(
    agent_id="custom_agent",
    scene="FloorPlan1",
    initial_position={"x": 1.0, "y": 0.9, "z": -1.0},
    initial_rotation={"x": 0, "y": 90, "z": 0}
)

agent = AI2THORAgent(config)
agent.initialize(
    gridSize=0.125,  # 더 작은 그리드 크기
    renderDepthImage=True,  # 깊이 이미지 렌더링
    width=512,
    height=512
)
```

### 수동 TaskPlan 생성

```python
from multi_agent_system import TaskPlan

task_plan = TaskPlan(
    description="Pick up an apple",
    actions=[
        {
            "action": "MoveAhead",
            "parameters": {"moveMagnitude": 0.25},
            "reason": "Move closer to object"
        },
        {
            "action": "PickupObject",
            "parameters": {"objectId": "Apple|1|1|1"},
            "reason": "Pick up the apple"
        }
    ],
    agent_id="agent_1",
    priority=1
)

agent.execute_task_plan(task_plan)
```

## 🎓 AI2THOR 함수 카테고리

### Navigation (이동)
- MoveAhead, MoveBack, MoveLeft, MoveRight
- RotateLeft, RotateRight
- LookUp, LookDown
- Crouch, Stand
- Teleport, TeleportFull

### Interaction (상호작용)
- PickupObject, PutObject, DropHandObject
- ThrowObject
- OpenObject, CloseObject
- ToggleObjectOn, ToggleObjectOff
- SliceObject, BreakObject, CookObject
- DirtyObject, CleanObject
- FillObjectWithLiquid, EmptyLiquidFromObject

### Held Object Manipulation (들고 있는 물체 조작)
- MoveHeldObjectAhead/Back/Left/Right/Up/Down
- MoveHeldObject (복합 이동)
- RotateHeldObject

### Object Physics (물리)
- PushObject, PullObject, DirectionalPush
- TouchThenApplyForce
- PausePhysicsAutoSim, UnpausePhysicsAutoSim
- AdvancePhysicsStep

### Scene Manipulation (씬 조작)
- InitialRandomSpawn
- RandomizeMaterials, RandomizeColors, RandomizeLighting
- SetObjectPoses, PlaceObjectAtPoint
- RemoveFromScene, DisableObject, EnableObject

### Query (쿼리)
- GetReachablePositions
- GetObjectInFrame
- GetCoordinateFromRaycast
- GetInteractablePoses
- GetSpawnCoordinatesAboveReceptacle

### Camera (카메라)
- AddThirdPartyCamera
- UpdateThirdPartyCamera

## 🐛 문제 해결

### 일반적인 문제

**1. "No module named 'ai2thor'"**
```bash
pip install ai2thor
```

**2. "ANTHROPIC_API_KEY not found"**
```bash
export ANTHROPIC_API_KEY="your-key"
```

**3. 에이전트가 충돌 또는 이동 실패**
- gridSize를 조정하거나 snapToGrid를 False로 설정
- forceAction=True 사용 (주의: 비현실적 동작 가능)

**4. 액션이 실패함**
- 객체가 visibilityDistance 내에 있는지 확인
- 객체 ID가 정확한지 확인
- 에이전트가 적절한 위치에 있는지 확인

### 로깅 활성화

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## 📚 참고 자료

- [AI2THOR 공식 문서](https://ai2thor.allenai.org/)
- [AI2THOR GitHub](https://github.com/allenai/ai2thor)
- [Anthropic Claude API](https://docs.anthropic.com/)

## 🤝 기여

이슈나 개선 사항이 있으면 자유롭게 제안해주세요!

## 📄 라이센스

이 프로젝트는 MIT 라이센스를 따릅니다.

## 🎉 주요 특징 요약

✅ **자연어 인터페이스**: 복잡한 AI2THOR API를 몰라도 자연어로 명령 가능
✅ **자동 작업 분해**: LLM이 명령어를 분석하여 최적의 작업 계획 수립
✅ **병렬 실행**: 여러 에이전트가 동시에 작업하여 효율성 극대화
✅ **유연한 확장**: 새로운 시나리오나 작업을 쉽게 추가 가능
✅ **상세한 로깅**: 모든 액션과 결과를 추적하여 디버깅 용이
✅ **재현 가능**: JSON 결과를 통해 실험 재현 가능

---

**Made with ❤️ using AI2THOR and Claude Sonnet**
