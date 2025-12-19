"""간단한 멀티-에이전트 테스트 (시각화 없음)"""
from multi_agent_system import FunctionDatabase, LLMTaskPlanner, MultiAgentOrchestrator

print("\n" + "="*80)
print("🧪 간단한 멀티-에이전트 테스트")
print("="*80 + "\n")

# 시스템 초기화
function_db = FunctionDatabase()
llm_planner = LLMTaskPlanner(function_db, use_local=True)
orchestrator = MultiAgentOrchestrator(function_db, llm_planner)

# 간단한 명령어
command = "2개의 에이전트가 각각 앞으로 3걸음 이동해."

try:
    print(f"📝 명령어: {command}\n")
    
    result = orchestrator.execute_natural_language_command(
        command=command,
        scene="FloorPlan1",
        max_agents=2,
        enable_video=False  # 비디오 없이 빠른 테스트
    )
    
    print("\n✅ 실행 완료!")
    print(f"✅ 사용된 agent 수: {result['num_agents']}")
    if 'total_time' in result:
        print(f"✅ 실행 시간: {result['total_time']:.2f}초")
    
finally:
    orchestrator.shutdown_all_agents()
    print("\n✅ 테스트 종료")
