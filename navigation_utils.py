#!/usr/bin/env python3
"""
Navigation Utilities for AI2-THOR
- 목표: 절대 중간에 멈추지 않고 객체까지 이동
- 메커니즘: 이동 → 도착 → 후진 → 위아래 탐색
"""

import math


def calculate_distance(pos1, pos2):
    """두 위치 간 2D 거리"""
    return math.sqrt((pos1['x'] - pos2['x'])**2 + (pos1['z'] - pos2['z'])**2)


def calculate_angle(from_pos, to_pos):
    """목표 방향의 각도 (degrees)"""
    dx = to_pos['x'] - from_pos['x']
    dz = to_pos['z'] - from_pos['z']
    return math.degrees(math.atan2(dx, dz))


def normalize_angle(angle):
    """각도를 -180~180 범위로 정규화"""
    while angle > 180:
        angle -= 360
    while angle < -180:
        angle += 360
    return angle


def navigate_to_object(controller, agent_id, object_type, capture_callback):
    """
    객체까지 이동하여 상호작용 준비
    
    절대 멈추지 않는 원칙:
    1. 목표 도달까지 계속 시도 (200 스텝)
    2. 충돌 시 우회하되, 목표를 포기하지 않음
    3. 50 스텝 안에 도착하지 못하면 다른 목표 위치 시도
    
    Args:
        controller: AI2-THOR controller
        agent_id: Agent ID (multi-agent) or None (single-agent)
        object_type: 객체 타입 (예: "Tomato")
        capture_callback: 프레임 캡처 콜백
    
    Returns:
        bool: 성공 여부
    """
    print(f"\n🎯 객체 네비게이션: {object_type}")
    
    # Multi-agent vs Single-agent
    if agent_id is not None:
        get_metadata = lambda: controller.last_event.events[agent_id].metadata
        step_kwargs = {'agentId': agent_id}
    else:
        get_metadata = lambda: controller.last_event.metadata
        step_kwargs = {}
    
    # 1. 객체 찾기
    all_objects = get_metadata()['objects']
    target_objects = [obj for obj in all_objects if obj['objectType'] == object_type]
    
    if not target_objects:
        print(f"  ❌ {object_type} 없음")
        return False
    
    current_pos = get_metadata()['agent']['position']
    target_obj = min(target_objects, key=lambda obj: calculate_distance(current_pos, obj['position']))
    obj_id = target_obj['objectId']
    obj_pos = target_obj['position']
    print(f"  📍 목표: {obj_id}")
    
    # 2. 도달 가능한 위치들
    reach_event = controller.step(action='GetReachablePositions', **step_kwargs)
    if not reach_event.metadata['lastActionSuccess']:
        print(f"  ❌ GetReachablePositions 실패")
        return False
    
    reachable_positions = reach_event.metadata['actionReturn']
    
    # 3. 상호작용 가능한 위치들
    interact_event = controller.step(action='GetInteractablePoses', objectId=obj_id, **step_kwargs)
    if not interact_event.metadata['lastActionSuccess'] or not interact_event.metadata.get('actionReturn'):
        print(f"  ❌ GetInteractablePoses 실패")
        return False
    
    interactable_positions = interact_event.metadata['actionReturn']
    
    # 4. 유효한 목표 위치들 (도달 가능 ∩ 상호작용 가능)
    targets = []
    for interact_pose in interactable_positions:
        for reach_pos in reachable_positions:
            if calculate_distance(interact_pose, reach_pos) < 0.26:
                dist_from_agent = calculate_distance(current_pos, reach_pos)
                dist_from_obj = calculate_distance(obj_pos, reach_pos)  # 객체와의 거리
                if dist_from_agent > 1.0:  # 1.0m 이상 떨어진 목표만 (실제로 이동하도록)
                    targets.append({'pos': reach_pos, 'dist': dist_from_agent, 'obj_dist': dist_from_obj})
                break
    
    if not targets:
        # 모든 목표가 1.0m 이내 - 그래도 가장 가까운 목표 선택
        print(f"  ⚠️ 가까운 위치에서 시작, 근처 목표 선택")
        for interact_pose in interactable_positions:
            for reach_pos in reachable_positions:
                if calculate_distance(interact_pose, reach_pos) < 0.26:
                    dist_from_obj = calculate_distance(obj_pos, reach_pos)
                    targets.append({'pos': reach_pos, 'dist': calculate_distance(current_pos, reach_pos), 'obj_dist': dist_from_obj})
                    break
        
        if not targets:
            print(f"  ❌ 목표 위치 없음")
            return False
    
    # 에이전트에서 접근 가능한 순서로 정렬 (도달하기 쉬운 위치 우선)
    targets.sort(key=lambda t: t['dist'])
    
    # 중복 제거 (같은 위치는 한 번만)
    unique_targets = []
    seen_positions = set()
    for target in targets:
        pos_key = (round(target['pos']['x'], 2), round(target['pos']['z'], 2))
        if pos_key not in seen_positions:
            unique_targets.append(target)
            seen_positions.add(pos_key)
    
    targets = unique_targets
    
    if not targets:
        print(f"  ❌ 유효한 목표 없음")
        return False
    
    # 최대 3개 목표를 시도
    success = False
    for i, target_info in enumerate(targets[:3]):
        target_pos = target_info['pos']
        print(f"  📍 시도 {i+1}/{min(len(targets), 3)}: ({target_pos['x']:.2f}, {target_pos['z']:.2f})")
        
        # 해당 목표로 이동 시도 (80 스텝 제한 - 더 긴 경로 허용)
        if try_reach_position(controller, agent_id, target_pos, capture_callback, max_steps=80):
            success = True
            break
        else:
            print(f"  ⚠️ 시도 {i+1} 실패, 다음 목표 시도")
    
    if not success:
        print(f"  ❌ 모든 목표 위치 도달 실패")
        return False
    
    # 5. 객체를 향해 회전
    current_pos = get_metadata()['agent']['position']
    current_rot = get_metadata()['agent']['rotation']['y']
    obj_pos = target_obj['position']
    target_angle = calculate_angle(current_pos, obj_pos)
    angle_diff = normalize_angle(target_angle - current_rot)
    
    if abs(angle_diff) > 5:
        print(f"  🔄 객체 방향 회전 ({angle_diff:.0f}°)")
        direction = 'RotateRight' if angle_diff > 0 else 'RotateLeft'
        controller.step(action=direction, degrees=abs(angle_diff), **step_kwargs)
        capture_callback()
    
    # 6. 후진 없이 바로 탐색 (객체 최대한 가까이)
    # 후진하지 않고 그 자리에서 바로 객체 확인
    print(f"  👀 수직 탐색")
    
    # 정면
    if check_visible(get_metadata(), object_type):
        print(f"  ✓ 발견 (정면)")
        return True
    
    # 아래
    controller.step(action='LookDown', degrees=30, **step_kwargs)
    capture_callback()
    if check_visible(get_metadata(), object_type):
        print(f"  ✓ 발견 (아래)")
        return True
    
    # 위
    controller.step(action='LookUp', degrees=60, **step_kwargs)
    capture_callback()
    if check_visible(get_metadata(), object_type):
        print(f"  ✓ 발견 (위)")
        return True
    
    # 원위치
    controller.step(action='LookDown', degrees=30, **step_kwargs)
    capture_callback()
    
    print(f"  ❌ 찾지 못함")
    return False


