"""개선된 시스템 통합 테스트"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from multi_agent_system import FunctionDatabase, LLMTaskPlanner, MultiAgentOrchestrator

print("\n" + "="*80)
print("🧪 개선된 멀티-에이전트 시스템 테스트")
print("="*80 + "\n")

# 시스템 초기화 (llama3.2:3b 사용)
function_db = FunctionDatabase()
llm_planner = LLMTaskPlanner(function_db, use_local=True)
orchestrator = MultiAgentOrchestrator(function_db, llm_planner)

# 시각화 활성화
orchestrator.enable_visualization()

# 더 복잡한 상호작용 명령어
command = """
2개의 agent를 생성해.
agent 1은 주방을 탐색하고 전등을 켜.
agent 2는 오른쪽으로 회전하고 앞으로 2걸음 이동해.
"""

try:
    print(f"📝 명령어: {command}\n")
    
    result = orchestrator.execute_natural_language_command(
        command=command,
        scene="FloorPlan1",
        max_agents=2,
        enable_video=True,
        video_duration=15  # 15초 녹화
    )
    
    print("\n✅ 실행 완료!")
    print(f"✅ Agent 수: {result['num_agents']}")
    print(f"✅ 작업 수: {result['num_tasks']}")
    print(f"✅ 성공한 액션: {sum(r.get('successful_actions', 0) for r in result['task_results'])}")
    print(f"✅ 비디오: output_videos/ 디렉토리 확인")
    
finally:
    orchestrator.shutdown_all_agents()
    print("\n✅ 테스트 종료")
