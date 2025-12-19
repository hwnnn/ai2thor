from ai2thor.controller import Controller
import cv2
import numpy as np

controller = Controller(scene='FloorPlan1', width=800, height=600)

# 씬 중앙 찾기
event = controller.step('GetReachablePositions')
positions = event.metadata['actionReturn']
center_x = float(np.mean([p['x'] for p in positions]))
center_z = float(np.mean([p['z'] for p in positions]))

print(f'씬 중앙: ({center_x:.2f}, {center_z:.2f})')

# Agent의 초기 프레임 확인
print(f'Agent frame shape: {event.frame.shape}')
cv2.imwrite('output_images/test_agent_view.jpg', cv2.cvtColor(event.frame, cv2.COLOR_RGB2BGR))
print('✓ Agent view 저장')

# AddThirdPartyCamera 추가
event = controller.step(
    action='AddThirdPartyCamera',
    position=dict(x=center_x, y=3.0, z=center_z),
    rotation=dict(x=90, y=0, z=0),
    fieldOfView=90
)

print(f'AddThirdPartyCamera 성공: {event.metadata["lastActionSuccess"]}')

# Pass로 프레임 가져오기
event = controller.step('Pass')

print(f'third_party_camera_frames 존재: {hasattr(event, "third_party_camera_frames")}')
if hasattr(event, 'third_party_camera_frames'):
    print(f'third_party_camera_frames 개수: {len(event.third_party_camera_frames)}')
    if len(event.third_party_camera_frames) > 0:
        tpc = event.third_party_camera_frames[0]
        print(f'TopView frame shape: {tpc.shape}')
        print(f'TopView 픽셀 범위: min={tpc.min()}, max={tpc.max()}, mean={tpc.mean():.1f}')
        
        # 저장
        cv2.imwrite('output_images/test_topview_immediate.jpg', cv2.cvtColor(tpc, cv2.COLOR_RGB2BGR))
        print('✓ TopView 저장')
        
        # 몇 번 더 시도
        for i in range(3):
            event = controller.step('Pass')
            if hasattr(event, 'third_party_camera_frames') and len(event.third_party_camera_frames) > 0:
                tpc = event.third_party_camera_frames[0]
                print(f'프레임 {i+1}: mean={tpc.mean():.1f}')

controller.stop()