def try_reach_position(controller, agent_id, target_pos, capture_callback, max_steps=80):
    """
    AI2-THOR의 GetShortestPath를 사용하여 목표 위치까지 이동
    
    Args:
        controller: AI2-THOR controller
        agent_id: Agent ID or None
        target_pos: 목표 위치 {'x', 'y', 'z'}
        capture_callback: 프레임 캡처
        max_steps: 최대 스텝 수
    
    Returns:
        bool: 도달 성공 여부
    """
    if agent_id is not None:
        get_metadata = lambda: controller.last_event.events[agent_id].metadata
        step_kwargs = {'agentId': agent_id}
    else:
        get_metadata = lambda: controller.last_event.metadata
        step_kwargs = {}
    
    initial_pos = get_metadata()['agent']['position']
    initial_dist = calculate_distance(initial_pos, target_pos)
    print(f"    🚶 이동 시작: {initial_dist:.2f}m")
    
    # AI2-THOR의 최단 경로 계산
    path_event = controller.step(
        action='GetShortestPathToPoint',
        target=target_pos,
        **step_kwargs
    )
    
    if not path_event.metadata['lastActionSuccess']:
        print(f"    ❌ 경로 찾기 실패")
        return False
    
    path = path_event.metadata['actionReturn']['corners']
    
    if not path or len(path) == 0:
        print(f"    ❌ 경로 없음")
        return False
    
    print(f"    🗺️ 경로: {len(path)}개 웨이포인트")
    
    # 경로를 따라 이동
    for waypoint_idx, waypoint in enumerate(path):
        current_pos = get_metadata()['agent']['position']
        
        # 현재 웨이포인트까지의 거리
        waypoint_dist = calculate_distance(current_pos, waypoint)
        
        # 웨이포인트 근처면 다음으로
        if waypoint_dist < 0.35:
            continue
        
        # 웨이포인트를 향해 이동
        attempts = 0
        max_attempts = 30  # 최대 30번 시도로 증가
        while attempts < max_attempts:
            current_pos = get_metadata()['agent']['position']
            current_rot = get_metadata()['agent']['rotation']['y']
            dist = calculate_distance(current_pos, waypoint)
            
            # 웨이포인트 도착
            if dist < 0.35:
                break
            
            # 목표 방향 계산
            target_angle = calculate_angle(current_pos, waypoint)
            angle_diff = normalize_angle(target_angle - current_rot)
            
            # 회전 필요
            if abs(angle_diff) > 15:
                direction = 'RotateRight' if angle_diff > 0 else 'RotateLeft'
                controller.step(action=direction, degrees=min(30, abs(angle_diff)), **step_kwargs)
                capture_callback()
                attempts += 1
                continue
            
            # 전진
            move_result = controller.step(action='MoveAhead', moveMagnitude=min(0.25, dist), **step_kwargs)
            capture_callback()
            attempts += 1
            
            if not move_result.metadata['lastActionSuccess']:
                # 이동 실패 - 작은 회전 후 다시 시도
                rotate_dir = 'RotateRight' if attempts % 2 == 0 else 'RotateLeft'
                controller.step(action=rotate_dir, degrees=15, **step_kwargs)
                capture_callback()
                
                # 여러 번 실패하면 이 웨이포인트 건너뜀
                if attempts > 10:
                    print(f"    ⚠️ 웨이포인트 {waypoint_idx+1} 접근 어려움, 다음으로")
                    break
        
        # 진행 상황 표시
        if waypoint_idx % 2 == 0:
            final_dist = calculate_distance(get_metadata()['agent']['position'], target_pos)
            print(f"    📍 웨이포인트 {waypoint_idx+1}/{len(path)}: 목표까지 {final_dist:.2f}m")
    
    # 최종 목표 거리 확인
    final_pos = get_metadata()['agent']['position']
    final_dist = calculate_distance(final_pos, target_pos)
    
    if final_dist <= 0.35:
        print(f"    ✓ 도착 (거리 {final_dist:.2f}m)")
        return True
    else:
        print(f"    ⚠️ 목표에서 멀리 떨어짐 (거리 {final_dist:.2f}m)")
        return False


def check_visible(metadata, object_type):
    """객체가 보이는지 확인"""
    return any(obj['visible'] and obj['objectType'] == object_type 
               for obj in metadata['objects'])
