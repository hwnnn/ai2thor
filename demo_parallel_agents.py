#!/usr/bin/env python3
"""
개선된 두 에이전트 데모: 병렬 실행 + 충돌 회피
- Agent 1: 토마토를 찾아서 상호작용
- Agent 2: 불 켜는 버튼(LightSwitch) 찾아서 누르기
- 병렬 실행: 두 에이전트가 동시에 작업 수행
- 충돌 회피: 경로가 겹칠 경우 우회
- tests 파일 방식 준수: frame_count 기반 capture
"""

import os
import sys
import cv2
import numpy as np
import random
import math
import threading
import time
from datetime import datetime
from ai2thor.controller import Controller

# 프로젝트 루트를 Python path에 추가
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from multi_agent_system import AI2THORAgent, AgentConfig
from multi_agent_visualizer import MultiAgentVisualizer


class AgentCoordinator:
    """에이전트 간 충돌 회피를 위한 코디네이터"""
    
    def __init__(self):
        self.agent_positions = {}  # agent_id -> (x, z)
        self.agent_targets = {}    # agent_id -> (x, z)
        self.lock = threading.Lock()
        self.min_distance = 0.5    # 최소 거리 (미터)
    
    def update_position(self, agent_id, x, z):
        """에이전트 위치 업데이트"""
        with self.lock:
            self.agent_positions[agent_id] = (x, z)
    
    def set_target(self, agent_id, x, z):
        """목표 위치 설정"""
        with self.lock:
            self.agent_targets[agent_id] = (x, z)
    
    def check_collision(self, agent_id, target_x, target_z):
        """다른 에이전트와 충돌 가능성 체크"""
        with self.lock:
            for other_id, (other_x, other_z) in self.agent_positions.items():
                if other_id == agent_id:
                    continue
                
                # 거리 계산
                dist = math.sqrt((target_x - other_x)**2 + (target_z - other_z)**2)
                if dist < self.min_distance:
                    return True  # 충돌 위험
            
            return False  # 안전
    
    def wait_if_collision(self, agent_id, target_x, target_z, max_wait=2.0):
        """충돌 위험이 있으면 대기"""
        wait_time = 0
        while self.check_collision(agent_id, target_x, target_z) and wait_time < max_wait:
            time.sleep(0.1)
            wait_time += 0.1
        
        return wait_time < max_wait  # 성공적으로 대기 완료


