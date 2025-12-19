"""직접 TaskPlan으로 테스트 (LLM 없이)"""
from multi_agent_system import FunctionDatabase, MultiAgentOrchestrator, TaskPlan, ActionStep
from typing import Dict

print("\n" + "="*80)
print("🧪 TaskPlan 직접 테스트 (LLM 없이)")
print("="*80 + "\n")

# 시스템 초기화 (LLM 없이)
function_db = FunctionDatabase()
orchestrator = MultiAgentOrchestrator(function_db, llm_planner=None)

# TaskPlan 직접 생성
task_plans = [
    TaskPlan(
        task_id="task_1",
        description="Agent 1이 앞으로 이동",
        agent_id="agent_1",
        actions=[
            ActionStep(
                action="MoveAhead",
                parameters={"moveMagnitude": 0.25},
                reason="앞으로 이동"
            ),
            ActionStep(
                action="MoveAhead",
                parameters={"moveMagnitude": 0.25},
                reason="앞으로 이동"
            )
        ],
        dependencies=[],
        priority=1
    ),
    TaskPlan(
        task_id="task_2",
        description="Agent 2가 오른쪽으로 회전 후 이동",
        agent_id="agent_2",
        actions=[
            ActionStep(
                action="RotateRight",
                parameters={"degrees": 90},
                reason="오른쪽 회전"
            ),
            ActionStep(
                action="MoveAhead",
                parameters={"moveMagnitude": 0.25},
                reason="앞으로 이동"
            )
        ],
        dependencies=[],
        priority=1
    )
]

try:
    print("✅ TaskPlan 2개 생성 완료")
    print(f"  - Task 1: {task_plans[0].description}")
    print(f"  - Task 2: {task_plans[1].description}\n")
    
    # 에이전트 초기화
    result_dict: Dict = orchestrator.initialize_agents(
        scene="FloorPlan1",
        num_agents=2
    )
    print(f"✅ {len(result_dict['agents'])}개 Agent 초기화 완료\n")
    
    # Task 실행
    print("📹 Task 실행 중...")
    results = orchestrator.execute_tasks_parallel(task_plans)
    
    print("\n✅ 실행 완료!")
    for agent_id, result in results.items():
        status = "✅ 성공" if result["success"] else "❌ 실패"
        print(f"  - {agent_id}: {status}")
    
finally:
    orchestrator.shutdown_all_agents()
    print("\n✅ 테스트 종료")
