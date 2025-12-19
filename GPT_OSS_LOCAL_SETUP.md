# GPT-OSS 로컬 설치 가이드

OpenAI의 gpt-oss 오픈소스 LLM을 로컬에 설치하여 사용하는 방법입니다.

## 방법 1: Ollama 사용 (추천) 🌟

Ollama는 Docker 기반으로 LLM을 로컬에서 쉽게 실행할 수 있는 도구입니다.

### 1. Ollama 설치

#### macOS
```bash
# Homebrew 사용
brew install ollama

# 또는 공식 웹사이트에서 다운로드
# https://ollama.com/download
```

#### Linux
```bash
curl -fsSL https://ollama.com/install.sh | sh
```

### 2. GPT-OSS 모델 다운로드 및 실행

```bash
# gpt-oss-20b (작은 모델, 빠른 속도)
ollama pull gpt-oss:20b
ollama run gpt-oss:20b

# gpt-oss-120b (큰 모델, 높은 성능)
ollama pull gpt-oss:120b
ollama run gpt-oss:120b
```

### 3. API 서버로 실행

```bash
# 백그라운드에서 API 서버 실행
ollama serve

# 또는 특정 모델을 API 서버로 실행
ollama run gpt-oss:20b
```

API 엔드포인트: `http://localhost:11434`

### 4. Python에서 사용

```bash
pip install openai
```

```python
from openai import OpenAI

# Ollama API 클라이언트
client = OpenAI(
    base_url="http://localhost:11434/v1",
    api_key="ollama"  # Ollama는 API 키가 필요없지만 형식상 필요
)

response = client.chat.completions.create(
    model="gpt-oss:20b",
    messages=[
        {"role": "user", "content": "안녕하세요!"}
    ]
)

print(response.choices[0].message.content)
```

## 방법 2: Docker 직접 사용

### 1. Docker 설치

- macOS: [Docker Desktop](https://www.docker.com/products/docker-desktop/)
- Linux: `sudo apt install docker.io` (Ubuntu/Debian)

### 2. Ollama Docker 이미지 실행

```bash
# Ollama 컨테이너 실행
docker run -d -v ollama:/root/.ollama -p 11434:11434 --name ollama ollama/ollama

# 모델 다운로드
docker exec -it ollama ollama pull gpt-oss:20b

# 모델 실행
docker exec -it ollama ollama run gpt-oss:20b
```

## 방법 3: Python vLLM 사용

고성능이 필요하고 GPU가 있는 경우:

```bash
# vLLM 설치
pip install --pre vllm==0.10.1+gptoss \
    --extra-index-url https://wheels.vllm.ai/gpt-oss/ \
    --extra-index-url https://download.pytorch.org/whl/nightly/cu128 \
    --index-strategy unsafe-best-match

# 서버 실행
vllm serve openai/gpt-oss-20b
```

## AI2THOR 멀티-에이전트 시스템에 통합

### 1. 로컬 Ollama 사용하도록 수정

`multi_agent_system.py`를 다음과 같이 수정:

```python
from openai import OpenAI

class LLMTaskPlanner:
    def __init__(self, function_db: FunctionDatabase, api_key: Optional[str] = None, use_local=False):
        self.function_db = function_db
        
        if use_local:
            # Ollama 로컬 서버 사용
            self.client = OpenAI(
                base_url="http://localhost:11434/v1",
                api_key="ollama"
            )
            self.model = "gpt-oss:20b"
        else:
            # OpenAI API 사용
            self.client = OpenAI(api_key=api_key or os.environ.get("OPENAI_API_KEY"))
            self.model = "gpt-4"
```

### 2. 로컬 모델로 실행

```python
from multi_agent_system import *

function_db = FunctionDatabase()
llm_planner = LLMTaskPlanner(function_db, use_local=True)  # 로컬 모델 사용
orchestrator = MultiAgentOrchestrator(function_db, llm_planner)

result = orchestrator.execute_natural_language_command(
    command="scene 1에서 토마토를 썰고, 불을 켜고 닫고, 냉장고에 토마토를 넣어.",
    scene="FloorPlan1"
)

orchestrator.shutdown_all_agents()
```

## 모델 비교

| 모델 | 파라미터 | 메모리 | 속도 | 품질 | 용도 |
|-----|---------|--------|------|------|------|
| gpt-oss-20b | 21B | ~12GB | 빠름 | 좋음 | 일반 작업, 빠른 응답 |
| gpt-oss-120b | 117B | ~70GB | 느림 | 우수 | 복잡한 추론, 고품질 |
| GPT-4 (OpenAI) | ? | Cloud | 중간 | 최고 | 비용 발생, 최고 품질 |

## 시스템 요구사항

### gpt-oss-20b
- RAM: 16GB 이상
- GPU: 선택사항 (CPU만으로도 실행 가능, 느림)
- 디스크: 15GB 이상

### gpt-oss-120b
- RAM: 80GB 이상
- GPU: H100 80GB 또는 유사
- 디스크: 80GB 이상

## 장단점

### Ollama (로컬)
**장점:**
- ✅ 완전 무료
- ✅ API 키 불필요
- ✅ 오프라인 사용 가능
- ✅ 프라이버시 보호
- ✅ 설치 및 사용 간단

**단점:**
- ❌ 초기 모델 다운로드 시간 (20b: ~12GB, 120b: ~70GB)
- ❌ 로컬 리소스 사용
- ❌ GPT-4보다 성능 낮음

### OpenAI GPT-4 (클라우드)
**장점:**
- ✅ 최고 품질
- ✅ 빠른 응답
- ✅ 리소스 불필요

**단점:**
- ❌ API 비용 발생
- ❌ API 키 필요
- ❌ 인터넷 필요
- ❌ 프라이버시 우려

## 추천 사용 시나리오

### gpt-oss-20b (로컬, Ollama)
- 개발 및 테스트
- 프로토타이핑
- 프라이버시가 중요한 경우
- 비용 절감이 중요한 경우

### GPT-4 (OpenAI)
- 프로덕션 환경
- 최고 품질이 필요한 경우
- 로컬 리소스가 부족한 경우

## 문제 해결

### Ollama 서버가 시작되지 않음
```bash
# Ollama 재시작
pkill ollama
ollama serve
```

### 모델 다운로드 실패
```bash
# 이전 다운로드 삭제
ollama rm gpt-oss:20b

# 다시 다운로드
ollama pull gpt-oss:20b
```

### Docker 권한 오류 (Linux)
```bash
sudo usermod -aG docker $USER
newgrp docker
```

## 참고 자료

- [Ollama 공식 문서](https://ollama.com)
- [gpt-oss GitHub](https://github.com/openai/gpt-oss)
- [gpt-oss Ollama 가이드](https://cookbook.openai.com/articles/gpt-oss/run-locally-ollama)
- [Ollama 모델 라이브러리](https://ollama.com/library/gpt-oss)
