"""
AddThirdPartyCamera 테스트
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from multi_agent_system import AI2THORAgent, AgentConfig
from ai2thor.controller import Controller
import cv2
import numpy as np

def test_third_party_camera():
    """AddThirdPartyCamera API 테스트"""
    
    print("\n=== AddThirdPartyCamera 테스트 시작 ===\n")
    
    # Agent Config 생성
    config = AgentConfig(
        agent_id="agent_1",
        scene="FloorPlan1"
    )
    
    # Agent 생성
    agent = AI2THORAgent(config)
    agent.initialize()
    
    controller = agent.controller
    
    try:
        # 씬 중앙 위치 찾기
        event = controller.step("GetReachablePositions")
        reachable_positions = event.metadata['actionReturn']
        
        if reachable_positions:
            center_x = float(np.mean([p['x'] for p in reachable_positions]))
            center_z = float(np.mean([p['z'] for p in reachable_positions]))
            
            print(f"씬 중앙: ({center_x:.2f}, {center_z:.2f})")
            
            # AddThirdPartyCamera로 탑뷰 카메라 추가
            event = controller.step(
                action='AddThirdPartyCamera',
                position=dict(x=center_x, y=3.0, z=center_z),
                rotation=dict(x=90, y=0, z=0),
                fieldOfView=90
            )
            
            print(f"✓ 카메라 추가 성공: {event.metadata['lastActionSuccess']}")
            
            # 프레임 확인
            event = controller.step("Pass")
            
            print(f"\nAgent frame: {event.frame.shape if event.frame is not None else 'None'}")
            
            if hasattr(event, 'third_party_camera_frames'):
                print(f"third_party_camera_frames 존재: {len(event.third_party_camera_frames)}개")
                if len(event.third_party_camera_frames) > 0:
                    tpc_frame = event.third_party_camera_frames[0]
                    print(f"Third party camera frame shape: {tpc_frame.shape}")
                    print(f"Third party camera frame dtype: {tpc_frame.dtype}")
                    
                    # 프레임 저장
                    cv2.imwrite('output_images/third_party_camera_test.jpg', cv2.cvtColor(tpc_frame, cv2.COLOR_RGB2BGR))
                    print(f"\n✓ 프레임 저장됨: output_images/third_party_camera_test.jpg")
                else:
                    print("✗ third_party_camera_frames가 비어있음")
            else:
                print("✗ third_party_camera_frames 속성이 없음")
        
    finally:
        print("\n시스템 종료 중...")
        controller.stop()
        print("✓ 테스트 완료\n")

if __name__ == "__main__":
    test_third_party_camera()
