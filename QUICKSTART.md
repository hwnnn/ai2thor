# 🚀 빠른 시작 가이드

AI2THOR 멀티-에이전트 시스템을 빠르게 시작하는 방법입니다.

## 📦 두 가지 옵션

### 옵션 1: 로컬 LLM (무료, 추천!) 🌟

**장점:**
- ✅ 완전 무료 (API 비용 0원)
- ✅ API 키 불필요
- ✅ 오프라인 사용 가능
- ✅ 프라이버시 보장

**설치:**
```bash
# 1. Ollama 설치
brew install ollama  # macOS
# 또는
curl -fsSL https://ollama.com/install.sh | sh  # Linux

# 2. Ollama 서버 시작
ollama serve

# 3. 새 터미널에서 gpt-oss 다운로드 (~12GB)
ollama pull gpt-oss:20b

# 4. 테스트
ollama run gpt-oss:20b "안녕하세요!"
```

**사용:**
```bash
# 예제 실행
python local_llm.py 1    # 순차적 작업
python local_llm.py 2    # 병렬 작업
```

**Python 코드:**
```python
from multi_agent_system import *

function_db = FunctionDatabase()
llm_planner = LLMTaskPlanner(function_db, use_local=True)  # 로컬!
orchestrator = MultiAgentOrchestrator(function_db, llm_planner)

result = orchestrator.execute_natural_language_command(
    command="scene 1에서 토마토를 썰고, 불을 켜고 닫고, 냉장고에 토마토를 넣어.",
    scene="FloorPlan1"
)

orchestrator.shutdown_all_agents()
```

### 옵션 2: OpenAI GPT-4 (유료)

**장점:**
- ✅ 최고 품질
- ✅ 빠른 응답
- ✅ 설치 불필요

**단점:**
- ❌ API 비용 발생
- ❌ 인터넷 필요

**설정:**
```bash
# API 키 설정
export OPENAI_API_KEY="sk-..."

# 예제 실행
python korean_commands.py 1
```

**Python 코드:**
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

## 📊 비교표

| 항목 | 로컬 gpt-oss | OpenAI GPT-4 |
|-----|-------------|--------------|
| 비용 | **무료** | 유료 (종량제) |
| API 키 | **불필요** | 필요 |
| 인터넷 | **불필요** | 필수 |
| 프라이버시 | **완전 보장** | 데이터 전송 |
| 품질 | 좋음 | **최고** |
| 속도 | 하드웨어 의존 | **빠름** |
| 설치 | 필요 (~12GB) | **불필요** |

## 💡 어떤 것을 선택해야 할까?

### 로컬 LLM (gpt-oss)을 선택하세요 만약:
- 개발 및 테스트 중이라면
- API 비용을 절감하고 싶다면
- 프라이버시가 중요하다면
- 오프라인 환경이라면
- 16GB 이상 RAM이 있다면

### OpenAI GPT-4를 선택하세요 만약:
- 프로덕션 환경이라면
- 최고 품질이 필요하다면
- 로컬 리소스가 부족하다면
- 빠른 응답이 필요하다면

## 🛠️ 시스템 요구사항

### 로컬 LLM (gpt-oss-20b)
- **RAM:** 16GB 이상
- **디스크:** 15GB 이상 여유 공간
- **CPU:** 다중 코어 (GPU 선택사항)
- **OS:** macOS, Linux, Windows (Docker)

### OpenAI GPT-4
- **인터넷:** 안정적인 연결
- **API 키:** OpenAI 계정
- **시스템:** 제한 없음

## 📚 더 알아보기

- [GPT_OSS_LOCAL_SETUP.md](GPT_OSS_LOCAL_SETUP.md) - 상세 로컬 설치 가이드
- [README_MultiAgent.md](README_MultiAgent.md) - 멀티-에이전트 시스템 설명
- [README.md](README.md) - 전체 프로젝트 개요

## 🎯 다음 단계

1. ✅ 위의 두 옵션 중 하나를 선택하여 설치
2. ✅ 예제 실행으로 테스트
3. ✅ 자신만의 한국어 명령어 작성
4. ✅ AI2THOR 환경에서 다양한 작업 시도

## 🆘 문제 해결

### Ollama 서버가 시작되지 않음
```bash
pkill ollama
ollama serve
```

### gpt-oss 모델 다운로드 실패
```bash
# 이전 다운로드 삭제
ollama rm gpt-oss:20b

# 다시 다운로드
ollama pull gpt-oss:20b
```

### OpenAI API 키 오류
```bash
# 환경 변수 확인
echo $OPENAI_API_KEY

# 다시 설정
export OPENAI_API_KEY="sk-..."
```

## 💬 예제 명령어

```python
# 순차적 작업 (1개 agent)
"scene 1에서 토마토를 썰고, 불을 켜고 닫고, 냉장고에 토마토를 넣어."

# 병렬 작업 (여러 agent)
"agent 1은 주방에서 사과를 찾고, agent 2는 거실에서 TV를 켜."

# 복잡한 작업
"주방에서 요리를 준비해줘. 냉장고에서 재료를 꺼내고, 토마토를 썰고, 접시에 담아."

# 검색 작업
"집 전체에서 열쇠를 찾아줘. 여러 agent가 동시에 다른 방을 탐색해."
```

---

**시작하세요! 🚀**

로컬 LLM으로 무료로 시작하거나, GPT-4로 최고 품질을 경험하세요!
