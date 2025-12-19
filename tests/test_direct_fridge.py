"""
직접 냉장고 문 열고 닫기 테스트 (LLM 없이)
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from multi_agent_system import AI2THORAgent, AgentConfig
from multi_agent_visualizer import MultiAgentVisualizer
import time

def test_direct_fridge():
    """LLM 없이 직접 냉장고 문 열고 닫기"""
    
    print("\n=== 직접 냉장고 테스트 시작 ===\n")
    
    # 시각화 시스템 초기화
    visualizer = MultiAgentVisualizer()
    
    # Agent Config 생성
    config = AgentConfig(
        agent_id="agent_1",
        scene="FloorPlan1"
    )
    
    # Agent 생성
    agent = AI2THORAgent(config)
    agent.initialize()
    
    agents = {"agent_1": agent}
    
    try:
        # 시각화 시작
        visualizer.initialize_top_view_camera("FloorPlan1", agent_count=1)
        visualizer.setup_video_writers(agents)
        
        print("냉장고 찾는 중...")
        # 냉장고 객체 찾기
        event = agent.controller.step("Pass")
        fridge_id = None
        for obj in event.metadata['objects']:
            if obj['objectType'] == 'Fridge':
                fridge_id = obj['objectId']
                print(f"✓ 냉장고 발견: {fridge_id}")
                print(f"  위치: ({obj['position']['x']:.2f}, {obj['position']['y']:.2f}, {obj['position']['z']:.2f})")
                print(f"  열림 상태: {obj['isOpen']}")
                break
        
        if not fridge_id:
            print("✗ 냉장고를 찾을 수 없습니다")
            return
        
        # 녹화 시작
        recording_duration = 8.0  # 8초
        start_time = time.time()
        frame_count = 0
        
        action_done = False
        
        while time.time() - start_time < recording_duration:
            # 3초 후 냉장고 문 열기
            if not action_done and time.time() - start_time > 3.0:
                print("\n냉장고 문 여는 중...")
                result = agent.controller.step(
                    action='OpenObject',
                    objectId=fridge_id,
                    forceAction=True
                )
                if result.metadata['lastActionSuccess']:
                    print("✓ 냉장고 문 열기 성공")
                else:
                    print(f"✗ 냉장고 문 열기 실패: {result.metadata['errorMessage']}")
                action_done = True
            
            # 프레임 캡처
            visualizer.capture_frame(agents, frame_count)
            frame_count += 1
            time.sleep(0.1)  # 10 FPS
        
        print(f"\n✓ {frame_count} 프레임 녹화 완료")
        
        # 최종 상태 확인
        event = agent.controller.step("Pass")
        for obj in event.metadata['objects']:
            if obj['objectId'] == fridge_id:
                print(f"\n최종 냉장고 상태:")
                print(f"  열림: {obj['isOpen']}")
                break
        
    finally:
        print("\n시스템 종료 중...")
        visualizer.close()
        agent.controller.stop()
        print("✓ 테스트 완료\n")
        
        # 비디오 파일 확인
        video_dir = "output_videos"
        if os.path.exists(video_dir):
            video_files = [f for f in os.listdir(video_dir) if f.endswith('.mp4')]
            latest_videos = sorted(video_files, reverse=True)[:2]
            
            print("=== 생성된 비디오 ===")
            for video in latest_videos:
                video_path = os.path.join(video_dir, video)
                size = os.path.getsize(video_path)
                print(f"✓ {video} ({size/1024:.1f} KB)")

if __name__ == "__main__":
    test_direct_fridge()
