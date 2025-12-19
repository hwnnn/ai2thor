"""카메라 및 비디오 시스템 테스트"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from multi_agent_system import FunctionDatabase, LLMTaskPlanner, MultiAgentOrchestrator

print("\n" + "="*80)
print("🎥 카메라 및 비디오 시스템 테스트")
print("="*80 + "\n")

# 시스템 초기화
function_db = FunctionDatabase()
llm_planner = LLMTaskPlanner(function_db, use_local=True)
orchestrator = MultiAgentOrchestrator(function_db, llm_planner)

# 시각화 활성화
orchestrator.enable_visualization()

# 간단한 명령어 (카메라 테스트용)
command = "1개의 agent가 360도 회전해."

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
    print("\n📹 생성된 비디오:")
    print("  - topview_*.mp4 : 위에서 내려다본 탑뷰 (agent 위치 표시)")
    print("  - agent_1_pov_*.mp4 : Agent 1의 1인칭 시점")
    print("  - combined_*.mp4 : 탑뷰 + Agent POV 통합")
    
finally:
    orchestrator.shutdown_all_agents()
    print("\n✅ 테스트 종료")
