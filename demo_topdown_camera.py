#!/usr/bin/env python3
"""
Topdown Camera 데모 (Third Party Camera 사용)
- Controller 1개, agentCount=1 (단일 에이전트)
- AddThirdPartyCamera로 천장에서 아래를 내려다보는 카메라 설치
- 에이전트가 순차적으로: 토마토 자르기 → 불 켜기
- 영상: Topview + Agent POV 저장

Note: ThirdPartyCamera는 multi-agent 모드(agentCount>1)에서 작동하지 않아
      단일 에이전트로 구현합니다.
"""

import os
import cv2
import numpy as np
import random
import math
from datetime import datetime
from ai2thor.controller import Controller


def calculate_distance(pos1, pos2):
    """두 위치 간 거리 계산"""
    return math.sqrt((pos1['x'] - pos2['x'])**2 + (pos1['z'] - pos2['z'])**2)


def get_random_position(reachable_positions, exclude_positions=None, min_distance_from_exclude=2.0):
    """이동 가능한 위치 중 랜덤 선택"""
    valid_positions = []
    
    for pos in reachable_positions:
        valid = True
        
        if exclude_positions:
            for exclude_pos in exclude_positions:
                dist = calculate_distance(pos, exclude_pos)
                if dist < min_distance_from_exclude:
                    valid = False
                    break
        
        if valid:
            valid_positions.append(pos)
    
    if not valid_positions:
        return random.choice(reachable_positions)
    
    return random.choice(valid_positions)


def try_move_sideways(controller):
    """좌우로 이동 가능한지 확인하고 우회"""
    left_event = controller.step(action='MoveLeft', moveMagnitude=0.25)
    if left_event.metadata['lastActionSuccess']:
        print("  ← 왼쪽으로 우회 성공")
        return True
    
    right_event = controller.step(action='MoveRight', moveMagnitude=0.25)
    if right_event.metadata['lastActionSuccess']:
        print("  → 오른쪽으로 우회 성공")
        return True
    
    return False


