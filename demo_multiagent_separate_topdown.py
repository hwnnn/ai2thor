#!/usr/bin/env python3
"""
Multi-Agent 데모: Agent 0을 Topdown Camera로 사용
- 하나의 Controller에서 agentCount=3으로 실행
- Agent 0: 천장에 고정 (Topdown camera 역할)
- Agent 1: 토마토 자르기
- Agent 2: 불 켜기
- 영상: Topview만 녹화 (Agent POV는 주석 처리)
"""

import os
import sys
import cv2
import numpy as np
import random
import math
from datetime import datetime
from ai2thor.controller import Controller

# 프로젝트 루트를 Python path에 추가
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


class AgentCoordinator:
    """에이전트 간 충돌 회피 관리"""
    
    def __init__(self):
        self.agent_positions = {}  # agent_id -> (x, z)
        self.min_distance = 0.5
    
    def update_position(self, agent_id, x, z):
        """에이전트 위치 업데이트"""
        self.agent_positions[agent_id] = (x, z)
    
    def check_collision(self, agent_id, target_x, target_z):
        """다른 에이전트와 충돌 가능성 체크"""
        for other_id, (other_x, other_z) in self.agent_positions.items():
            if other_id == agent_id:
                continue
            dist = math.sqrt((target_x - other_x)**2 + (target_z - other_z)**2)
            if dist < self.min_distance:
                return True
        return False


def calculate_distance(pos1, pos2):
    """두 위치 간 거리 계산"""
    return math.sqrt((pos1['x'] - pos2['x'])**2 + (pos1['z'] - pos2['z'])**2)


