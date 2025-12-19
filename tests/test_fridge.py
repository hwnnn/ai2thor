"""
냉장고 문 열고 닫기 테스트
단일 agent가 냉장고 문을 열고 닫는 동작을 수행하며 3개의 비디오를 생성
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from multi_agent_system import MultiAgentOrchestrator, FunctionDatabase, LLMTaskPlanner
import time

def test_single_agent_fridge():
    """단일 agent로 냉장고 문 열고 닫기 테스트"""
    
    print("\n=== 냉장고 테스트 시작 ===\n")
    
    # 시스템 초기화
    function_db = FunctionDatabase()
    llm_planner = LLMTaskPlanner(function_db, use_local=True)
    orchestrator = MultiAgentOrchestrator(function_db, llm_planner)
    orchestrator.enable_visualization()
    
    try:
        # 냉장고 문 열기 명령
        command = "Open the fridge door"
        
        print(f"명령 실행 중: {command}")
        result = orchestrator.execute_natural_language_command(
            command,
            scene="FloorPlan1",
            enable_video=True,
            video_duration=8
        )
        
        print("\n=== 실행 결과 ===")
        print(f"✓ 성공: {result.get('success', False)}")
        print(f"✓ 메시지: {result.get('message', 'N/A')}")
        
        # 비디오 파일 확인
        video_dir = "output_videos"
        if os.path.exists(video_dir):
            video_files = [f for f in os.listdir(video_dir) if f.endswith('.mp4')]
            latest_videos = sorted(video_files, reverse=True)[:3]
            
            print("\n=== 생성된 비디오 ===")
            for video in latest_videos:
                video_path = os.path.join(video_dir, video)
                size = os.path.getsize(video_path)
                print(f"✓ {video} ({size/1024:.1f} KB)")
        
    finally:
        print("\n시스템 종료 중...")
        orchestrator.close_all_agents()
        print("✓ 테스트 완료\n")

if __name__ == "__main__":
    test_single_agent_fridge()
