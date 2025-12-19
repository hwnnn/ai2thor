"""
AI2THOR Multi-Agent System 사용 예제
다양한 시나리오에서 멀티-에이전트 시스템을 활용하는 방법을 보여줍니다.
"""

from multi_agent_system import (
    FunctionDatabase, 
    LLMTaskPlanner, 
    MultiAgentOrchestrator
)
import json
import time


def example_1_parallel_exploration():
    """예제 1: 병렬 탐색 - 여러 에이전트가 동시에 다른 방을 탐색"""
    
    print("\n" + "="*80)
    print("예제 1: 병렬 탐색")
    print("="*80)
    
    function_db = FunctionDatabase()
    llm_planner = LLMTaskPlanner(function_db)
    orchestrator = MultiAgentOrchestrator(function_db, llm_planner)
    
    command = """
    Create 3 exploration agents. 
    Agent 1 should explore the kitchen area by moving forward 3 times and rotating to look around.
    Agent 2 should explore the living room area by moving in a square pattern.
    Agent 3 should stay in place but rotate 360 degrees to survey the entire room.
    All agents should report what objects they can see.
    """
    
    try:
        result = orchestrator.execute_natural_language_command(
            command=command,
            scene="FloorPlan1",
            max_agents=3
        )
        
        # 결과 저장
        with open('results/example_1_exploration.json', 'w') as f:
            json.dump(result, f, indent=2)
        
        print("\n✓ Example 1 completed successfully!")
        return result
        
    finally:
        orchestrator.shutdown_all_agents()


def example_2_object_gathering():
    """예제 2: 객체 수집 - 에이전트들이 협력하여 객체 수집"""
    
    print("\n" + "="*80)
    print("예제 2: 객체 수집 작업")
    print("="*80)
    
    function_db = FunctionDatabase()
    llm_planner = LLMTaskPlanner(function_db)
    orchestrator = MultiAgentOrchestrator(function_db, llm_planner)
    
    command = """
    Create 2 agents to collect items from a kitchen.
    Agent 1 should find and pick up an apple, then place it on the dining table.
    Agent 2 should find and pick up a mug, fill it with water, and place it on the counter.
    Both agents should work simultaneously but independently.
    """
    
    try:
        result = orchestrator.execute_natural_language_command(
            command=command,
            scene="FloorPlan1",
            max_agents=2
        )
        
        with open('results/example_2_gathering.json', 'w') as f:
            json.dump(result, f, indent=2)
        
        print("\n✓ Example 2 completed successfully!")
        return result
        
    finally:
        orchestrator.shutdown_all_agents()


def example_3_sequential_tasks():
    """예제 3: 순차 작업 - 의존성이 있는 작업들을 순서대로 수행"""
    
    print("\n" + "="*80)
    print("예제 3: 순차적 의존성 작업")
    print("="*80)
    
    function_db = FunctionDatabase()
    llm_planner = LLMTaskPlanner(function_db)
    orchestrator = MultiAgentOrchestrator(function_db, llm_planner)
    
    command = """
    Create 2 agents for a cooking preparation task.
    Agent 1 should first open the refrigerator, then signal completion.
    After Agent 1 finishes, Agent 2 should move to the refrigerator and pick up an egg.
    Then Agent 1 should close the refrigerator.
    Finally, Agent 2 should take the egg to the microwave and place it inside.
    """
    
    try:
        result = orchestrator.execute_natural_language_command(
            command=command,
            scene="FloorPlan1",
            max_agents=2
        )
        
        with open('results/example_3_sequential.json', 'w') as f:
            json.dump(result, f, indent=2)
        
        print("\n✓ Example 3 completed successfully!")
        return result
        
    finally:
        orchestrator.shutdown_all_agents()


def example_4_environment_manipulation():
    """예제 4: 환경 조작 - 여러 에이전트가 환경을 변경"""
    
    print("\n" + "="*80)
    print("예제 4: 환경 조작")
    print("="*80)
    
    function_db = FunctionDatabase()
    llm_planner = LLMTaskPlanner(function_db)
    orchestrator = MultiAgentOrchestrator(function_db, llm_planner)
    
    command = """
    Create 3 agents to set up a room.
    Agent 1 should turn on all lights in the room by toggling light switches.
    Agent 2 should open all cabinets and drawers to check their contents.
    Agent 3 should move around and clean any dirty objects by using the clean action.
    All agents should work in parallel.
    """
    
    try:
        result = orchestrator.execute_natural_language_command(
            command=command,
            scene="FloorPlan1",
            max_agents=3
        )
        
        with open('results/example_4_manipulation.json', 'w') as f:
            json.dump(result, f, indent=2)
        
        print("\n✓ Example 4 completed successfully!")
        return result
        
    finally:
        orchestrator.shutdown_all_agents()


