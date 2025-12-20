# AI2THOR Multi-Agent Navigation System

AI2THOR 환경에서 동작하는 **LLM 기반 멀티-에이전트 내비게이션 시스템**입니다.

## 🎯 주요 기능

### 1. LLM 기반 자연어 명령 처리
- **Ollama + llama3.2:3b 모델** 사용
- 한국어 자연어 명령을 작업으로 분해
- 작업 간 의존성 분석 및 최적 에이전트 수 결정

### 2. 지능형 내비게이션 시스템
- **GetReachablePositions + GetInteractablePoses** 교집합 활용
- 상하 시야 탐색 (좌우 회전 최소화)
- 스마트 충돌 회피 (좌우 번갈아가며 시도)
- 실제 도달 가능한 경로만 계산

### 3. 멀티-에이전트 병렬 실행
- 독립적인 작업 병렬 처리
- 에이전트별 비디오 POV 녹화 (30fps, avc1 codec)
- 에이전트 충돌 방지 (초기 위치 3m+ 분산)

### 4. 지원 작업 타입
- `slice_and_store`: 객체 자르기 + 저장
- `toggle_light`: 전등 제어
- `heat_object`: 전자레인지 사용
- `clean_object`: 싱크대 사용

## 📋 필수 요구사항

- **Python**: 3.8+
- **Ollama**: 로컬 LLM 서버
- **AI2THOR**: 5.0.0
- **OpenCV**: 비디오 녹화용

## 🚀 설치 및 실행

## 🚀 설치 및 실행

### 1. 의존성 설치

```bash
pip install -r requirements.txt
```

### 2. Ollama 설치 및 모델 다운로드

```bash
# macOS
brew install ollama

# Ollama 서버 시작
ollama serve

# 새 터미널에서 모델 다운로드
ollama pull llama3.2:3b
```

### 3. 실행

```bash
# 기본 명령 실행
python3 multi_agent_llm_prompting.py

# 커스텀 명령 실행
python3 multi_agent_llm_prompting.py "토마토를 썰어서 냉장고에 넣고, 불을 꺼줘"
```

## 📁 주요 파일 구조

```
ai2thor/
├── multi_agent_llm_prompting.py  # 메인 실행 파일 (LLM 통합)
├── navigation_utils.py            # 공통 내비게이션 로직
├── navigation_action.py           # 액션 단위 내비게이션 (병렬용)
├── multi_agent_parallel.py        # 병렬 실행 시스템
├── single_agent.py                # 단일 에이전트 실행
├── output_videos/                 # 녹화된 비디오 저장
└── requirements.txt               # 의존성 목록
```

## 🎮 사용 예시

### 예시 1: 단일 작업

```bash
python3 multi_agent_llm_prompting.py "토마토를 썰어서 냉장고에 넣어줘"
```

**실행 결과:**
- LLM 분석: 1개 작업 → 1명 에이전트
- Agent 0: 토마토 찾기 → 이동 → 자르기 → 픽업 → 냉장고로 이동 → 넣기
- 출력: `output_videos/agent0_YYYYMMDD_HHMMSS.mp4`

### 예시 2: 병렬 작업

```bash
python3 multi_agent_llm_prompting.py "토마토를 썰어서 냉장고에 넣고, 불을 꺼줘"
```

**실행 결과:**
- LLM 분석: 2개 독립 작업 → 2명 에이전트
- Agent 0: 토마토 → 냉장고
- Agent 1: 전등 스위치 → 끄기
- 출력: `agent0_*.mp4`, `agent1_*.mp4`

## 🔧 핵심 기술

### 1. 내비게이션 알고리즘

```
1. GetReachablePositions: 걸어갈 수 있는 모든 위치
2. GetInteractablePoses: 객체와 상호작용 가능한 위치
3. 교집합 계산: 실제 도달 가능한 상호작용 위치
4. 목표까지 이동 (충돌 회피)
5. 한 발자국 후진 (시야 확보)
6. 상하 시야로만 객체 탐색 (정면 → 아래 → 위)
```

### 2. 충돌 회피 전략

```
- 충돌 감지 시:
  1. 후진 (0.2m)
  2. 오른쪽/왼쪽 45도 회전
  3. 전진 시도
  4. 실패 시 반대 방향 시도
  5. 둘 다 실패 시 원래 방향 복귀
- 좌우 방향 번갈아가며 시도 (무한 루프 방지)
```

### 3. LLM 프롬프트 구조

```
- 사용자 명령 입력
- 작업 타입 정의 (slice_and_store, toggle_light 등)
- 작업 분해 및 의존성 분석
- 최적 에이전트 수 결정
- JSON 형식으로 작업 목록 반환
```

## 🎯 설정 가능 파라미터

### navigation_utils.py

