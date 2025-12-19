"""
로컬 LLM (Ollama gpt-oss) 사용 예제
완전 무료, API 키 불필요, 오프라인 사용 가능
"""

import json
import os
from multi_agent_system import (
    FunctionDatabase, 
    LLMTaskPlanner, 
    MultiAgentOrchestrator
)


def check_ollama_running():
    """Ollama 서버가 실행 중인지 확인"""
    import subprocess
    try:
        result = subprocess.run(
            ["curl", "-s", "http://localhost:11434/api/tags"],
            capture_output=True,
            timeout=2
        )
        if result.returncode == 0:
            print("✅ Ollama 서버가 실행 중입니다.")
            return True
        else:
            print("❌ Ollama 서버가 응답하지 않습니다.")
            return False
    except Exception as e:
        print(f"❌ Ollama 서버 확인 실패: {e}")
        return False


def check_gpt_oss_installed():
    """gpt-oss 모델이 설치되어 있는지 확인"""
    import subprocess
    try:
        result = subprocess.run(
            ["ollama", "list"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if "gpt-oss" in result.stdout:
            print("✅ gpt-oss 모델이 설치되어 있습니다.")
            return True
        else:
            print("❌ gpt-oss 모델이 설치되어 있지 않습니다.")
            print("   설치 방법: ollama pull gpt-oss:20b")
            return False
    except Exception as e:
        print(f"❌ 모델 확인 실패: {e}")
        return False


def example_local_llm_sequential():
    """예제: 로컬 LLM으로 순차적 작업 수행"""
    print("\n" + "="*80)
    print("예제: 로컬 LLM (gpt-oss) - 순차적 작업")
    print("="*80)
    
    # Ollama 확인
    if not check_ollama_running():
        print("\n❌ Ollama 서버를 먼저 시작해주세요:")
        print("   macOS: brew install ollama && ollama serve")
        print("   Linux: curl -fsSL https://ollama.com/install.sh | sh && ollama serve")
        return
    
    if not check_gpt_oss_installed():
        print("\n❌ gpt-oss 모델을 먼저 설치해주세요:")
        print("   ollama pull gpt-oss:20b")
        return
    
    # 시스템 초기화 (로컬 LLM 사용)
    function_db = FunctionDatabase()
    llm_planner = LLMTaskPlanner(function_db, use_local=True)  # 로컬 사용!
    orchestrator = MultiAgentOrchestrator(function_db, llm_planner)
    
    command = "scene 1에서 토마토를 썰고, 불을 켜고 닫고, 냉장고에 토마토를 넣어."
    
    try:
        print(f"\n💬 명령어: {command}")
        print("⏳ 로컬 LLM 분석 중...\n")
        
        result = orchestrator.execute_natural_language_command(
            command=command,
            scene="FloorPlan1",
            max_agents=5
        )
        
        # 결과 저장
        output_file = "results/example_local_llm_sequential.json"
        os.makedirs("results", exist_ok=True)
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        
        print(f"\n✅ 결과 저장: {output_file}")
        print(f"✅ 사용된 agent 수: {result['num_agents']}")
        print(f"✅ 분석: {result['analysis']}")
        print("\n💡 로컬 LLM 사용으로 API 비용 0원!")
        
        return result
        
    finally:
        orchestrator.shutdown_all_agents()


def example_local_llm_parallel():
    """예제: 로컬 LLM으로 병렬 작업 수행"""
    print("\n" + "="*80)
    print("예제: 로컬 LLM (gpt-oss) - 병렬 작업")
    print("="*80)
    
    if not check_ollama_running() or not check_gpt_oss_installed():
        return
    
    function_db = FunctionDatabase()
    llm_planner = LLMTaskPlanner(function_db, use_local=True)
    orchestrator = MultiAgentOrchestrator(function_db, llm_planner)
    
    command = """
    agent 1은 주방에서 사과를 찾아서 가져오고,
    agent 2는 거실에서 TV를 켜고,
    agent 3는 침실을 탐색해서 모든 서랍을 열어.
    """
    
    try:
        print(f"\n💬 명령어: {command}")
        print("⏳ 로컬 LLM 분석 중...\n")
        
        result = orchestrator.execute_natural_language_command(
            command=command,
            scene="FloorPlan1",
            max_agents=5
        )
        
        output_file = "results/example_local_llm_parallel.json"
        os.makedirs("results", exist_ok=True)
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        
        print(f"\n✅ 결과 저장: {output_file}")
        print(f"✅ 사용된 agent 수: {result['num_agents']}")
        print(f"✅ 분석: {result['analysis']}")
        print("\n💡 로컬 LLM 사용으로 API 비용 0원!")
        
        return result
        
    finally:
        orchestrator.shutdown_all_agents()


def compare_local_vs_cloud():
    """로컬 LLM vs 클라우드 API 비교"""
    print("\n" + "="*80)
    print("로컬 LLM vs 클라우드 API 비교")
    print("="*80)
    
    comparison = """
    
    ┌────────────────────┬────────────────────┬────────────────────┐
    │      항목          │  로컬 (gpt-oss)    │  클라우드 (GPT-4)  │
    ├────────────────────┼────────────────────┼────────────────────┤
    │ 비용               │ 무료 (0원)         │ 유료 (종량제)      │
    │ API 키 필요        │ 불필요             │ 필요               │
    │ 인터넷 연결        │ 불필요             │ 필수               │
    │ 프라이버시         │ 완전 보장          │ 데이터 전송        │
    │ 속도               │ 하드웨어 의존      │ 빠름               │
    │ 품질               │ 좋음               │ 최고               │
    │ 설치               │ 필요 (~12GB)       │ 불필요             │
    │ 메모리 요구사항    │ 16GB RAM           │ 없음               │
    └────────────────────┴────────────────────┴────────────────────┘
    
    💡 추천 사용 시나리오:
    
    📦 로컬 LLM (gpt-oss):
    - 개발 및 테스트
    - 프로토타이핑
    - 프라이버시가 중요한 경우
    - 비용 절감이 필요한 경우
    - 인터넷 연결이 불안정한 환경
    
    ☁️ 클라우드 API (GPT-4):
    - 프로덕션 환경
    - 최고 품질이 필요한 경우
    - 로컬 리소스가 부족한 경우
    - 빠른 응답이 필요한 경우
    """
    
    print(comparison)


def setup_instructions():
    """Ollama 및 gpt-oss 설치 안내"""
    print("\n" + "="*80)
    print("Ollama 및 gpt-oss 설치 방법")
    print("="*80)
    
    instructions = """
    
    🍎 macOS:
    ────────────────────────────────────────────────────────────
    # 1. Ollama 설치
    brew install ollama
    
    # 2. Ollama 서버 시작
    ollama serve
    
    # 3. 새 터미널에서 gpt-oss 다운로드
    ollama pull gpt-oss:20b
    
    
    🐧 Linux:
    ────────────────────────────────────────────────────────────
    # 1. Ollama 설치
    curl -fsSL https://ollama.com/install.sh | sh
    
    # 2. Ollama 서버 시작
    ollama serve
    
    # 3. 새 터미널에서 gpt-oss 다운로드
    ollama pull gpt-oss:20b
    
    
    🐳 Docker (모든 OS):
    ────────────────────────────────────────────────────────────
    # 1. Ollama 컨테이너 실행
    docker run -d -v ollama:/root/.ollama -p 11434:11434 \\
        --name ollama ollama/ollama
    
    # 2. gpt-oss 다운로드
    docker exec -it ollama ollama pull gpt-oss:20b
    
    # 3. 모델 실행
    docker exec -it ollama ollama run gpt-oss:20b
    
    
    ✅ 설치 확인:
    ────────────────────────────────────────────────────────────
    # Ollama 서버 확인
    curl http://localhost:11434/api/tags
    
    # 설치된 모델 확인
    ollama list
    
    # 모델 테스트
    ollama run gpt-oss:20b "안녕하세요!"
    
    
    📦 시스템 요구사항:
    ────────────────────────────────────────────────────────────
    - RAM: 16GB 이상 (20b 모델)
    - 디스크: 15GB 이상 여유 공간
    - CPU: 다중 코어 (GPU 선택사항)
    
    
    🚀 사용 시작:
    ────────────────────────────────────────────────────────────
    # 예제 실행
    python example_local_llm.py 1    # 순차적 작업
    python example_local_llm.py 2    # 병렬 작업
    python example_local_llm.py compare  # 비교표 보기
    """
    
    print(instructions)
    print("\n📚 자세한 정보: GPT_OSS_LOCAL_SETUP.md 참고")


def main():
    """메인 함수"""
    import sys
    
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == "1":
            example_local_llm_sequential()
        elif command == "2":
            example_local_llm_parallel()
        elif command == "compare":
            compare_local_vs_cloud()
        elif command == "setup":
            setup_instructions()
        else:
            print("사용법:")
            print("  python example_local_llm.py 1        # 순차적 작업 예제")
            print("  python example_local_llm.py 2        # 병렬 작업 예제")
            print("  python example_local_llm.py compare  # 로컬 vs 클라우드 비교")
            print("  python example_local_llm.py setup    # 설치 안내")
    else:
        print("\n" + "="*80)
        print("로컬 LLM (Ollama gpt-oss) 예제")
        print("="*80)
        print("\n💡 완전 무료, API 키 불필요, 오프라인 사용 가능!\n")
        
        print("사용 가능한 명령:")
        print("  python example_local_llm.py 1        # 순차적 작업 예제")
        print("  python example_local_llm.py 2        # 병렬 작업 예제")
        print("  python example_local_llm.py compare  # 로컬 vs 클라우드 비교")
        print("  python example_local_llm.py setup    # 설치 안내")
        
        print("\n" + "="*80)
        setup_instructions()


if __name__ == "__main__":
    main()