def example_5_search_and_report():
    """예제 5: 검색 및 보고 - 에이전트들이 특정 객체를 찾아 보고"""
    
    print("\n" + "="*80)
    print("예제 5: 검색 및 보고")
    print("="*80)
    
    function_db = FunctionDatabase()
    llm_planner = LLMTaskPlanner(function_db)
    orchestrator = MultiAgentOrchestrator(function_db, llm_planner)
    
    command = """
    Create 4 agents to search for specific items in different areas.
    Agent 1 should search the kitchen for any fruit (apple, tomato, etc.).
    Agent 2 should search for electronic devices (laptop, phone, remote).
    Agent 3 should search for books or papers.
    Agent 4 should search for cleaning supplies (soap, sponge, spray bottle).
    Each agent should explore their area thoroughly and report what they find.
    """
    
    try:
        result = orchestrator.execute_natural_language_command(
            command=command,
            scene="FloorPlan1",
            max_agents=4
        )
        
        with open('results/example_5_search.json', 'w') as f:
            json.dump(result, f, indent=2)
        
        print("\n✓ Example 5 completed successfully!")
        return result
        
    finally:
        orchestrator.shutdown_all_agents()


def example_6_complex_coordination():
    """예제 6: 복잡한 조정 - 여러 에이전트가 복잡한 작업을 조정"""
    
    print("\n" + "="*80)
    print("예제 6: 복잡한 에이전트 조정")
    print("="*80)
    
    function_db = FunctionDatabase()
    llm_planner = LLMTaskPlanner(function_db)
    orchestrator = MultiAgentOrchestrator(function_db, llm_planner)
    
    command = """
    Create 3 agents for a complex meal preparation scenario.
    
    Agent 1 (Ingredient Gatherer):
    - Open the fridge
    - Pick up bread, lettuce, and tomato
    - Close the fridge
    - Bring items to the counter
    
    Agent 2 (Prep Cook):
    - Get a knife from the drawer
    - Slice the tomato and bread
    - Place sliced items on a plate
    
    Agent 3 (Cleaner):
    - Clean the counter before work starts
    - Turn on the faucet
    - Clean any dirty dishes
    - Turn off the faucet when done
    
    Agents should coordinate: Agent 3 cleans first, then Agent 1 gathers, then Agent 2 preps.
    """
    
    try:
        result = orchestrator.execute_natural_language_command(
            command=command,
            scene="FloorPlan1",
            max_agents=3
        )
        
        with open('results/example_6_coordination.json', 'w') as f:
            json.dump(result, f, indent=2)
        
        print("\n✓ Example 6 completed successfully!")
        return result
        
    finally:
        orchestrator.shutdown_all_agents()


def run_all_examples():
    """모든 예제 실행"""
    
    import os
    os.makedirs('results', exist_ok=True)
    
    examples = [
        ("Parallel Exploration", example_1_parallel_exploration),
        ("Object Gathering", example_2_object_gathering),
        ("Sequential Tasks", example_3_sequential_tasks),
        ("Environment Manipulation", example_4_environment_manipulation),
        ("Search and Report", example_5_search_and_report),
        ("Complex Coordination", example_6_complex_coordination),
    ]
    
    results = {}
    
    print("\n" + "="*80)
    print("Running All Multi-Agent Examples")
    print("="*80)
    
    for name, example_func in examples:
        print(f"\n\nRunning: {name}")
        print("-"*80)
        
        try:
            result = example_func()
            results[name] = {
                'status': 'success',
                'summary': {
                    'num_agents': result.get('num_agents', 0),
                    'num_tasks': result.get('num_tasks', 0),
                    'total_actions': sum(
                        r.get('total_actions', 0) 
                        for r in result.get('task_results', [])
                    )
                }
            }
            
            # 각 예제 간 대기
            time.sleep(2)
            
        except Exception as e:
            print(f"\n✗ Example failed: {e}")
            results[name] = {
                'status': 'failed',
                'error': str(e)
            }
    
    # 전체 결과 요약
    print("\n\n" + "="*80)
    print("All Examples Summary")
    print("="*80)
    
    for name, result in results.items():
        status = result['status']
        if status == 'success':
            summary = result['summary']
            print(f"\n✓ {name}:")
            print(f"  - Agents: {summary['num_agents']}")
            print(f"  - Tasks: {summary['num_tasks']}")
            print(f"  - Actions: {summary['total_actions']}")
        else:
            print(f"\n✗ {name}: {result['error']}")
    
    # 전체 결과 저장
    with open('results/all_examples_summary.json', 'w') as f:
        json.dump(results, f, indent=2)
    
    print("\n" + "="*80)
    print("All examples completed! Check 'results/' directory for detailed outputs.")
    print("="*80 + "\n")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        example_num = sys.argv[1]
        examples_map = {
            '1': example_1_parallel_exploration,
            '2': example_2_object_gathering,
            '3': example_3_sequential_tasks,
            '4': example_4_environment_manipulation,
            '5': example_5_search_and_report,
            '6': example_6_complex_coordination,
        }
        
        if example_num in examples_map:
            examples_map[example_num]()
        elif example_num == 'all':
            run_all_examples()
        else:
            print(f"Invalid example number: {example_num}")
            print("Usage: python example_multi_agent_scenarios.py [1-6|all]")
    else:
        # 기본: 첫 번째 예제만 실행
        example_1_parallel_exploration()
