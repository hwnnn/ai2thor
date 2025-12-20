#!/usr/bin/env python3
"""
Action-based Navigation for Multi-Agent Interleaving
- 각 액션(이동, 회전) 단위로 제어권 반환
- 병렬 실행을 위한 state machine
"""

from navigation_utils import calculate_distance, calculate_angle, normalize_angle


def navigate_single_action(controller, agent_id, nav_state, obj, capture_callback):
    """
    한 번의 액션만 수행하고 결과 반환
    
    Returns:
        (completed, new_state, result_data)
        completed: 네비게이션 완료 여부
        new_state: 다음 상태
        result_data: 상태 정보 (target_pos, target_rotation 등)
    """
    step_kwargs = {'agentId': agent_id} if agent_id is not None else {}
    
    def get_metadata():
        if agent_id is not None:
            return controller.last_event.events[agent_id].metadata
        return controller.last_event.metadata
    
    obj_id = obj['objectId']
    obj_pos = obj['position']
    
    # 초기화 - 목표 위치 계산
    if nav_state.get('phase') is None:
        print(f"  🚶 [Agent{agent_id}] 네비게이션 시작: {obj['objectType']}")
        
        # GetReachablePositions
        reachable_positions = controller.step(
            action='GetReachablePositions',
            **step_kwargs
        ).metadata['actionReturn']
        
        # GetInteractablePoses
        interactable_result = controller.step(
            action='GetInteractablePoses',
            objectId=obj_id,
            **step_kwargs
        )
        
        if not interactable_result.metadata['lastActionSuccess']:
            print(f"  ❌ [Agent{agent_id}] GetInteractablePoses 실패")
            return (True, nav_state, None)
        
        interactable_poses = interactable_result.metadata['actionReturn']
        if not interactable_poses:
            print(f"  ❌ [Agent{agent_id}] 상호작용 가능한 위치 없음")
            return (True, nav_state, None)
        
        # 교집합 찾기
        valid_positions = []
        for pose in interactable_poses:
            pose_pos = {'x': pose['x'], 'z': pose['z']}
            for reachable_pos in reachable_positions:
                dist = calculate_distance(pose_pos, reachable_pos)
                if dist < 0.26:
                    valid_positions.append({
                        'position': reachable_pos,
                        'rotation': pose.get('rotation', None),
                        'dist_to_obj': calculate_distance(reachable_pos, obj_pos)
                    })
                    break
        
        if not valid_positions:
            print(f"  ❌ [Agent{agent_id}] 도달 가능한 상호작용 위치 없음")
            return (True, nav_state, None)
        
        # 가장 가까운 위치 선택
        target = min(valid_positions, key=lambda p: p['dist_to_obj'])
        
        nav_state['phase'] = 'moving'
        nav_state['target_pos'] = target['position']
        nav_state['target_rotation'] = target['rotation']
        nav_state['rotation_attempts'] = 0
        nav_state['moved_back'] = False
        
        return (False, nav_state, None)
    
    # 이동 단계
    elif nav_state['phase'] == 'moving':
        current_pos = get_metadata()['agent']['position']
        target_pos = nav_state['target_pos']
        distance = calculate_distance(current_pos, target_pos)
        
        # 최종 목표 위치 도달 확인
        if distance <= 0.15:
            print(f"  ✓ [Agent{agent_id}] 목표 도착, 후진 후 상하 시야 확인")
            # 후진
            controller.step(action='MoveBack', **step_kwargs)
            capture_callback()
            
            # 상하 시야 확인
            # 1. 정면 확인
            visible_objs = [o for o in get_metadata()['objects']
                           if o['objectId'] == obj_id and o['visible']]
            if visible_objs:
                print(f"  ✅ [Agent{agent_id}] 객체 발견 (정면)")
                return (True, nav_state, visible_objs[0])
            
            # 2. 아래 확인
            print(f"  👇 [Agent{agent_id}] 아래 확인")
            controller.step(action='LookDown', **step_kwargs)
            capture_callback()
            visible_objs = [o for o in get_metadata()['objects']
                           if o['objectId'] == obj_id and o['visible']]
            if visible_objs:
                print(f"  ✅ [Agent{agent_id}] 객체 발견 (아래)")
                return (True, nav_state, visible_objs[0])
            
            # 3. 위 확인
            print(f"  👆 [Agent{agent_id}] 위 확인")
            controller.step(action='LookUp', **step_kwargs)
            controller.step(action='LookUp', **step_kwargs)  # 정면보다 위로
            capture_callback()
            visible_objs = [o for o in get_metadata()['objects']
                           if o['objectId'] == obj_id and o['visible']]
            if visible_objs:
                print(f"  ✅ [Agent{agent_id}] 객체 발견 (위)")
                return (True, nav_state, visible_objs[0])
            
            # 4. 시선 정면으로 복구
            controller.step(action='LookDown', **step_kwargs)
            capture_callback()
            
            print(f"  ❌ [Agent{agent_id}] 객체를 찾을 수 없음")
            return (True, nav_state, None)
        
        # GetShortestPath를 사용하여 AI2-THOR에게 경로 계산 요청
        if not nav_state.get('path_calculated') or nav_state.get('recalculate_path'):
            path_result = controller.step(
                action='GetShortestPath',
                objectId=obj_id,
                **step_kwargs
            )
            
            if path_result.metadata['lastActionSuccess']:
                corners = path_result.metadata['actionReturn']['corners']
                if corners and len(corners) > 1:
                    nav_state['path'] = corners
                    nav_state['path_index'] = 1  # 0은 현재 위치
                    nav_state['path_calculated'] = True
                    nav_state['recalculate_path'] = False
                    nav_state['stuck_count'] = 0
                    print(f"  🗺️ [Agent{agent_id}] 경로 계산 완료 ({len(corners)}개 waypoint)")
                else:
                    # 경로가 없으면 직접 이동 시도
                    nav_state['path_calculated'] = True
                    nav_state['path'] = [current_pos, target_pos]
                    nav_state['path_index'] = 1
            else:
                # GetShortestPath 실패 시 직접 계산
                nav_state['path_calculated'] = True
                nav_state['path'] = [current_pos, target_pos]
                nav_state['path_index'] = 1
        
        # 경로의 다음 waypoint로 이동
        if nav_state.get('path') and nav_state.get('path_index') < len(nav_state['path']):
            waypoint = nav_state['path'][nav_state['path_index']]
            wp_distance = calculate_distance(current_pos, waypoint)
            
            # waypoint 도달
            if wp_distance <= 0.2:
                nav_state['path_index'] += 1
                if nav_state['path_index'] >= len(nav_state['path']):
                    # 모든 waypoint 도달
                    return (False, nav_state, None)
                return (False, nav_state, None)
            
            # waypoint 방향으로 이동
            target_angle = calculate_angle(current_pos, waypoint)
            current_angle = get_metadata()['agent']['rotation']['y']
            angle_diff = normalize_angle(target_angle - current_angle)
            
            # 회전 필요
            if abs(angle_diff) > 20:
                direction = 'RotateRight' if angle_diff > 0 else 'RotateLeft'
                rotate_degrees = min(abs(angle_diff), 45)
                controller.step(action=direction, degrees=rotate_degrees, **step_kwargs)
                capture_callback()
                return (False, nav_state, None)
            
            # 전진
            move_magnitude = min(0.25, wp_distance * 0.8)
            event = controller.step(action='MoveAhead', moveMagnitude=move_magnitude, **step_kwargs)
            capture_callback()
            
            if not event.metadata['lastActionSuccess']:
                # 충돌 발생 - stuck 카운트 증가
                nav_state['stuck_count'] = nav_state.get('stuck_count', 0) + 1
                print(f"  🚧 [Agent{agent_id}] 충돌 발생 ({nav_state['stuck_count']}/3)")
                
                if nav_state['stuck_count'] >= 3:
                    # 3번 연속 충돌 시 경로 재계산
                    print(f"  🔄 [Agent{agent_id}] 경로 재계산")
                    nav_state['recalculate_path'] = True
                    nav_state['stuck_count'] = 0
                    # 후진 후 재계산
                    controller.step(action='MoveBack', moveMagnitude=0.3, **step_kwargs)
                    capture_callback()
                    controller.step(action='RotateRight', degrees=45, **step_kwargs)
                    capture_callback()
                else:
                    # 소폭 회전 후 재시도
                    controller.step(action='RotateRight', degrees=15, **step_kwargs)
                    capture_callback()
            else:
                # 성공 시 stuck_count 초기화
                nav_state['stuck_count'] = 0
        
        return (False, nav_state, None)
    
    return (True, nav_state, None)
    
    return (True, nav_state, None)
