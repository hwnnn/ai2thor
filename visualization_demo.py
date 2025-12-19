"""
Multi-Agent Visualization Demo
멀티-에이전트 시각화 데모
"""

from multi_agent_system import FunctionDatabase, LLMTaskPlanner, MultiAgentOrchestrator


def demo_visualization_local():
    """로컬 LLM으로 시각화 데모"""
    print("\n" + "="*80)
    print("멀티-에이전트 시각화 데모 (로컬 LLM)")
    print("="*80 + "\n")
    
    # 시스템 초기화
    function_db = FunctionDatabase()
    llm_planner = LLMTaskPlanner(function_db, use_local=True)
    orchestrator = MultiAgentOrchestrator(function_db, llm_planner)
    
    # 시각화 활성화
    orchestrator.enable_visualization()
    
    # 명령어
    command = """
    3개의 에이전트를 생성해서 각각 다른 방향으로 탐색하고,
    agent 1은 전진하고, agent 2는 오른쪽으로, agent 3는 왼쪽으로 이동해.
    """
    
    try:
        result = orchestrator.execute_natural_language_command(
            command=command,
            scene="FloorPlan1",
            max_agents=3,
            enable_video=True,
            video_duration=20  # 20초 녹화
        )
        
        print("\n✅ 실행 완료!")
        print(f"✅ 사용된 agent 수: {result['num_agents']}")
        print(f"✅ 비디오 파일: output_videos/ 디렉토리 확인")
        print("\n생성된 비디오:")
        print("  - topview_*.mp4: 탑뷰 (모든 agent 위치)")
        print("  - agent_*_pov_*.mp4: 각 agent 1인칭 시점")
        print("  - combined_*.mp4: 통합 뷰 (탑뷰 + 모든 POV)")
        
    finally:
        orchestrator.shutdown_all_agents()


def demo_visualization_gpt4():
    """GPT-4로 시각화 데모"""
    print("\n" + "="*80)
    print("멀티-에이전트 시각화 데모 (GPT-4)")
    print("="*80 + "\n")
    
    # 시스템 초기화
    function_db = FunctionDatabase()
    llm_planner = LLMTaskPlanner(function_db, use_local=False)
    orchestrator = MultiAgentOrchestrator(function_db, llm_planner)
    
    # 시각화 활성화
    orchestrator.enable_visualization()
    
    # 명령어
    command = """
    scene 1에서 3개의 에이전트가 병렬로 작업을 수행해.
    agent 1은 주방을 탐색하고,
    agent 2는 거실을 탐색하고,
    agent 3는 침실을 탐색해.
    """
    
    try:
        result = orchestrator.execute_natural_language_command(
            command=command,
            scene="FloorPlan1",
            max_agents=3,
            enable_video=True,
            video_duration=30  # 30초 녹화
        )
        
        print("\n✅ 실행 완료!")
        print(f"✅ 사용된 agent 수: {result['num_agents']}")
        print(f"✅ 비디오 파일: output_videos/ 디렉토리 확인")
        
    finally:
        orchestrator.shutdown_all_agents()


def simple_demo():
    """간단한 데모 (시각화 없이)"""
    print("\n" + "="*80)
    print("간단한 멀티-에이전트 데모 (시각화 없음)")
    print("="*80 + "\n")
    
    function_db = FunctionDatabase()
    llm_planner = LLMTaskPlanner(function_db, use_local=True)
    orchestrator = MultiAgentOrchestrator(function_db, llm_planner)
    
    command = "2개의 에이전트가 각각 전진하고 회전해."
    
    try:
        result = orchestrator.execute_natural_language_command(
            command=command,
            scene="FloorPlan1",
            max_agents=2,
            enable_video=False  # 시각화 비활성화
        )
        
        print("\n✅ 실행 완료!")
        print(f"✅ 사용된 agent 수: {result['num_agents']}")
        
    finally:
        orchestrator.shutdown_all_agents()


if __name__ == "__main__":
    import sys
    
    print("\n멀티-에이전트 시각화 시스템")
    print("="*80)
    
    if len(sys.argv) > 1:
        demo_type = sys.argv[1]
        
        if demo_type == "local":
            demo_visualization_local()
        elif demo_type == "gpt4":
            demo_visualization_gpt4()
        elif demo_type == "simple":
            simple_demo()
        else:
            print("사용법:")
            print("  python visualization_demo.py local   # 로컬 LLM + 시각화")
            print("  python visualization_demo.py gpt4    # GPT-4 + 시각화")
            print("  python visualization_demo.py simple  # 시각화 없이 실행")
    else:
        print("\n사용 가능한 데모:")
        print("  python visualization_demo.py local   # 로컬 LLM + 시각화 (무료)")
        print("  python visualization_demo.py gpt4    # GPT-4 + 시각화 (유료)")
        print("  python visualization_demo.py simple  # 시각화 없이 실행")
        print("\n추천: python visualization_demo.py local")