def get_random_position(reachable_positions, exclude_positions=None, min_distance_from_exclude=2.0, 
                       other_agent_pos=None, min_distance_between_agents=1.5):
    """이동 가능한 위치 중 랜덤 선택 (제약 조건 적용)"""
    valid_positions = []
    
    # 씬 중심 계산
    center_x = np.mean([p['x'] for p in reachable_positions])
    center_z = np.mean([p['z'] for p in reachable_positions])
    
    for pos in reachable_positions:
        valid = True
        
        # 1. 목표 객체로부터 충분히 멀리
        if exclude_positions:
            for exclude_pos in exclude_positions:
                dist = calculate_distance(pos, exclude_pos)
                if dist < min_distance_from_exclude:
                    valid = False
                    break
        
        # 2. 다른 agent와 충분히 떨어진 곳
        if valid and other_agent_pos:
            dist = calculate_distance(pos, other_agent_pos)
            if dist < min_distance_between_agents:
                valid = False
        
        if valid:
            # 중심으로부터의 거리 계산
            dist_from_center = math.sqrt((pos['x'] - center_x)**2 + (pos['z'] - center_z)**2)
            valid_positions.append((pos, dist_from_center))
    
    if not valid_positions:
        return random.choice(reachable_positions)
    
    # 50% 확률로 주변부 선호
    if random.random() < 0.5:
        # 중심에서 먼 위치 30%
        valid_positions.sort(key=lambda x: x[1], reverse=True)
        candidates = valid_positions[:max(1, len(valid_positions) // 3)]
        return random.choice(candidates)[0]
    else:
        # 완전 랜덤
        return random.choice(valid_positions)[0]


def navigate_to_object(controller, agent_id, target_obj, coordinator, capture_func):
    """목표 객체로 이동 (GetShortestPath 사용)"""
    event = controller.last_event
    current_pos = event.events[agent_id].metadata['agent']['position']
    target_pos = target_obj['position']
    
    print(f"[{agent_id}] 목표 위치로 이동 시작...")
    
    # GetShortestPath로 경로 찾기
    path_event = controller.step(
        action='GetShortestPath',
        agentId=agent_id,
        objectId=target_obj['objectId'],
        allowedError=0.5
    )
    
    if not path_event.metadata['lastActionSuccess'] or not path_event.metadata.get('actionReturn'):
        print(f"[{agent_id}] ⚠️ 경로 찾기 실패, 직접 이동 시도")
        return navigate_directly(controller, agent_id, target_pos, coordinator, capture_func)
    
    corners = path_event.metadata['actionReturn']['corners']
    print(f"[{agent_id}] 경로 포인트: {len(corners)}개")
    
    # 각 코너로 이동
    for i, corner in enumerate(corners):
        if not navigate_to_corner(controller, agent_id, corner, coordinator, capture_func):
            print(f"[{agent_id}] ⚠️ 코너 {i+1} 도달 실패")
    
    # 목표 객체로 최종 접근 (0.3m까지)
    print(f"[{agent_id}] 목표 객체로 최종 접근 중 (0.3m 목표)...")
    final_approach_attempts = 0
    max_final_attempts = 50
    
    while final_approach_attempts < max_final_attempts:
        current_pos = controller.last_event.events[agent_id].metadata['agent']['position']
        distance_to_target = calculate_distance(current_pos, target_pos)
        
        if distance_to_target < 0.3:  # 30cm 이내
            print(f"[{agent_id}] ✓ 목표 객체 0.3m 이내 도착 (거리: {distance_to_target:.2f}m)")
            return True
        
        # 목표 방향으로 회전
        dx = target_pos['x'] - current_pos['x']
        dz = target_pos['z'] - current_pos['z']
        target_angle = math.degrees(math.atan2(dx, dz))
        current_rotation = controller.last_event.events[agent_id].metadata['agent']['rotation']['y']
        angle_diff = (target_angle - current_rotation + 180) % 360 - 180
        
        if abs(angle_diff) > 10:
            direction = 'RotateRight' if angle_diff > 0 else 'RotateLeft'
            controller.step(action=direction, agentId=agent_id, degrees=min(20, abs(angle_diff)))
            capture_func()
        else:
            # 전진
            event = controller.step(action='MoveAhead', agentId=agent_id, moveMagnitude=0.1)
            capture_func()
            
            if not event.metadata['lastActionSuccess']:
                # 이동 실패 시 약간 회전 후 재시도
                controller.step(action='RotateRight', agentId=agent_id, degrees=15)
                capture_func()
        
        final_approach_attempts += 1
    
    final_event = controller.last_event
    final_pos = final_event.events[agent_id].metadata['agent']['position']
    final_dist = calculate_distance(final_pos, target_pos)
    
    print(f"[{agent_id}] ✓ 목표 지점 도착 (거리: {final_dist:.2f}m)")
    return True


def navigate_to_corner(controller, agent_id, corner, coordinator, capture_func):
    """특정 코너로 이동"""
    max_attempts = 30
    consecutive_failures = 0
    prev_pos = None
    
    for attempt in range(max_attempts):
        event = controller.last_event
        current_pos = event.events[agent_id].metadata['agent']['position']
        
        # Stuck 감지
        if prev_pos:
            moved = math.sqrt((current_pos['x'] - prev_pos['x'])**2 + (current_pos['z'] - prev_pos['z'])**2)
            if moved < 0.01 and consecutive_failures >= 3:
                print(f"[{agent_id}] 🚧 Stuck 감지, 우회 시도")
                controller.step(action='MoveBack', agentId=agent_id, moveMagnitude=0.5)
                capture_func()
                controller.step(action='RotateRight', agentId=agent_id, degrees=60)
                capture_func()
                consecutive_failures = 0
                continue
        
        prev_pos = current_pos.copy()
        
        # 거리 계산
        dist = math.sqrt((corner['x'] - current_pos['x'])**2 + (corner['z'] - current_pos['z'])**2)
        
        if dist < 0.2:
            return True
        
        # 방향 계산 및 회전
        dx = corner['x'] - current_pos['x']
        dz = corner['z'] - current_pos['z']
        target_angle = math.degrees(math.atan2(dx, dz))
        current_rotation = event.events[agent_id].metadata['agent']['rotation']['y']
        angle_diff = (target_angle - current_rotation + 180) % 360 - 180
        
        if abs(angle_diff) > 15:
            action = 'RotateRight' if angle_diff > 0 else 'RotateLeft'
            controller.step(action=action, agentId=agent_id, degrees=min(30, abs(angle_diff)))
            capture_func()
            continue
        
        # 이동
        move_event = controller.step(action='MoveAhead', agentId=agent_id, moveMagnitude=0.25)
        capture_func()
        
        new_pos = move_event.events[agent_id].metadata['agent']['position']
        coordinator.update_position(agent_id, new_pos['x'], new_pos['z'])
        
        if not move_event.metadata['lastActionSuccess']:
            consecutive_failures += 1
            print(f"[{agent_id}] 이동 실패 ({consecutive_failures}회)")
            
            if consecutive_failures >= 3:
                print(f"[{agent_id}] 🔄 우회 경로 탐색")
                controller.step(action='MoveBack', agentId=agent_id, moveMagnitude=0.5)
                capture_func()
                controller.step(action='RotateRight', agentId=agent_id, degrees=60)
                capture_func()
                consecutive_failures = 0
        else:
            consecutive_failures = 0
    
    return False


def navigate_directly(controller, agent_id, target_pos, coordinator, capture_func):
    """직접 목표 위치로 이동 (경로 찾기 실패 시)"""
    max_attempts = 30
    consecutive_failures = 0
    
    for _ in range(max_attempts):
        event = controller.last_event
        current_pos = event.events[agent_id].metadata['agent']['position']
        distance = calculate_distance(current_pos, target_pos)
        
        if distance < 1.5:
            return True
        
        # 방향 계산
        dx = target_pos['x'] - current_pos['x']
        dz = target_pos['z'] - current_pos['z']
        target_angle = math.degrees(math.atan2(dx, dz))
        current_rotation = event.events[agent_id].metadata['agent']['rotation']['y']
        angle_diff = (target_angle - current_rotation + 180) % 360 - 180
        
        # 회전
        if abs(angle_diff) > 15:
            action = 'RotateRight' if angle_diff > 0 else 'RotateLeft'
            controller.step(action=action, agentId=agent_id, degrees=min(30, abs(angle_diff)))
            capture_func()
            continue
        
        # 이동
        move_event = controller.step(action='MoveAhead', agentId=agent_id, moveMagnitude=0.25)
        capture_func()
        
        if not move_event.metadata['lastActionSuccess']:
            consecutive_failures += 1
            if consecutive_failures >= 3:
                controller.step(action='MoveBack', agentId=agent_id, moveMagnitude=0.5)
                capture_func()
                controller.step(action='RotateRight', agentId=agent_id, degrees=45)
                capture_func()
                consecutive_failures = 0
        else:
            consecutive_failures = 0
    
    return False


def search_object_nearby(controller, agent_id, object_type, capture_func):
    """근처에서 객체 탐색 (상하좌우 회전)"""
    print(f"[{agent_id}] 근처에서 {object_type} 탐색 중 (상하좌우 회전)...")
    
    # 상하 시야각 조정
    for horizon in [0, 30, -30, 15, -15]:
        # 시야각 조정
        if horizon < 0:
            controller.step(action='LookUp', agentId=agent_id, degrees=abs(horizon))
        elif horizon > 0:
            controller.step(action='LookDown', agentId=agent_id, degrees=abs(horizon))
        capture_func()
        
        # 좌우 360도 회전
        for rotation_step in range(12):
            if rotation_step > 0:
                controller.step(action='RotateRight', agentId=agent_id, degrees=30)
                capture_func()
            
            # 객체 확인
            event = controller.last_event
            for obj in event.events[agent_id].metadata['objects']:
                if obj['objectType'] == object_type and obj['visible']:
                    print(f"[{agent_id}] ✓ {object_type} 발견!")
                    # 시야각 원복
                    if horizon < 0:
                        controller.step(action='LookDown', agentId=agent_id, degrees=abs(horizon))
                    elif horizon > 0:
                        controller.step(action='LookUp', agentId=agent_id, degrees=abs(horizon))
                    capture_func()
                    return obj
        
        # 시야각 원복
        if horizon < 0:
            controller.step(action='LookDown', agentId=agent_id, degrees=abs(horizon))
        elif horizon > 0:
            controller.step(action='LookUp', agentId=agent_id, degrees=abs(horizon))
        capture_func()
    
    return None


def interact_with_object(controller, agent_id, obj, action_type, capture_func):
    """객체와 상호작용"""
    print(f"[{agent_id}] {obj['objectType']}와 상호작용 시도...")
    
    max_attempts = 5
    for attempt in range(max_attempts):
        if action_type == 'pickup':
            event = controller.step(
                action='PickupObject',
                agentId=agent_id,
                objectId=obj['objectId'],
                forceAction=True
            )
        elif action_type == 'toggle':
            event = controller.step(
                action='ToggleObjectOn',
                agentId=agent_id,
                objectId=obj['objectId'],
                forceAction=True
            )
        elif action_type == 'slice':
            event = controller.step(
                action='SliceObject',
                agentId=agent_id,
                objectId=obj['objectId'],
                forceAction=True
            )
        
        capture_func()
        
        if event.metadata['lastActionSuccess']:
            print(f"[{agent_id}] ✓ 상호작용 성공!")
            return True
        else:
            print(f"[{agent_id}] ⚠️ 실패 ({attempt+1}/{max_attempts}): {event.metadata.get('errorMessage', 'Unknown')}")
    
    return False


def agent_task(controller, agent_id, target_object_type, action_type, coordinator, capture_func):
    """에이전트 태스크 실행"""
    print(f"\n{'='*60}")
    print(f"[{agent_id}] {target_object_type} 미션 시작")
    print(f"{'='*60}")
    
    # 1. 객체 찾기
    event = controller.last_event
    target_obj = None
    for obj in event.events[agent_id].metadata['objects']:
        if obj['objectType'] == target_object_type:
            target_obj = obj
            print(f"[{agent_id}] ✓ {target_object_type} 위치 확인: ({obj['position']['x']:.2f}, {obj['position']['y']:.2f}, {obj['position']['z']:.2f})")
            break
    
    if not target_obj:
        print(f"[{agent_id}] ✗ {target_object_type}를 찾을 수 없습니다")
        return False
    
    # 2. 객체로 이동
    if not navigate_to_object(controller, agent_id, target_obj, coordinator, capture_func):
        print(f"[{agent_id}] ✗ 이동 실패")
        return False
    
    # 3. 근처 탐색
    found_obj = search_object_nearby(controller, agent_id, target_object_type, capture_func)
    if not found_obj:
        print(f"[{agent_id}] ✗ 객체를 찾을 수 없습니다")
        return False
    
    # 4. 상호작용
    if interact_with_object(controller, agent_id, found_obj, action_type, capture_func):
        return True
    
    return False


def main():
    print("=" * 60)
    print("Multi-Agent 데모: Agent 0을 Topdown Camera로 사용")
    print("=" * 60)
    
    # 출력 디렉토리
    output_dir = '/Users/jaehwan/Desktop/JaeHwan/workspace/ai2thor/output_videos'
    os.makedirs(output_dir, exist_ok=True)
    
    # 타임스탬프
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # 비디오 작성기 초기화 (Topview만)
    fps = 6
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    
    video_writers = {
        'topview': cv2.VideoWriter(
            os.path.join(output_dir, f'topview_{timestamp}.mp4'),
            fourcc, fps, (1920, 1080)
        )
        # Agent POV는 주석 처리
        # 'agent_1_pov': cv2.VideoWriter(...),
        # 'agent_2_pov': cv2.VideoWriter(...),
    }
    
    frame_count = 0
    
    def capture_frame():
        """프레임 캡처 함수"""
        nonlocal frame_count
        
        # Main controller에서 agent POV 가져오기
        main_event = controller.last_event
        frame0 = main_event.events[0].frame
        frame1 = main_event.events[1].frame
        
        # Topdown controller에서 topdown view 가져오기
        topdown_cont (Topview만)"""
        nonlocal frame_count
        
        # Agent 0 (천장 고정)의 프레임이 topdown view
        event = controller.last_event
        topdown_frame = event.events[0].frame  # Agent 0 = Topdown camera
        
        # Agent POV는 주석 처리
        # frame1 = event.events[1].frame  # Agent 1 POV
        # frame2 = event.events[2].frame  # Agent 2 POV
        
        # 해상도 조정
        topdown_bgr = cv2.cvtColor(topdown_frame, cv2.COLOR_RGB2BGR)
        topdown_resized = cv2.resize(topdown_bgr, (1920, 1080))
        
        # Topview만 저장
        video_writers['topview'].write(topdown_resiz
            width=800,
            height=600,
            fieldOfView=90,
            visibilityDistance=3.0,
            makeAgentsVisible=True,
            renderDepthImage=False,
            renderInstanceSegmentation=False
        )
        print("✓ Main Controller 초기화 완료")
        
        # 씬 정보 수집
        event = controller.last_event
        reachable_positions = controller.step(
            action='GetReachablePositions',
            agentId=0
        ).metadata['actionReturn']
        
        # 씬 중심 계산
        center_x = np.mean([p['x'] for p in reachable_positions])
        center_z = np.mean([p['z'] for p in reachable_positions])
        
        # Topdown Controller 초기화 (천장에서 내려다보기)
        # Controller 초기화 (3 agents: 1 topdown camera + 2 workers)
        print("\n🎮 Controller 초기화 중... (3 agents)")
        controller = Controller(
            scene="FloorPlan1",
            agentCount=3,
            width=1920,  # Topdown camera 해상도
            height=1080,
            fieldOfView=90,
            visibilityDistance=10.0,  # Topdown은 넓게 봐야 함
            makeAgentsVisible=True,
            renderDepthImage=False,
            renderInstanceSegmentation=False
        )
        print("✓eleportFull',
            x=center_x,
            y=5.0,
            z=center_z,
            rotation={'x': 90, 'y': 0, 'z': 0},  # 90도 = 아래를 내려다봄
            horizon=0,
            standing1  # Agent 1로 reachable positions 가져오기
        ).metadata['actionReturn']
        
        # 씬 중심 계산
        center_x = np.mean([p['x'] for p in reachable_positions])
        center_z = np.mean([p['z'] for p in reachable_positions])
        
        # Agent 0을 천장에 고정 (Topdown camera)
        print("\n📹 Agent 0을 Topdown Camera로 설정 중...")
        controller.step(
            action='TeleportFull',
            agentId=0,
            x=center_x,
            y=5.0,
            z=center_z,
            rotation={'x': 90, 'y': 0, 'z': 0},  # 90도 = 아래를 내려다봄
            horizon=0,
            standing=True
        )
        print("✓ Agent 0 = Topdown Camera (천장 고정['z']:.2f})")
        print(f"[agent_1] 위치: ({pos_1['x']:.2f}, {pos_1['z']:.2f})")
        print(f"📏 에이전트 간 거리: {calculate_distance(pos_0, pos_1):.2f}m")
        
        # Coordinator 초기화
        coordinator = AgentCoordinator()
        coordinator.update_position(0, pos_0['x'], pos_0['z'])
        coordinator.update_position(1, pos_1['x'], pos_1['z'])
        
        print("\n📹 비디오 작성기 초기화 완료")
        print("\n🎬 태스크 시작...")
        capture_frame()1].metadata['objects']  # Agent 1 메타데이터
        target_objects = []
        for obj in all_objects:
            if obj['objectType'] in ['Tomato', 'LightSwitch']:
                target_objects.append(obj)
        
        exclude_positions = [obj['position'] for obj in target_objects]
        print(f"제외 위치: {len(exclude_positions)}개 (목표 객체 주변)")
        
        # Agent 1, 2 랜덤 위치 설정
        print("\n📍 Agent 1, 2 랜덤 위치 설정...")
        pos_1 = get_random_position(reachable_positions, exclude_positions)
        pos_2 = 1: 토마토 슬라이스
        success_1 = agent_task(controller, 1, 'Tomato', 'slice', coordinator, capture_frame)
        
        # Agent 2: 불 켜기
        success_2 = agent_task(controller, 2, 'LightSwitch', 'toggle', coordinator, capture_frame)
        
        # 결과 출력
        print(f"\n{'='*60}")
        print("📊 작업 결과")
        print(f"{'='*60}")
        print(f"[agent_1] 토마토 자르기: {'✓ 성공' if success_1 else '✗ 실패'}")
        print(f"[agent_2] 불 켜기: {'✓ 성공' if success_2os_1['z'])
        coordinator.update_position(2, pos_2['x'], pos_2
        # 비디오 작성기 닫기
        for writer in video_writers.values():
            writer.release()
        
        # Controller 종료
        if 'controller' in locals():
            controller.stop()
        if 'topdown_controller' in locals():
            topdown_controller.stop()
        
        print("✓ 모든 시스템 종료 완료")
    
    print("\n✅ 데모 완료!")


if __name__ == "__main__":
    main()