```python
# 목표 도착 거리
dist <= 0.4  # 0.4m 이내면 도착으로 판단

# 진행 상황 체크
dist < last_distance - 0.1  # 0.1m 이상 줄어들면 진행으로 판단
consecutive_no_progress >= 8  # 8회 연속 진행 없으면 우회

# 회전 각도 임계값
abs(angle_diff) > 15  # 15도 이상 차이나면 회전
```

### multi_agent_llm_prompting.py

```python
# 비디오 설정
fps = 30
fourcc = cv2.VideoWriter_fourcc(*'avc1')

# 에이전트 초기 위치
min_distance_agents = 3.0  # 에이전트 간 최소 거리
min_distance_objects = 2.5  # 객체와 최소 거리

# LLM 설정
model = "llama3.2:3b"
timeout = 60  # 초
```

## 📊 출력 결과

### 터미널 출력

```
🤔 LLM 분석 중...
✓ 분석 완료
  - 작업 수: 2개
  - 필요 에이전트: 2명
  - 분석: Two independent tasks...

🎮 Controller 초기화 중...
✓ 초기화 완료

📦 씬 내 객체 수: 87개
📍 Agent0: (1.25, -0.75)
📍 Agent1: (-2.00, 1.50)

💡 작업 실행 시작

[Agent0] 🎯 작업: Tomato → Fridge
  🎯 목표 객체: Tomato|1|2|3
  📍 도달 가능한 위치: 243개
  📍 상호작용 가능한 위치: 8개
  🚶 목표 위치로 이동 중... (현재 거리: 3.45m)
  ✓ 목표 위치 도착! (거리: 0.38m)
  ⬅️ 한 발자국 후진 (시야 확보)
  👁️ 상하 시야로 객체 탐색
  ✅ 객체 발견! (정면)
  ...

✓ 녹화 완료 (총 1247 프레임)
📁 Agent0: agent0_20251220_143052.mp4
📁 Agent1: agent1_20251220_143052.mp4
```

### 비디오 출력

- **파일명**: `agent{id}_{timestamp}.mp4`
- **해상도**: 800x600
- **프레임레이트**: 30fps
- **코덱**: avc1 (H.264)
- **오버레이**: Agent 번호, 프레임 번호

## 🐛 문제 해결

## 🐛 문제 해결

### Ollama 연결 오류

```bash
❌ Ollama 연결 오류: [Errno 61] Connection refused
```

**해결:**
```bash
ollama serve  # 새 터미널에서 실행
```

### 모델을 찾을 수 없음

```bash
❌ Ollama 요청 실패: 404
```

**해결:**
```bash
ollama pull llama3.2:3b
```

### OpenCV 오류

```bash
ModuleNotFoundError: No module named 'cv2'
```

**해결:**
```bash
pip install opencv-python
```

### 에이전트가 객체를 찾지 못함

- **원인**: GetInteractablePoses가 빈 배열 반환
- **해결**: 씬에 해당 객체가 존재하는지 확인

### 에이전트가 무한히 회전

- **원인**: stuck 감지 로직 오작동
- **해결**: navigation_utils.py의 `consecutive_no_progress` 임계값 증가

## 🔍 기술 세부사항

### 사용된 AI2-THOR API

```python
# 위치 정보
GetReachablePositions()      # 걸어갈 수 있는 모든 위치
GetInteractablePoses(objectId)  # 객체와 상호작용 가능한 위치

# 이동
MoveAhead(moveMagnitude)     # 전진
MoveBack(moveMagnitude)      # 후진
RotateRight(degrees)          # 우회전
RotateLeft(degrees)           # 좌회전

# 시야
LookUp()                      # 고개 위로
LookDown()                    # 고개 아래로

# 상호작용
SliceObject(objectId)         # 자르기
PickupObject(objectId)        # 픽업
OpenObject(objectId)          # 열기
CloseObject(objectId)         # 닫기
PutObject(objectId)           # 넣기
ToggleObjectOn(objectId)      # 켜기
ToggleObjectOff(objectId)     # 끄기
```

### 좌표 시스템

- **X축**: 좌우 (양수: 오른쪽)
- **Y축**: 상하 (고정: 0.91)
- **Z축**: 앞뒤 (양수: 앞)
- **단위**: 미터(m)
- **그리드**: 0.25m

## 📚 참고 자료

- [AI2-THOR 공식 문서](https://ai2thor.allenai.org/ithor/documentation/)
- [Ollama 공식 사이트](https://ollama.ai/)
- [llama3.2 모델 정보](https://ollama.ai/library/llama3.2)

## 🤝 기여

이슈 및 PR은 언제나 환영합니다!

## 📄 라이선스

MIT License

---

**개발 환경:**
- Python: 3.13.2
- AI2-THOR: 5.0.0
- Ollama: llama3.2:3b
- 위치: `/Users/jaehwan/Desktop/JaeHwan/workspace/ai2thor`