def main():
    print("="*60)
    print("Topdown Camera 데모 (Third Party Camera)")
    print("- 단일 에이전트가 순차적으로 미션 수행")
    print("- ThirdPartyCamera로 topdown view 녹화")
    print("="*60)
    
    # 출력 디렉토리
    output_dir = 'output_videos'
    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # 비디오 작성기
    fps = 10
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    
    video_writers = {
        'topview': cv2.VideoWriter(
            os.path.join(output_dir, f'topview_{timestamp}.mp4'),
            fourcc, fps, (800, 800)
        ),
        'agent_pov': cv2.VideoWriter(
            os.path.join(output_dir, f'agent_pov_{timestamp}.mp4'),
            fourcc, fps, (800, 600)
        )
    }
    
    frame_count = 0
    topdown_frame_count = 0
    
    controller = None
    
    def capture_frame():
        """프레임 캡처 - event.third_party_camera_frames 사용"""
        nonlocal frame_count, topdown_frame_count
        
        event = controller.last_event
        
        # Third party camera 프레임 (Topdown)
        if event.third_party_camera_frames and len(event.third_party_camera_frames) > 0:
            topdown_frame = event.third_party_camera_frames[0]
            if topdown_frame is not None and topdown_frame.size > 0:
                topdown_bgr = cv2.cvtColor(topdown_frame, cv2.COLOR_RGB2BGR)
                topdown_resized = cv2.resize(topdown_bgr, (800, 800))
                video_writers['topview'].write(topdown_resized)
                topdown_frame_count += 1
        
        # Agent POV
        agent_frame = event.frame
        if agent_frame is not None and agent_frame.size > 0:
            agent_bgr = cv2.cvtColor(agent_frame, cv2.COLOR_RGB2BGR)
            agent_resized = cv2.resize(agent_bgr, (800, 600))
            video_writers['agent_pov'].write(agent_resized)
        
        frame_count += 1
    
    try:
        # Controller 초기화 (단일 에이전트)
        print("\n🎮 Controller 초기화 중... (단일 에이전트)")
        controller = Controller(
            scene="FloorPlan1",
            agentCount=1,
            width=800,
            height=600,
            fieldOfView=90,
            visibilityDistance=10.0
        )
        print("✓ Controller 초기화 완료")
        
        # Scene 정보
        reachable_positions = controller.step(action='GetReachablePositions').metadata['actionReturn']
        center_x = sum(p['x'] for p in reachable_positions) / len(reachable_positions)
        center_z = sum(p['z'] for p in reachable_positions) / len(reachable_positions)
        
        print(f"\n{'='*60}")
        print("Scene 정보")
        print(f"{'='*60}")
        print(f"이동 가능한 위치: {len(reachable_positions)}개")
        print(f"Scene 중심: ({center_x:.2f}, {center_z:.2f})")
        
        # Third Party Camera 추가 (Topdown view) - 문서 예제대로
        print("\n📹 Topdown 카메라 설치 중 (AddThirdPartyCamera)...")
        event = controller.step(
            action="AddThirdPartyCamera",
            position=dict(x=center_x, y=2.5, z=center_z),
            rotation=dict(x=90, y=0, z=0),
            fieldOfView=90
        )
        
        if event.metadata['lastActionSuccess']:
            print(f"✓ Topdown 카메라 설치 완료")
            print(f"  - 위치: ({center_x:.2f}, 2.5, {center_z:.2f})")
            print(f"  - 회전: (90°, 0°, 0°) - 아래를 바라봄")
            print(f"  - FOV: 90°")
            
            # 초기 프레임 확인
            if event.third_party_camera_frames and len(event.third_party_camera_frames) > 0:
                print(f"  - ✓ third_party_camera_frames: {len(event.third_party_camera_frames)}개")
                print(f"  - Frame shape: {event.third_party_camera_frames[0].shape}")
            else:
                print(f"  - ⚠️ third_party_camera_frames: 비어있음")
        else:
            print(f"⚠️ Topdown 카메라 설치 실패: {event.metadata.get('errorMessage', 'Unknown')}")
        
        # 목표 객체 찾기
        event = controller.last_event
        all_objects = event.metadata['objects']
        
        tomato = None
        lightswitch = None
        for obj in all_objects:
            if obj['objectType'] == 'Tomato' and tomato is None:
                tomato = obj
            if obj['objectType'] == 'LightSwitch' and lightswitch is None:
                lightswitch = obj
        
        print(f"\n📍 목표 객체 확인:")
        if tomato:
            print(f"  - Tomato: ({tomato['position']['x']:.2f}, {tomato['position']['y']:.2f}, {tomato['position']['z']:.2f})")
        if lightswitch:
            print(f"  - LightSwitch: ({lightswitch['position']['x']:.2f}, {lightswitch['position']['y']:.2f}, {lightswitch['position']['z']:.2f})")
        
        # 에이전트 랜덤 시작 위치
        exclude_positions = []
        if tomato:
            exclude_positions.append(tomato['position'])
        if lightswitch:
            exclude_positions.append(lightswitch['position'])
        
        start_pos = get_random_position(reachable_positions, exclude_positions)
        controller.step(
            action='TeleportFull',
            **start_pos,
            rotation={'x': 0, 'y': 0, 'z': 0},
            horizon=0,
            standing=True
        )
        print(f"\n📍 에이전트 시작 위치: ({start_pos['x']:.2f}, {start_pos['z']:.2f})")
        
        print("\n🎬 태스크 시작...")
        capture_frame()
        
        # ===== 미션 1: 토마토 자르기 =====
        success_tomato = False
        if tomato:
            print(f"\n{'='*60}")
            print("🍅 미션 1: 토마토 자르기")
            print(f"{'='*60}")
            
            # 토마토로 이동
            print("토마토 위치로 이동 중...")
            max_attempts = 100
            consecutive_failures = 0
            
            for attempt in range(max_attempts):
                current_pos = controller.last_event.metadata['agent']['position']
                distance = calculate_distance(current_pos, tomato['position'])
                
                if distance < 1.0:
                    print(f"✓ 목표 거리 도달 ({distance:.2f}m)")
                    break
                
                dx = tomato['position']['x'] - current_pos['x']
                dz = tomato['position']['z'] - current_pos['z']
                target_angle = math.degrees(math.atan2(dx, dz))
                current_rotation = controller.last_event.metadata['agent']['rotation']['y']
                angle_diff = (target_angle - current_rotation + 180) % 360 - 180
                
                if abs(angle_diff) > 15:
                    direction = 'RotateRight' if angle_diff > 0 else 'RotateLeft'
                    controller.step(action=direction, degrees=min(30, abs(angle_diff)))
                    capture_frame()
                    continue
                
                move_magnitude = min(0.25, distance - 0.5)
                event = controller.step(action='MoveAhead', moveMagnitude=move_magnitude)
                capture_frame()
                
                if not event.metadata['lastActionSuccess']:
                    consecutive_failures += 1
                    if consecutive_failures >= 3:
                        print("  🚧 막힘 감지, 우회 시도...")
                        if try_move_sideways(controller):
                            capture_frame()
                            consecutive_failures = 0
                            continue
                        
                        controller.step(action='MoveBack', moveMagnitude=0.3)
                        capture_frame()
                        controller.step(action='RotateRight', degrees=45)
                        capture_frame()
                        consecutive_failures = 0
                else:
                    consecutive_failures = 0
            
            # 토마토 찾아서 자르기
            print("토마토 탐색 중...")
            for horizon_angle in [0, 30, -30, 15, -15, 45, -45]:
                if success_tomato:
                    break
                    
                if horizon_angle > 0:
                    controller.step(action='LookUp', degrees=abs(horizon_angle))
                elif horizon_angle < 0:
                    controller.step(action='LookDown', degrees=abs(horizon_angle))
                capture_frame()
                
                for rotation_step in range(12):
                    if rotation_step > 0:
                        controller.step(action='RotateRight', degrees=30)
                        capture_frame()
                    
                    event = controller.last_event
                    for obj in event.metadata['objects']:
                        if obj['objectType'] == 'Tomato' and obj['visible']:
                            print(f"✓ 토마토 발견!")
                            
                            # 시야각 원복
                            if horizon_angle != 0:
                                if horizon_angle > 0:
                                    controller.step(action='LookDown', degrees=abs(horizon_angle))
                                else:
                                    controller.step(action='LookUp', degrees=abs(horizon_angle))
                                capture_frame()
                            
                            # 자르기
                            for att in range(5):
                                slice_event = controller.step(
                                    action='SliceObject',
                                    objectId=obj['objectId'],
                                    forceAction=True
                                )
                                capture_frame()
                                
                                if slice_event.metadata['lastActionSuccess']:
                                    print(f"✓ 토마토 자르기 성공!")
                                    success_tomato = True
                                    break
                                else:
                                    error_msg = slice_event.metadata.get('errorMessage', 'Unknown')
                                    print(f"  ⚠️ 시도 {att+1}/5: {error_msg}")
                            break
                    if success_tomato:
                        break
                
                # 시야각 원복
                if not success_tomato and horizon_angle != 0:
                    if horizon_angle > 0:
                        controller.step(action='LookDown', degrees=abs(horizon_angle))
                    else:
                        controller.step(action='LookUp', degrees=abs(horizon_angle))
                    capture_frame()
        
        # ===== 미션 2: 불 켜기 =====
        success_light = False
        if lightswitch:
            print(f"\n{'='*60}")
            print("💡 미션 2: 불 켜기")
            print(f"{'='*60}")
            
            # 불스위치로 이동
            print("불스위치 위치로 이동 중...")
            max_attempts = 100
            consecutive_failures = 0
            
            for attempt in range(max_attempts):
                current_pos = controller.last_event.metadata['agent']['position']
                distance = calculate_distance(current_pos, lightswitch['position'])
                
                if distance < 1.5:
                    print(f"✓ 목표 거리 도달 ({distance:.2f}m)")
                    break
                
                dx = lightswitch['position']['x'] - current_pos['x']
                dz = lightswitch['position']['z'] - current_pos['z']
                target_angle = math.degrees(math.atan2(dx, dz))
                current_rotation = controller.last_event.metadata['agent']['rotation']['y']
                angle_diff = (target_angle - current_rotation + 180) % 360 - 180
                
                if abs(angle_diff) > 15:
                    direction = 'RotateRight' if angle_diff > 0 else 'RotateLeft'
                    controller.step(action=direction, degrees=min(30, abs(angle_diff)))
                    capture_frame()
                    continue
                
                move_magnitude = min(0.25, distance - 1.0)
                event = controller.step(action='MoveAhead', moveMagnitude=move_magnitude)
                capture_frame()
                
                if not event.metadata['lastActionSuccess']:
                    consecutive_failures += 1
                    if consecutive_failures >= 3:
                        print("  🚧 막힘 감지, 우회 시도...")
                        if try_move_sideways(controller):
                            capture_frame()
                            consecutive_failures = 0
                            continue
                        
                        controller.step(action='MoveBack', moveMagnitude=0.3)
                        capture_frame()
                        controller.step(action='RotateRight', degrees=45)
                        capture_frame()
                        consecutive_failures = 0
                else:
                    consecutive_failures = 0
            
            # 불스위치 찾아서 켜기
            print("불스위치 탐색 중...")
            for horizon_angle in [0, 30, -30, 15, -15, 45, -45]:
                if success_light:
                    break
                    
                if horizon_angle > 0:
                    controller.step(action='LookUp', degrees=abs(horizon_angle))
                elif horizon_angle < 0:
                    controller.step(action='LookDown', degrees=abs(horizon_angle))
                capture_frame()
                
                for rotation_step in range(12):
                    if rotation_step > 0:
                        controller.step(action='RotateRight', degrees=30)
                        capture_frame()
                    
                    event = controller.last_event
                    for obj in event.metadata['objects']:
                        if obj['objectType'] == 'LightSwitch' and obj['visible']:
                            print(f"✓ 불스위치 발견!")
                            
                            # 시야각 원복
                            if horizon_angle != 0:
                                if horizon_angle > 0:
                                    controller.step(action='LookDown', degrees=abs(horizon_angle))
                                else:
                                    controller.step(action='LookUp', degrees=abs(horizon_angle))
                                capture_frame()
                            
                            # 켜기
                            for att in range(5):
                                toggle_event = controller.step(
                                    action='ToggleObjectOn',
                                    objectId=obj['objectId'],
                                    forceAction=True
                                )
                                capture_frame()
                                
                                if toggle_event.metadata['lastActionSuccess']:
                                    print(f"✓ 불 켜기 성공!")
                                    success_light = True
                                    break
                                else:
                                    error_msg = toggle_event.metadata.get('errorMessage', 'Unknown')
                                    # 이미 켜져 있으면 성공으로 처리
                                    if 'already' in error_msg.lower() or 'on' in error_msg.lower():
                                        print(f"  (불이 이미 켜져 있음)")
                                        success_light = True
                                        break
                                    print(f"  ⚠️ 시도 {att+1}/5: {error_msg}")
                            break
                    if success_light:
                        break
                
                # 시야각 원복
                if not success_light and horizon_angle != 0:
                    if horizon_angle > 0:
                        controller.step(action='LookDown', degrees=abs(horizon_angle))
                    else:
                        controller.step(action='LookUp', degrees=abs(horizon_angle))
                    capture_frame()
        
        # 결과
        print(f"\n{'='*60}")
        print("📊 작업 결과")
        print(f"{'='*60}")
        print(f"🍅 토마토 자르기: {'✓ 성공' if success_tomato else '✗ 실패'}")
        print(f"💡 불 켜기: {'✓ 성공' if success_light else '✗ 실패'}")
        
        # 마무리 프레임
        print("\n📹 마무리 프레임 녹화...")
        for _ in range(10):
            controller.step(action='RotateRight', degrees=30)
            capture_frame()
        
        print(f"\n✓ 녹화 완료")
        print(f"  - 총 프레임: {frame_count}")
        print(f"  - Topdown 프레임: {topdown_frame_count}")
        print(f"\n📁 저장된 파일:")
        print(f"  - Topview: topview_{timestamp}.mp4")
        print(f"  - Agent POV: agent_pov_{timestamp}.mp4")
        
    finally:
        print("\n🔄 시스템 종료 중...")
        for writer in video_writers.values():
            writer.release()
        
        if controller is not None:
            controller.stop()
        print("✓ 모든 시스템 종료 완료")
    
    print("\n✅ 데모 완료!")


if __name__ == "__main__":
    main()
