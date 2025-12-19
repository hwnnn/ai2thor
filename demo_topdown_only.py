#!/usr/bin/env python3
"""
Topdown Camera + Agent POVs 데모
- Controller 1개, agentCount=3
- Agent 0: 천장에 고정 (Topdown camera) - Unity 화면에 표시
- Agent 1: 토마토 자르기
- Agent 2: 불 켜기
- 영상: Topview + Agent 1/2 POV 저장
- 상호작용: 0.3m까지 이동 (좌우 우회 로직) → 상하좌우 회전하며 탐색 → 상호작용
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


def get_random_position(reachable_positions, exclude_positions=None, min_distance_from_exclude=2.0, 
                       other_agent_pos=None, min_distance_between_agents=1.5):
    """이동 가능한 위치 중 랜덤 선택"""
    valid_positions = []
    
    for pos in reachable_positions:
        valid = True
        
        # 목표 객체로부터 충분히 멀리
        if exclude_positions:
            for exclude_pos in exclude_positions:
                dist = calculate_distance(pos, exclude_pos)
                if dist < min_distance_from_exclude:
                    valid = False
                    break
        
        # 다른 agent와 충분히 떨어진 곳
        if valid and other_agent_pos:
            dist = calculate_distance(pos, other_agent_pos)
            if dist < min_distance_between_agents:
                valid = False
        
        if valid:
            valid_positions.append(pos)
    
    if not valid_positions:
        return random.choice(reachable_positions)
    
    return random.choice(valid_positions)


def try_move_sideways(controller, agent_id, capture_func=None):
    """좌우로 이동 가능한지 확인하고 우회"""
    # 왼쪽 시도
    left_event = controller.step(action='MoveLeft', agentId=agent_id, moveMagnitude=0.25, renderImage=False)
    if capture_func:
        capture_func()
    
    if left_event.metadata['lastActionSuccess']:
        print(f"[agent_{agent_id}] ← 왼쪽으로 우회 성공")
        return True
    
    # 오른쪽 시도
    right_event = controller.step(action='MoveRight', agentId=agent_id, moveMagnitude=0.25, renderImage=False)
    if capture_func:
        capture_func()
    
    if right_event.metadata['lastActionSuccess']:
        print(f"[agent_{agent_id}] → 오른쪽으로 우회 성공")
        return True
    
    return False


def navigate_to_distance(controller, agent_id, target_pos, target_distance=0.3, capture_func=None):
    """목표 위치에 특정 거리까지 접근"""
    print(f"[agent_{agent_id}] 목표 위치로 이동 중 ({target_distance}m 목표)...")
    
    max_attempts = 100
    consecutive_failures = 0
    
    for attempt in range(max_attempts):
        current_pos = controller.last_event.events[agent_id].metadata['agent']['position']
        distance = calculate_distance(current_pos, target_pos)
        
        if distance < target_distance:
            print(f"[agent_{agent_id}] ✓ 목표 거리 도달 ({distance:.2f}m)")
            return True
        
        # 목표 방향 계산
        dx = target_pos['x'] - current_pos['x']
        dz = target_pos['z'] - current_pos['z']
        target_angle = math.degrees(math.atan2(dx, dz))
        current_rotation = controller.last_event.events[agent_id].metadata['agent']['rotation']['y']
        angle_diff = (target_angle - current_rotation + 180) % 360 - 180
        
        # 회전
        if abs(angle_diff) > 15:
            direction = 'RotateRight' if angle_diff > 0 else 'RotateLeft'
            controller.step(action=direction, agentId=agent_id, degrees=min(30, abs(angle_diff)), renderImage=False)
            if capture_func:
                capture_func()
            continue
        
        # 이동
        move_magnitude = min(0.25, distance - target_distance + 0.1)
        event = controller.step(action='MoveAhead', agentId=agent_id, moveMagnitude=move_magnitude, renderImage=False)
        if capture_func:
            capture_func()
        
        if not event.metadata['lastActionSuccess']:
            consecutive_failures += 1
            if consecutive_failures >= 3:
                print(f"[agent_{agent_id}] 🚧 막힘 감지, 좌우 우회 시도...")
                
                # 좌우로 우회 시도
                if try_move_sideways(controller, agent_id, capture_func):
                    consecutive_failures = 0
                    continue
                
                # 좌우도 막혔으면 백스텝 + 회전
                print(f"[agent_{agent_id}] ⚠️ 좌우 모두 막힘, 백스텝 후 회전")
                controller.step(action='MoveBack', agentId=agent_id, moveMagnitude=0.3, renderImage=False)
                if capture_func:
                    capture_func()
                controller.step(action='RotateRight', agentId=agent_id, degrees=45, renderImage=False)
                if capture_func:
                    capture_func()
                consecutive_failures = 0
        else:
            consecutive_failures = 0
    
    final_pos = controller.last_event.events[agent_id].metadata['agent']['position']
    final_dist = calculate_distance(final_pos, target_pos)
    print(f"[agent_{agent_id}] ✓ 이동 완료 (거리: {final_dist:.2f}m)")
    return True


def search_and_interact(controller, agent_id, object_type, action_type, capture_func):
    """상하좌우 회전하며 객체 탐색 및 상호작용"""
    print(f"[agent_{agent_id}] {object_type} 탐색 중 (상하좌우 회전)...")
    
    # 상하 시야각 조정
    for horizon_angle in [0, 30, -30, 15, -15]:
        # 시야각 조정
        if horizon_angle < 0:
            controller.step(action='LookUp', agentId=agent_id, degrees=abs(horizon_angle), renderImage=False)
        elif horizon_angle < 0:
            controller.step(action='LookDown', agentId=agent_id, degrees=abs(horizon_angle), renderImage=False)
        if capture_func:
            capture_func()
        
        # 좌우 360도 회전
        for rotation_step in range(12):
            if rotation_step > 0:
                controller.step(action='RotateRight', agentId=agent_id, degrees=30, renderImage=False)
                if capture_func:
                    capture_func()
            
            # 객체 확인
            event = controller.last_event
            for obj in event.events[agent_id].metadata['objects']:
                if obj['objectType'] == object_type and obj['visible']:
                    print(f"[agent_{agent_id}] ✓ {object_type} 발견!")
                    
                    # 시야각 원복
                    if horizon_angle < 0:
                        controller.step(action='LookDown', agentId=agent_id, degrees=abs(horizon_angle), renderImage=False)
                    elif horizon_angle > 0:
                        controller.step(action='LookUp', agentId=agent_id, degrees=abs(horizon_angle), renderImage=False)
                    if capture_func:
                        capture_func()
                    
                    # 상호작용 시도
                    return try_interact(controller, agent_id, obj, action_type, capture_func)
        
        # 시야각 원복
        if horizon_angle < 0:
            controller.step(action='LookDown', agentId=agent_id, degrees=abs(horizon_angle), renderImage=False)
        elif horizon_angle > 0:
            controller.step(action='LookUp', agentId=agent_id, degrees=abs(horizon_angle), renderImage=False)
        if capture_func:
            capture_func()
    
    print(f"[agent_{agent_id}] ✗ {object_type}를 찾을 수 없습니다")
    return False


def try_interact(controller, agent_id, obj, action_type, capture_func):
    """객체와 상호작용 시도"""
    print(f"[agent_{agent_id}] {obj['objectType']}와 상호작용 시도...")
    
    max_attempts = 5
    for attempt in range(max_attempts):
        if action_type == 'pickup':
            event = controller.step(
                action='PickupObject',
                agentId=agent_id,
                objectId=obj['objectId'],
                forceAction=True,
                renderImage=False
            )
        elif action_type == 'toggle':
            event = controller.step(
                action='ToggleObjectOn',
                agentId=agent_id,
                objectId=obj['objectId'],
                forceAction=True,
                renderImage=False
            )
        elif action_type == 'slice':
            event = controller.step(
                action='SliceObject',
                agentId=agent_id,
                objectId=obj['objectId'],
                forceAction=True,
                renderImage=False
            )
        
        if capture_func:
            capture_func()
        
        if event.metadata['lastActionSuccess']:
            print(f"[agent_{agent_id}] ✓ 상호작용 성공!")
            return True
        else:
            error_msg = event.metadata.get('errorMessage', 'Unknown')
            print(f"[agent_{agent_id}] ⚠️ 실패 ({attempt+1}/{max_attempts}): {error_msg}")
    
    return False


def agent_task(controller, agent_id, target_object_type, action_type, capture_func):
    """에이전트 태스크 실행"""
    print(f"\n{'='*60}")
    print(f"[agent_{agent_id}] {target_object_type} 미션 시작")
    print(f"{'='*60}")
    
    # 1. 객체 위치 확인
    event = controller.last_event
    target_obj = None
    for obj in event.events[agent_id].metadata['objects']:
        if obj['objectType'] == target_object_type:
            target_obj = obj
            print(f"[agent_{agent_id}] ✓ {target_object_type} 위치 확인: ({obj['position']['x']:.2f}, {obj['position']['y']:.2f}, {obj['position']['z']:.2f})")
            break
    
    if not target_obj:
        print(f"[agent_{agent_id}] ✗ {target_object_type}를 찾을 수 없습니다")
        return False
    
    # 2. 0.3m까지 이동
    if not navigate_to_distance(controller, agent_id, target_obj['position'], target_distance=0.3, capture_func=capture_func):
        print(f"[agent_{agent_id}] ✗ 이동 실패")
        return False
    
    # 3. 상하좌우 회전하며 탐색 및 상호작용
    if search_and_interact(controller, agent_id, target_object_type, action_type, capture_func):
        return True
    
    return False


def main():
    print("=" * 60)
    print("Topdown Camera + Agent POVs 데모")
    print("=" * 60)
    
    # 출력 디렉토리
    output_dir = '/Users/jaehwan/Desktop/JaeHwan/workspace/ai2thor/output_videos'
    os.makedirs(output_dir, exist_ok=True)
    
    # 타임스탬프
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # 비디오 작성기 (topview만)
    fps = 6
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    
    video_writers = {
        'topview': cv2.VideoWriter(
            os.path.join(output_dir, f'topview_{timestamp}.mp4'),
            fourcc, fps, (1920, 1080)
        )
    }
    
    frame_count = 0
    
    def capture_frame():
        """프레임 캡처 (topview만)"""
        nonlocal frame_count
        
        # Agent 0의 프레임을 업데이트 (Done action으로 아무 동작도 하지 않음)
        event = controller.step(action='Done', agentId=0, renderImage=True)
        topdown_frame = event.events[0].frame
        
        # 해상도 조정
        topdown_bgr = cv2.cvtColor(topdown_frame, cv2.COLOR_RGB2BGR)
        topdown_resized = cv2.resize(topdown_bgr, (1920, 1080))
        
        # 저장
        video_writers['topview'].write(topdown_resized)
        frame_count += 1
    
    try:
        # Controller 초기화 (3 agents)
        print("\n🎮 Controller 초기화 중... (3 agents)")
        controller = Controller(
            scene="FloorPlan1",
            agentCount=3,
            width=1920,  # Agent 0 (topdown) 해상도
            height=1080,
            fieldOfView=90,
            visibilityDistance=10.0,
            makeAgentsVisible=False  # Agent 실룣엣을 숨김
        )
        print("✓ Controller 초기화 완료 (Unity 화면 = Agent 0 topdown view)")
        
        # 씬 정보 수집
        reachable_positions = controller.step(
            action='GetReachablePositions',
            agentId=1
        ).metadata['actionReturn']
        
        center_x = np.mean([p['x'] for p in reachable_positions])
        center_z = np.mean([p['z'] for p in reachable_positions])
        
        # Agent 0을 천장에 고정 (Topdown camera)
        print("\n📹 Agent 0을 Topdown Camera로 설정...")
        
        # 천장에서 아래를 내려다보도록 배치 (forceAction으로 공중 배치 강제)
        controller.step(
            action='TeleportFull',
            agentId=0,
            x=center_x,
            y=2.5,  # 천장 높이
            z=center_z,
            rotation={'x': 0, 'y': 0, 'z': 0},
            horizon=90,  # 90 = 아래를 내려다봄
            standing=True,
            forceAction=True  # 공중 배치 허용
        )
        
        print(f"✓ Agent 0 = Topdown Camera (목표 위치: {center_x:.2f}, 2.5, {center_z:.2f})")
        
        # 확인: Agent 0의 현재 위치와 회전
        agent_0_meta = controller.last_event.events[0].metadata['agent']
        print(f"  - 실제 Position: ({agent_0_meta['position']['x']:.2f}, {agent_0_meta['position']['y']:.2f}, {agent_0_meta['position']['z']:.2f})")
        print(f"  - Rotation: ({agent_0_meta['rotation']['x']:.1f}°, {agent_0_meta['rotation']['y']:.1f}°, {agent_0_meta['rotation']['z']:.1f}°)")
        print(f"  - Horizon: {agent_0_meta['cameraHorizon']:.1f}°")
        
        # Scene 정보
        print(f"\n{'='*60}")
        print("Scene 정보")
        print(f"{'='*60}")
        print(f"이동 가능한 위치: {len(reachable_positions)}개")
        print(f"Scene 중심: ({center_x:.2f}, {center_z:.2f})")
        
        # 목표 객체 위치
        event = controller.last_event
        all_objects = event.events[1].metadata['objects']
        target_objects = []
        for obj in all_objects:
            if obj['objectType'] in ['Tomato', 'LightSwitch']:
                target_objects.append(obj)
        
        exclude_positions = [obj['position'] for obj in target_objects]
        
        # Agent 1, 2 랜덤 위치 설정
        print("\n📍 Agent 1, 2 랜덤 위치 설정...")
        pos_1 = get_random_position(reachable_positions, exclude_positions)
        pos_2 = get_random_position(reachable_positions, exclude_positions, other_agent_pos=pos_1)
        
        controller.step(action='TeleportFull', agentId=1, **pos_1, rotation={'x': 0, 'y': 0, 'z': 0}, horizon=0, standing=True, renderImage=False)
        controller.step(action='TeleportFull', agentId=2, **pos_2, rotation={'x': 0, 'y': 0, 'z': 0}, horizon=0, standing=True, renderImage=False)
        
        print(f"[agent_1] 위치: ({pos_1['x']:.2f}, {pos_1['z']:.2f})")
        print(f"[agent_2] 위치: ({pos_2['x']:.2f}, {pos_2['z']:.2f})")
        print(f"📏 에이전트 간 거리: {calculate_distance(pos_1, pos_2):.2f}m")
        
        print("\n🎬 태스크 시작...")
        capture_frame()
        
        # Agent 1: 토마토 자르기
        success_1 = agent_task(controller, 1, 'Tomato', 'slice', capture_frame)
        
        # Agent 2: 불 켜기
        success_2 = agent_task(controller, 2, 'LightSwitch', 'toggle', capture_frame)
        
        # 결과
        print(f"\n{'='*60}")
        print("📊 작업 결과")
        print(f"{'='*60}")
        print(f"[agent_1] 토마토 자르기: {'✓ 성공' if success_1 else '✗ 실패'}")
        print(f"[agent_2] 불 켜기: {'✓ 성공' if success_2 else '✗ 실패'}")
        
        # 마무리 프레임
        print("\n📹 마무리 프레임 녹화...")
        for _ in range(5):
            capture_frame()
        
        print(f"\n✓ 총 {frame_count} 프레임 녹화 완료 (topview)")
        
    finally:
        print("\n🔄 시스템 종료 중...")
        for writer in video_writers.values():
            writer.release()
        if 'controller' in locals():
            controller.stop()
        print("✓ 모든 시스템 종료 완료")
    
    print("\n✅ 데모 완료!")


if __name__ == "__main__":
    main()
