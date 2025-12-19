"""
한국어 자연어 명령어 예제
GPT-4를 사용하여 최소한의 agent로 작업 수행
"""

import json
import os
from multi_agent_system import (
    FunctionDatabase, 
    LLMTaskPlanner, 
    MultiAgentOrchestrator
)


def example_korean_sequential():
    """예제 1: 순차적 작업 (1개 agent만 필요)"""
    print("\n" + "="*80)
    print("예제 1: 순차적 작업 - 토마토 썰고, 불 켜고 끄고, 냉장고에 넣기")
    print("="*80)
    
    # 시스템 초기화
    function_db = FunctionDatabase()
    llm_planner = LLMTaskPlanner(function_db)
    orchestrator = MultiAgentOrchestrator(function_db, llm_planner)
    
    command = "scene 1에서 토마토를 썰고, 불을 켜고 닫고, 냉장고에 토마토를 넣어."
    
    try:
        result = orchestrator.execute_natural_language_command(
            command=command,
            scene="FloorPlan1",
            max_agents=5
        )
        
        # 결과 저장
        output_file = "results/example_korean_sequential.json"
        os.makedirs("results", exist_ok=True)
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        
        print(f"\n✓ 결과 저장: {output_file}")
        print(f"✓ 사용된 agent 수: {result['num_agents']}")
        print(f"✓ 분석: {result['analysis']}")
        
        return result
        
    finally:
        orchestrator.shutdown_all_agents()


def example_korean_parallel():
    """예제 2: 병렬 작업 (여러 agent 필요)"""
    print("\n" + "="*80)
    print("예제 2: 병렬 작업 - 여러 agent가 동시에 다른 작업 수행")
    print("="*80)
    
    function_db = FunctionDatabase()
    llm_planner = LLMTaskPlanner(function_db)
    orchestrator = MultiAgentOrchestrator(function_db, llm_planner)
    
    command = """
    agent 1은 주방에서 사과를 찾아서 가져오고,
    agent 2는 거실에서 TV를 켜고,
    agent 3는 침실을 탐색해서 모든 서랍을 열어.
    """
    
    try:
        result = orchestrator.execute_natural_language_command(
            command=command,
            scene="FloorPlan1",
            max_agents=5
        )
        
        output_file = "results/example_korean_parallel.json"
        os.makedirs("results", exist_ok=True)
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        
        print(f"\n✓ 결과 저장: {output_file}")
        print(f"✓ 사용된 agent 수: {result['num_agents']}")
        print(f"✓ 분석: {result['analysis']}")
        
        return result
        
    finally:
        orchestrator.shutdown_all_agents()


def example_korean_complex():
    """예제 3: 복잡한 작업 - 요리 준비"""
    print("\n" + "="*80)
    print("예제 3: 복잡한 작업 - 요리 준비")
    print("="*80)
    
    function_db = FunctionDatabase()
    llm_planner = LLMTaskPlanner(function_db)
    orchestrator = MultiAgentOrchestrator(function_db, llm_planner)
    
    command = """
    주방에서 요리를 준비해줘.
    먼저 냉장고에서 계란, 토마토, 양상추를 꺼내고,
    토마토를 칼로 썰고,
    계란을 전자레인지에 넣어서 요리하고,
    모든 재료를 접시에 담아서 식탁에 놓아줘.
    """
    
    try:
        result = orchestrator.execute_natural_language_command(
            command=command,
            scene="FloorPlan1",
            max_agents=5
        )
        
        output_file = "results/example_korean_complex.json"
        os.makedirs("results", exist_ok=True)
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        
        print(f"\n✓ 결과 저장: {output_file}")
        print(f"✓ 사용된 agent 수: {result['num_agents']}")
        print(f"✓ 분석: {result['analysis']}")
        
        return result
        
    finally:
        orchestrator.shutdown_all_agents()


