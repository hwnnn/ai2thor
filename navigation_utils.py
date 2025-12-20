#!/usr/bin/env python3
"""
Navigation Utilities for AI2-THOR
- 공통 네비게이션 로직
- GetReachablePositions + MoveAhead로 걸어서 이동
- GetInteractablePoses로 정확한 상호작용
"""

import math


def calculate_distance(pos1, pos2):
    """두 위치 간 2D 거리 계산"""
    return math.sqrt((pos1['x'] - pos2['x'])**2 + (pos1['z'] - pos2['z'])**2)


def calculate_angle(from_pos, to_pos):
    """목표 방향의 각도 계산 (degrees)"""
    dx = to_pos['x'] - from_pos['x']
    dz = to_pos['z'] - from_pos['z']
    angle = math.degrees(math.atan2(dx, dz))
    return angle


def normalize_angle(angle):
    """각도를 -180~180 범위로 정규화"""
    while angle > 180:
        angle -= 360
    while angle < -180:
        angle += 360
    return angle


def navigate_to_object(controller, agent_id, obj, capture_callback):
    """
    객체 앞까지 걸어서 이동하고 상호작용 준비
    
    단계:
    1. 객체 위치 파악
    2. GetReachablePositions로 걸어갈 수 있는 모든 위치 확인
    3. GetInteractablePoses로 상호작용 가능한 위치 확인
    4. 두 위치의 교집합에서 가장 가까운 위치 선택 (장애물 너머가 아닌 실제 도달 가능한 위치)
    5. MoveAhead로 걸어서 해당 위치로 이동
    6. 객체 방향으로 정확히 회전
    7. 객체 반환
    
    Args:
        controller: AI2-THOR controller (multi-agent or single-agent)
        agent_id: Agent ID (multi-agent의 경우, single-agent는 None)
        obj: 객체 메타데이터
        capture_callback: 프레임 캡처 콜백 함수
    
    Returns:
        visible한 객체 또는 None
    """
    obj_id = obj['objectId']
    obj_pos = obj['position']
    
    print(f"  🎯 목표 객체: {obj_id}")
    print(f"     위치: ({obj_pos['x']:.2f}, {obj_pos['y']:.2f}, {obj_pos['z']:.2f})")
    
    # Multi-agent vs Single-agent 메타데이터 접근
    if agent_id is not None:
        # Multi-agent
        get_metadata = lambda: controller.last_event.events[agent_id].metadata
        step_kwargs = {'agentId': agent_id}
    else:
        # Single-agent
        get_metadata = lambda: controller.last_event.metadata
        step_kwargs = {}
    
    # 1단계: GetReachablePositions로 걸어갈 수 있는 모든 위치 확인
    reachable_event = controller.step(action='GetReachablePositions', **step_kwargs)
    if not reachable_event.metadata['lastActionSuccess']:
        print(f"  ❌ GetReachablePositions 실패")
        return None
    
    reachable_positions = reachable_event.metadata['actionReturn']
    print(f"  📍 도달 가능한 위치: {len(reachable_positions)}개")
    
    # 2단계: GetInteractablePoses로 상호작용 가능한 위치 확인
    interact_event = controller.step(action='GetInteractablePoses', objectId=obj_id, **step_kwargs)
    
    interactable_positions = []
    if interact_event.metadata['lastActionSuccess'] and interact_event.metadata.get('actionReturn'):
        interactable_positions = interact_event.metadata['actionReturn']
        print(f"  📍 상호작용 가능한 위치: {len(interactable_positions)}개")
    
    # 3단계: 도달 가능하면서 상호작용 가능한 위치 찾기
    # AI2-THOR 그리드 크기(0.25m)를 고려하여 교집합 확인
    valid_positions = []
    
    for interact_pose in interactable_positions:
        interact_pos = {'x': interact_pose['x'], 'y': interact_pose.get('y', 0), 'z': interact_pose['z']}
        
        # Reachable positions 중에서 가까운 위치가 있는지 확인 (0.25m 이내 - 그리드 크기)
        for reachable_pos in reachable_positions:
            dist = calculate_distance(interact_pos, reachable_pos)
            if dist < 0.26:  # 그리드 크기 + 약간의 여유
                # 이 위치가 객체와 얼마나 가까운지 계산
                dist_to_obj = calculate_distance(reachable_pos, obj_pos)
                valid_positions.append({
                    'position': reachable_pos,
                    'rotation': interact_pose.get('rotation', {'x': 0, 'y': 0, 'z': 0}),
                    'distance_to_obj': dist_to_obj
                })
                break
    
    # 유효한 위치가 없으면 상호작용 위치 자체를 사용 (가장 가까운 것)
    if not valid_positions:
        print(f"  ⚠️ 정확히 일치하는 도달 가능 위치 없음, 상호작용 위치 직접 사용")
        # 객체와 가장 가까운 상호작용 위치 선택
        closest_interact = min(interactable_positions, 
                              key=lambda p: calculate_distance({'x': p['x'], 'z': p['z']}, obj_pos))
        valid_positions.append({
            'position': {'x': closest_interact['x'], 'y': closest_interact.get('y', 0), 'z': closest_interact['z']},
            'rotation': closest_interact.get('rotation', {'x': 0, 'y': 0, 'z': 0}),
            'distance_to_obj': calculate_distance({'x': closest_interact['x'], 'z': closest_interact['z']}, obj_pos)
        })
    
    # 객체와 가장 가까운 유효 위치 선택 (현재 위치가 아닌 객체와의 거리 기준)
    target_info = min(valid_positions, key=lambda p: p['distance_to_obj'])
    target_pos = target_info['position']
    target_rotation = target_info['rotation']
    
    print(f"  📍 목표 위치: ({target_pos['x']:.2f}, {target_pos['z']:.2f}), 객체까지 {target_info['distance_to_obj']:.2f}m")
    
    # 4단계: 목표 위치로 완전히 이동 (반드시 도착할 때까지)
    print(f"  🚶 목표 위치로 이동 중...")
    max_steps = 150
    stuck_count = 0
    last_distance = float('inf')
    avoidance_direction = 'right'
    
    for step in range(max_steps):
        current_pos = get_metadata()['agent']['position']
        current_rot = get_metadata()['agent']['rotation']['y']
        
        dist = calculate_distance(current_pos, target_pos)
        
        # 목표 위치에 충분히 가까워졌는지 확인 (0.3m 이내)
        if dist <= 0.3:
            print(f"  ✓ 목표 위치 도착! (거리: {dist:.2f}m)")
            break
        
        # 진행 상황 체크
        if dist >= last_distance - 0.03:
            stuck_count += 1
            if stuck_count >= 5:
                print(f"  ⚠️ 진행 없음, 우회 시도")
                controller.step(action='MoveBack', moveMagnitude=0.3, **step_kwargs)
                capture_callback()
                
                rotate_action = 'RotateRight' if avoidance_direction == 'right' else 'RotateLeft'
                controller.step(action=rotate_action, degrees=45, **step_kwargs)
                capture_callback()
                
                avoidance_direction = 'left' if avoidance_direction == 'right' else 'right'
                stuck_count = 0
                continue
        else:
            stuck_count = 0
        
        last_distance = dist
        
        # 목표 방향 계산
        target_angle = calculate_angle(current_pos, target_pos)
        angle_diff = normalize_angle(target_angle - current_rot)
        
        # 방향 조정 (정확하게)
        if abs(angle_diff) > 10:
            direction = 'RotateRight' if angle_diff > 0 else 'RotateLeft'
            controller.step(action=direction, degrees=min(30, abs(angle_diff)), **step_kwargs)
            capture_callback()
            continue  # 회전 후 다음 루프
        
        # 전진
        move_magnitude = min(0.25, dist * 0.8)
        event = controller.step(action='MoveAhead', moveMagnitude=move_magnitude, **step_kwargs)
        capture_callback()
        
        if not event.metadata['lastActionSuccess']:
            # 충돌 시 스마트 회피
            print(f"  🚧 충돌 감지, {avoidance_direction} 회피")
            
            controller.step(action='MoveBack', moveMagnitude=0.2, **step_kwargs)
            capture_callback()
            
            rotate_action = 'RotateRight' if avoidance_direction == 'right' else 'RotateLeft'
            controller.step(action=rotate_action, degrees=45, **step_kwargs)
            capture_callback()
            
            attempt1 = controller.step(action='MoveAhead', moveMagnitude=0.25, **step_kwargs)
            capture_callback()
            
            if not attempt1.metadata['lastActionSuccess']:
                print(f"  🔄 반대 방향 시도")
                opposite_rotate = 'RotateLeft' if avoidance_direction == 'right' else 'RotateRight'
                controller.step(action=opposite_rotate, degrees=45, **step_kwargs)
                capture_callback()
                
                controller.step(action=opposite_rotate, degrees=45, **step_kwargs)
                capture_callback()
                
                attempt2 = controller.step(action='MoveAhead', moveMagnitude=0.25, **step_kwargs)
                capture_callback()
                
                if not attempt2.metadata['lastActionSuccess']:
                    rotate_action = 'RotateRight' if avoidance_direction == 'right' else 'RotateLeft'
                    controller.step(action=rotate_action, degrees=45, **step_kwargs)
                    capture_callback()
                else:
                    avoidance_direction = 'left' if avoidance_direction == 'right' else 'right'
    
    # 5단계: 목표 회전으로 객체를 정면으로
    if target_rotation:
        print(f"  🔄 객체 방향으로 회전")
        if isinstance(target_rotation, dict):
            target_y = target_rotation.get('y', 0)
        else:
            target_y = target_rotation
        
        current_rot = get_metadata()['agent']['rotation']['y']
        angle_diff = normalize_angle(target_y - current_rot)
        
        if abs(angle_diff) > 5:
            direction = 'RotateRight' if angle_diff > 0 else 'RotateLeft'
            controller.step(action=direction, degrees=abs(angle_diff), **step_kwargs)
            capture_callback()
    
    # 6단계: 한 발자국 후진 (더 나은 시야 확보)
    print(f"  ⬅️ 한 발자국 후진 (시야 확보)")
    controller.step(action='MoveBack', **step_kwargs)
    capture_callback()
    
    # 7단계: 상하 시야로 객체 찾기 (좌우 회전 절대 금지!)
    print(f"  👁️ 상하 시야로 객체 탐색")
    
    # 정면 확인
    visible_objs = [o for o in get_metadata()['objects']
                   if o['objectId'] == obj_id and o['visible']]
    if visible_objs:
        print(f"  ✅ 객체 발견! (정면)")
        return visible_objs[0]
    
    # 아래 확인
    print(f"  👇 아래 확인")
    controller.step(action='LookDown', **step_kwargs)
    capture_callback()
    
    visible_objs = [o for o in get_metadata()['objects']
                   if o['objectId'] == obj_id and o['visible']]
    if visible_objs:
        print(f"  ✅ 객체 발견! (아래)")
        return visible_objs[0]
    
    # 위 확인
    print(f"  👆 위 확인")
    controller.step(action='LookUp', **step_kwargs)
    controller.step(action='LookUp', **step_kwargs)
    capture_callback()
    
    visible_objs = [o for o in get_metadata()['objects']
                   if o['objectId'] == obj_id and o['visible']]
    if visible_objs:
        print(f"  ✅ 객체 발견! (위)")
        controller.step(action='LookDown', **step_kwargs)
        capture_callback()
        return visible_objs[0]
    
    # 고개 수평 복귀
    controller.step(action='LookDown', **step_kwargs)
    capture_callback()
    
    print(f"  ❌ 객체를 찾을 수 없음")
    return None
