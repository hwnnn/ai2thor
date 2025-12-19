"""간단한 1 Agent 비디오 테스트"""
from multi_agent_system import FunctionDatabase, LLMTaskPlanner, MultiAgentOrchestrator

print("\n" + "="*80)
print("🧪 1개 Agent 비디오 테스트 (10초)")
print("="*80 + "\n")

# 시스템 초기화
function_db = FunctionDatabase()
llm_planner = LLMTaskPlanner(function_db, use_local=True)
orchestrator = MultiAgentOrchestrator(function_db, llm_planner)

# 시각화 활성화
orchestrator.enable_visualization()

# 간단한 명령어
command = "agent 1이 오른쪽으로 회전해."

try:
    print(f"📝 명령어: {command}\n")
    
    result = orchestrator.execute_natural_language_command(
        command=command,
        scene="FloorPlan1",
        max_agents=1,
        enable_video=True,
        video_duration=10  # 10초 녹화
    )
    
    print("\n✅ 실행 완료!")
    print(f"✅ 비디오: output_videos/ 디렉토리 확인")
    
finally:
    orchestrator.shutdown_all_agents()
    print("\n✅ 테스트 종료")