def example_korean_cleanup():
    """예제 4: 청소 작업"""
    print("\n" + "="*80)
    print("예제 4: 청소 작업")
    print("="*80)
    
    function_db = FunctionDatabase()
    llm_planner = LLMTaskPlanner(function_db)
    orchestrator = MultiAgentOrchestrator(function_db, llm_planner)
    
    command = """
    주방을 깨끗하게 정리해줘.
    모든 더러운 접시를 싱크대로 가져와서 씻고,
    카운터를 닦고,
    모든 캐비닛과 서랍을 닫고,
    쓰레기통을 비워줘.
    """
    
    try:
        result = orchestrator.execute_natural_language_command(
            command=command,
            scene="FloorPlan1",
            max_agents=5
        )
        
        output_file = "results/example_korean_cleanup.json"
        os.makedirs("results", exist_ok=True)
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        
        print(f"\n✓ 결과 저장: {output_file}")
        print(f"✓ 사용된 agent 수: {result['num_agents']}")
        print(f"✓ 분석: {result['analysis']}")
        
        return result
        
    finally:
        orchestrator.shutdown_all_agents()


def example_korean_search():
    """예제 5: 검색 작업 - 병렬"""
    print("\n" + "="*80)
    print("예제 5: 검색 작업 - 여러 agent가 다른 방 탐색")
    print("="*80)
    
    function_db = FunctionDatabase()
    llm_planner = LLMTaskPlanner(function_db)
    orchestrator = MultiAgentOrchestrator(function_db, llm_planner)
    
    command = """
    집 전체에서 열쇠를 찾아줘.
    여러 agent가 동시에 다른 방을 탐색해서 열쇠를 찾으면 보고해.
    주방, 거실, 침실, 욕실을 모두 확인해.
    """
    
    try:
        result = orchestrator.execute_natural_language_command(
            command=command,
            scene="FloorPlan1",
            max_agents=5
        )
        
        output_file = "results/example_korean_search.json"
        os.makedirs("results", exist_ok=True)
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        
        print(f"\n✓ 결과 저장: {output_file}")
        print(f"✓ 사용된 agent 수: {result['num_agents']}")
        print(f"✓ 분석: {result['analysis']}")
        
        return result
        
    finally:
        orchestrator.shutdown_all_agents()


def run_all_examples():
    """모든 예제 실행"""
    print("\n" + "="*80)
    print("한국어 자연어 명령어 예제 실행")
    print("="*80)
    
    examples = [
        ("순차적 작업", example_korean_sequential),
        ("병렬 작업", example_korean_parallel),
        ("복잡한 작업", example_korean_complex),
        ("청소 작업", example_korean_cleanup),
        ("검색 작업", example_korean_search),
    ]
    
    results = {}
    for name, example_func in examples:
        try:
            print(f"\n실행 중: {name}...")
            result = example_func()
            results[name] = {
                'status': 'success',
                'num_agents': result['num_agents'],
                'num_tasks': result['num_tasks']
            }
        except Exception as e:
            print(f"\n✗ {name} 실패: {e}")
            results[name] = {
                'status': 'failed',
                'error': str(e)
            }
    
    # 전체 결과 요약
    print("\n" + "="*80)
    print("전체 실행 결과 요약")
    print("="*80)
    for name, result in results.items():
        if result['status'] == 'success':
            print(f"✓ {name}: {result['num_agents']}개 agent, {result['num_tasks']}개 작업")
        else:
            print(f"✗ {name}: 실패 - {result['error']}")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        example_num = sys.argv[1]
        
        if example_num == "1":
            example_korean_sequential()
        elif example_num == "2":
            example_korean_parallel()
        elif example_num == "3":
            example_korean_complex()
        elif example_num == "4":
            example_korean_cleanup()
        elif example_num == "5":
            example_korean_search()
        elif example_num == "all":
            run_all_examples()
        else:
            print("사용법: python example_korean_commands.py [1-5|all]")
    else:
        # 기본: 첫 번째 예제 실행
        example_korean_sequential()