def get_random_position(reachable_positions, exclude_positions=None, min_distance_from_exclude=2.0, other_agent_pos=None, min_distance_between_agents=1.5):
    """이동 가능한 위치 중 랜덤 선택 (제약 조건 적용)
    
    Args:
        reachable_positions: 이동 가능한 위치 리스트
        exclude_positions: 제외할 위치 리스트 (목표 객체 위치 등)
        min_distance_from_exclude: 제외 위치로부터 최소 거리
        other_agent_pos: 다른 agent의 위치
        min_distance_between_agents: agent 간 최소 거리
    """
    # 넓은 범위에 분산되도록 후보 위치를 먼저 필터링
    valid_positions = []
    
    for pos in reachable_positions:
        valid = True
        
        # 1. 제외 위치(목표 객체)로부터 충분히 멀리 떨어진 곳
        if exclude_positions:
            for exclude_pos in exclude_positions:
                dist = math.sqrt((pos['x'] - exclude_pos['x'])**2 + (pos['z'] - exclude_pos['z'])**2)
                if dist < min_distance_from_exclude:
                    valid = False
                    break
        
        # 2. 다른 agent와 충분히 떨어진 곳
        if valid and other_agent_pos:
            dist = math.sqrt((pos['x'] - other_agent_pos['x'])**2 + (pos['z'] - other_agent_pos['z'])**2)
            if dist < min_distance_between_agents:
                valid = False
        
        if valid:
            valid_positions.append(pos)
    
    if not valid_positions:
        print("⚠️ 제약 조건을 만족하는 위치가 없어 모든 위치 중 랜덤 선택")
        return random.choice(reachable_positions)
    
    # 3. 더 넓은 범위에 분산: 중심에서 먼 위치 우선 선택 (50% 확률)
    if random.random() < 0.5 and len(valid_positions) > 10:
        # 중심 계산
        center_x = sum(p['x'] for p in valid_positions) / len(valid_positions)
        center_z = sum(p['z'] for p in valid_positions) / len(valid_positions)
        
        # 중심에서 먼 순서로 정렬
        valid_positions.sort(
            key=lambda p: math.sqrt((p['x'] - center_x)**2 + (p['z'] - center_z)**2),
            reverse=True
        )
        
        # 상위 30% 중에서 선택
        top_30_percent = max(1, len(valid_positions) // 3)
        return random.choice(valid_positions[:top_30_percent])
    
    return random.choice(valid_positions)


def find_object_location(controller, object_type):
    """객체의 위치 찾기"""
    event = controller.last_event
    for obj in event.metadata['objects']:
        if object_type in obj['objectType']:
            return obj
    return None


def calculate_distance(pos1, pos2):
    """두 위치 사이의 거리 계산"""
    return math.sqrt((pos1['x'] - pos2['x'])**2 + (pos1['z'] - pos2['z'])**2)


def navigate_to_object(agent, agent_id, target_obj, coordinator, capture_func):
    """객체로 이동 (GetShortestPath 사용 + 충돌 회피)"""
    print(f"[{agent_id}] 목표 위치로 이동 시작...")
    
    target_pos = target_obj['position']
    coordinator.set_target(agent_id, target_pos['x'], target_pos['z'])
    
    # GetShortestPath로 최적 경로 계산
    current_event = agent.controller.last_event
    current_pos = current_event.metadata['agent']['position']
    
    # 객체 앞 1.5m 위치로 경로 찾기
    path_event = agent.controller.step(
        action='GetShortestPath',
        objectId=target_obj['objectId'],
        position=current_pos
    )
    
    if not path_event.metadata['lastActionSuccess'] or not path_event.metadata['actionReturn']:
        print(f"[{agent_id}] ⚠️ 경로를 찾을 수 없습니다, 직접 이동 시도...")
        # 경로를 찾을 수 없으면 직접 이동
        return navigate_directly(agent, agent_id, target_pos, coordinator, capture_func)
    
    corners = path_event.metadata['actionReturn']['corners']
    print(f"[{agent_id}] 경로 포인트: {len(corners)}개")
    
    # 경로를 따라 이동
    for i, corner in enumerate(corners[1:], 1):  # 첫 번째는 현재 위치
        print(f"[{agent_id}] 포인트 {i}/{len(corners)-1}로 이동 중...")
        
        # 해당 포인트로 이동
        consecutive_failures = 0
        prev_pos = None
        stuck_counter = 0
        
        for attempt in range(20):
            current_event = agent.controller.last_event
            current_pos = current_event.metadata['agent']['position']
            
            # 진행 상황 체크 (같은 위치에 갇혀있는지)
            if prev_pos:
                moved_dist = math.sqrt((current_pos['x'] - prev_pos['x'])**2 + (current_pos['z'] - prev_pos['z'])**2)
                if moved_dist < 0.05:  # 거의 움직이지 않음
                    stuck_counter += 1
                else:
                    stuck_counter = 0
            
            # 3회 연속 갇혀있으면 우회 시도
            if stuck_counter >= 3:
                print(f"[{agent_id}] 🚧 막힘 감지! 우회 시도 중...")
                # 백스텝
                agent.controller.step('MoveBack', moveMagnitude=0.5)
                capture_func()
                # 큰 각도로 회전
                agent.controller.step('RotateRight', degrees=60)
                capture_func()
                # 다시 시도
                stuck_counter = 0
                consecutive_failures = 0
                continue
            
            prev_pos = current_pos.copy()
            
            # 거리 계산
            dist = math.sqrt((corner['x'] - current_pos['x'])**2 + (corner['z'] - current_pos['z'])**2)
            
            if dist < 0.3:  # 충분히 가까움
                consecutive_failures = 0
                break
            
            # 방향 계산
            dx = corner['x'] - current_pos['x']
            dz = corner['z'] - current_pos['z']
            target_angle = math.degrees(math.atan2(dx, dz))
            current_rotation = current_event.metadata['agent']['rotation']['y']
            angle_diff = (target_angle - current_rotation + 180) % 360 - 180
            
            # 회전
            if abs(angle_diff) > 15:
                if angle_diff > 0:
                    agent.controller.step('RotateRight', degrees=min(30, abs(angle_diff)))
                else:
                    agent.controller.step('RotateLeft', degrees=min(30, abs(angle_diff)))
                capture_func()
                continue
            
            # 충돌 체크
            next_x = current_pos['x'] + 0.25 * math.sin(math.radians(current_rotation))
            next_z = current_pos['z'] + 0.25 * math.cos(math.radians(current_rotation))
            
            if not coordinator.wait_if_collision(agent_id, next_x, next_z, max_wait=1.0):
                print(f"[{agent_id}] 경로 충돌, 잠시 대기...")
                time.sleep(0.5)
                continue
            
            # 이동
            event = agent.controller.step('MoveAhead', moveMagnitude=0.25)
            capture_func()
            
            new_pos = event.metadata['agent']['position']
            coordinator.update_position(agent_id, new_pos['x'], new_pos['z'])
            
            if not event.metadata['lastActionSuccess']:
                consecutive_failures += 1
                print(f"[{agent_id}] 이동 실패 ({consecutive_failures}회)")
                
                # 연속 3회 실패 시 우회 로직
                if consecutive_failures >= 3:
                    print(f"[{agent_id}] 🔄 우회 경로 탐색 중...")
                    # 백스텝
                    agent.controller.step('MoveBack', moveMagnitude=0.5)
                    capture_func()
                    # 반대 방향으로 회전
                    agent.controller.step('RotateLeft' if consecutive_failures % 2 == 0 else 'RotateRight', degrees=45)
                    capture_func()
                    # 조금 전진
                    agent.controller.step('MoveAhead', moveMagnitude=0.25)
                    capture_func()
                    consecutive_failures = 0
                else:
                    # 조금만 회전
                    agent.controller.step('RotateRight', degrees=15)
                    capture_func()
            else:
                consecutive_failures = 0
    
    # 최종 거리 확인
    final_event = agent.controller.last_event
    final_pos = final_event.metadata['agent']['position']
    final_dist = calculate_distance(final_pos, target_pos)
    
    print(f"[{agent_id}] ✓ 목표 지점 도착 (거리: {final_dist:.2f}m)")
    return final_dist < 2.0


def navigate_directly(agent, agent_id, target_pos, coordinator, capture_func):
    """직접 목표 위치로 이동 (경로 찾기 실패 시)"""
    max_attempts = 30
    consecutive_failures = 0
    prev_pos = None
    stuck_counter = 0
    
    for attempt in range(max_attempts):
        current_event = agent.controller.last_event
        current_pos = current_event.metadata['agent']['position']
        
        # 진행 상황 체크
        if prev_pos:
            moved_dist = math.sqrt((current_pos['x'] - prev_pos['x'])**2 + (current_pos['z'] - prev_pos['z'])**2)
            if moved_dist < 0.05:
                stuck_counter += 1
            else:
                stuck_counter = 0
        
        # 갇혀있으면 우회
        if stuck_counter >= 3:
            print(f"[{agent_id}] 🚧 막힘 감지! 우회 시도 중...")
            agent.controller.step('MoveBack', moveMagnitude=0.5)
            capture_func()
            agent.controller.step('RotateRight', degrees=60)
            capture_func()
            stuck_counter = 0
            consecutive_failures = 0
            continue
        
        prev_pos = current_pos.copy()
        distance = calculate_distance(current_pos, target_pos)
        
        if distance < 1.5:
            return True
        
        # 방향 계산
        dx = target_pos['x'] - current_pos['x']
        dz = target_pos['z'] - current_pos['z']
        target_angle = math.degrees(math.atan2(dx, dz))
        current_rotation = current_event.metadata['agent']['rotation']['y']
        angle_diff = (target_angle - current_rotation + 180) % 360 - 180
        
        # 회전
        if abs(angle_diff) > 15:
            if angle_diff > 0:
                agent.controller.step('RotateRight', degrees=min(30, abs(angle_diff)))
            else:
                agent.controller.step('RotateLeft', degrees=min(30, abs(angle_diff)))
            capture_func()
            continue
        
        # 이동
        event = agent.controller.step('MoveAhead', moveMagnitude=0.25)
        capture_func()
        
        if not event.metadata['lastActionSuccess']:
            consecutive_failures += 1
            print(f"[{agent_id}] 이동 실패 ({consecutive_failures}회)")
            
            # 연속 3회 실패 시 우회
            if consecutive_failures >= 3:
                print(f"[{agent_id}] 🔄 우회 경로 탐색 중...")
                agent.controller.step('MoveBack', moveMagnitude=0.5)
                capture_func()
                agent.controller.step('RotateLeft' if consecutive_failures % 2 == 0 else 'RotateRight', degrees=45)
                capture_func()
                agent.controller.step('MoveAhead', moveMagnitude=0.25)
                capture_func()
                consecutive_failures = 0
            else:
                agent.controller.step('RotateRight', degrees=30)
                capture_func()
        else:
            consecutive_failures = 0
    
    return False


def search_object_nearby(agent, agent_id, object_type, capture_func):
    """근처에서 객체 탐색 (고개 상하좌우 회전)"""
    print(f"[{agent_id}] 근처에서 {object_type} 탐색 중...")
    
    # 360도 회전하며 탐색
    for rotation_step in range(12):
        if rotation_step > 0:
            agent.controller.step('RotateRight', degrees=30)
            capture_func()
        
        # 각 방향에서 고개 위아래로
        for horizon in [-30, -60, -30, 0, 30, 60, 30, 0]:
            if horizon < 0:
                agent.controller.step('LookUp', degrees=abs(horizon))
            elif horizon > 0:
                agent.controller.step('LookDown', degrees=horizon)
            
            capture_func()
            
            # 객체 검색
            event = agent.controller.last_event
            for obj in event.metadata['objects']:
                if object_type in obj['objectType'] and obj['visible']:
                    print(f"[{agent_id}] ✓ {object_type} 발견!")
                    # 고개 정면으로
                    current_horizon = event.metadata['agent']['cameraHorizon']
                    if current_horizon < 0:
                        agent.controller.step('LookDown', degrees=abs(current_horizon))
                    elif current_horizon > 0:
                        agent.controller.step('LookUp', degrees=current_horizon)
                    capture_func()
                    return obj
    
    print(f"[{agent_id}] ❌ {object_type}를 찾을 수 없습니다")
    return None


def interact_with_object(agent, agent_id, obj, action_type, capture_func):
    """객체와 상호작용"""
    print(f"[{agent_id}] {obj['objectType']}와 상호작용 시도...")
    
    # 약간 더 가까이
    for _ in range(3):
        event = agent.controller.step('MoveAhead', moveMagnitude=0.1)
        capture_func()
        if not event.metadata['lastActionSuccess']:
            break
    
    # 상호작용
    if action_type == 'pickup':
        event = agent.controller.step(action='PickupObject', objectId=obj['objectId'], forceAction=True)
    elif action_type == 'toggle':
        action = 'ToggleObjectOn' if not obj.get('isToggled', False) else 'ToggleObjectOff'
        event = agent.controller.step(action=action, objectId=obj['objectId'], forceAction=True)
    
    capture_func()
    
    if event.metadata['lastActionSuccess']:
        print(f"[{agent_id}] ✓ 상호작용 성공!")
        return True
    else:
        print(f"[{agent_id}] ⚠️ 상호작용 실패: {event.metadata.get('errorMessage', '')}")
        return False


def agent_task(agent, agent_id, object_type, action_type, coordinator, capture_func, results):
    """에이전트 작업 (병렬 실행용)"""
    try:
        print(f"\n{'=' * 60}")
        print(f"[{agent_id}] {object_type} 미션 시작")
        print(f"{'=' * 60}")
        
        # 1. 객체 위치 찾기
        target_obj = find_object_location(agent.controller, object_type)
        if not target_obj:
            print(f"[{agent_id}] ❌ {object_type}를 scene에서 찾을 수 없습니다")
            results[agent_id] = False
            return
        
        print(f"[{agent_id}] ✓ {object_type} 위치 확인: ({target_obj['position']['x']:.2f}, {target_obj['position']['y']:.2f}, {target_obj['position']['z']:.2f})")
        
        # 2. 객체로 이동
        if not navigate_to_object(agent, agent_id, target_obj, coordinator, capture_func):
            results[agent_id] = False
            return
        
        # 3. 근처에서 탐색
        found_obj = search_object_nearby(agent, agent_id, object_type, capture_func)
        if not found_obj:
            results[agent_id] = False
            return
        
        # 4. 상호작용
        success = interact_with_object(agent, agent_id, found_obj, action_type, capture_func)
        results[agent_id] = success
        
    except Exception as e:
        print(f"[{agent_id}] ❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()
        results[agent_id] = False


def main():
    """메인 실행 함수"""
    print("=" * 60)
    print("개선된 두 에이전트 데모: 병렬 실행 + 충돌 회피")
    print("=" * 60)
    
    # 출력 디렉토리
    os.makedirs('output_videos', exist_ok=True)
    os.makedirs('output_images', exist_ok=True)
    
    scene = "FloorPlan1"
    
    # 시각화 시스템 초기화
    print(f"\n📹 시각화 시스템 초기화 중...")
    visualizer = MultiAgentVisualizer()
    
    # Agent 생성
    print(f"\n🎮 에이전트 생성 중...")
    
    config1 = AgentConfig(agent_id="agent_1", scene=scene)
    agent1 = AI2THORAgent(config1)
    agent1.initialize()
    print("✓ Agent 1 초기화 완료")
    
    config2 = AgentConfig(agent_id="agent_2", scene=scene)
    agent2 = AI2THORAgent(config2)
    agent2.initialize()
    print("✓ Agent 2 초기화 완료")
    
    agents = {
        "agent_1": agent1,
        "agent_2": agent2
    }
    
    # Scene 정보 가져오기
    print(f"\n{'=' * 60}")
    print("Scene 정보 분석")
    print(f"{'=' * 60}")
    
    reachable_event = agent1.controller.step("GetReachablePositions")
    reachable_positions = reachable_event.metadata['actionReturn']
    print(f"이동 가능한 위치: {len(reachable_positions)}개")
    
    # 목표 객체 위치 미리 파악
    tomato_obj = find_object_location(agent1.controller, 'Tomato')
    lightswitch_obj = find_object_location(agent1.controller, 'LightSwitch')
    
    exclude_positions = []
    if tomato_obj:
        exclude_positions.append(tomato_obj['position'])
    if lightswitch_obj:
        exclude_positions.append(lightswitch_obj['position'])
    
    print(f"제외 위치: {len(exclude_positions)}개 (목표 객체 주변)")

    # 랜덤 위치로 이동
    print(f"\n📍 에이전트 랜덤 위치 설정...")
    
    # Agent 1 위치
    pos1 = get_random_position(reachable_positions, exclude_positions=exclude_positions)
    agent1.controller.step(
        action='Teleport',
        position=pos1,
        rotation={'x': 0, 'y': random.randint(0, 3) * 90, 'z': 0}
    )
    print(f"[agent_1] 위치: ({pos1['x']:.2f}, {pos1['z']:.2f})")
    
    # Agent 2 위치 (Agent 1과 충분히 떨어진 곳)
    pos2 = get_random_position(
        reachable_positions, 
        exclude_positions=exclude_positions,
        other_agent_pos=pos1
    )
    agent2.controller.step(
        action='Teleport',
        position=pos2,
        rotation={'x': 0, 'y': random.randint(0, 3) * 90, 'z': 0}
    )
    
    distance_between = math.sqrt((pos1['x'] - pos2['x'])**2 + (pos1['z'] - pos2['z'])**2)
    print(f"[agent_2] 위치: ({pos2['x']:.2f}, {pos2['z']:.2f})")
    print(f"📏 에이전트 간 거리: {distance_between:.2f}m")
    visualizer.initialize_top_view_camera(scene, agent_count=2)
    visualizer.setup_video_writers(agents)
    
    # 코디네이터 초기화
    coordinator = AgentCoordinator()
    coordinator.update_position("agent_1", pos1['x'], pos1['z'])
    coordinator.update_position("agent_2", pos2['x'], pos2['z'])
    
    # 프레임 캡처 함수
    frame_count = [0]  # mutable 객체로 사용
    frame_lock = threading.Lock()
    
    def capture_all_frames():
        """모든 카메라에서 프레임 캡처 (thread-safe)"""
        with frame_lock:
            visualizer.capture_frame(agents, frame_count[0])
            frame_count[0] += 1
    
    print(f"\n🎬 태스크 시작...")
    
    # 초기 프레임
    capture_all_frames()
    
    # 병렬 실행
    results = {}
    threads = []
    
    # Agent 1: 토마토 찾기
    t1 = threading.Thread(
        target=agent_task,
        args=(agent1, 'agent_1', 'Tomato', 'pickup', coordinator, capture_all_frames, results)
    )
    threads.append(t1)
    
    # Agent 2: 라이트 스위치 찾기
    t2 = threading.Thread(
        target=agent_task,
        args=(agent2, 'agent_2', 'LightSwitch', 'toggle', coordinator, capture_all_frames, results)
    )
    threads.append(t2)
    
    # 스레드 시작
    for t in threads:
        t.start()
    
    # 모든 스레드 완료 대기
    for t in threads:
        t.join()
    
    print(f"\n{'=' * 60}")
    print("📊 작업 결과")
    print(f"{'=' * 60}")
    print(f"[agent_1] 토마토 집기: {'✓ 성공' if results.get('agent_1', False) else '❌ 실패'}")
    print(f"[agent_2] 불 켜기: {'✓ 성공' if results.get('agent_2', False) else '❌ 실패'}")
    
    # 마무리 프레임 (작업 완료 후 정지 상태 유지)
    print(f"\n📹 마무리 프레임 녹화...")
    for _ in range(10):
        capture_all_frames()
        time.sleep(0.1)
    
    print(f"\n✓ 총 {frame_count[0]} 프레임 녹화 완료")
    
    # 정리
    print(f"\n🔄 시스템 종료 중...")
    visualizer.close()
    agent1.controller.stop()
    agent2.controller.stop()
    print("✓ 모든 시스템 종료 완료")
    
    # 결과 파일 확인
    print(f"\n{'=' * 60}")
    print("📹 생성된 비디오 파일")
    print(f"{'=' * 60}")
    
    video_files = []
    for filename in os.listdir('output_videos'):
        if filename.endswith('.mp4'):
            filepath = os.path.join('output_videos', filename)
            size = os.path.getsize(filepath)
            size_kb = size / 1024
            video_files.append((filename, size_kb))
    
    video_files.sort(reverse=True)
    for filename, size_kb in video_files[:5]:
        print(f"✓ {filename} ({size_kb:.1f} KB)")
    
    print(f"\n✅ 데모 완료!")


if __name__ == "__main__":
    main()
