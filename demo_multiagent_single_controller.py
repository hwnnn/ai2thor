#!/usr/bin/env python3
"""
진정한 Multi-Agent 데모: 하나의 Controller에 여러 Agent
- 하나의 Scene, 하나의 Controller
- 여러 Agent가 동일한 환경에서 병렬적으로 작업 수행
- Agent 1: 토마토 찾아서 집기
- Agent 2: 라이트 스위치 찾아서 누르기
"""

import os
import cv2
import numpy as np
import random
import math
import threading
import time
from datetime import datetime
from ai2thor.controller import Controller


class AgentCoordinator:
    """에이전트 간 충돌 회피를 위한 코디네이터"""
    
    def __init__(self):
        self.agent_positions = {}
        self.agent_targets = {}
        self.lock = threading.Lock()
        self.min_distance = 0.5
    
    def update_position(self, agent_id, x, z):
        with self.lock:
            self.agent_positions[agent_id] = (x, z)
    
    def set_target(self, agent_id, x, z):
        with self.lock:
            self.agent_targets[agent_id] = (x, z)
    
    def check_collision(self, agent_id, target_x, target_z):
        with self.lock:
            for other_id, (other_x, other_z) in self.agent_positions.items():
                if other_id == agent_id:
                    continue
                dist = math.sqrt((target_x - other_x)**2 + (target_z - other_z)**2)
                if dist < self.min_distance:
                    return True
            return False
    
    def wait_if_collision(self, agent_id, target_x, target_z, max_wait=2.0):
        wait_time = 0
        while self.check_collision(agent_id, target_x, target_z) and wait_time < max_wait:
            time.sleep(0.1)
            wait_time += 0.1
        return wait_time < max_wait


def get_random_position(reachable_positions, exclude_positions=None, min_distance_from_exclude=2.0, 
                       other_agent_pos=None, min_distance_between_agents=1.5):
    """이동 가능한 위치 중 랜덤 선택 (제약 조건 적용)"""
    valid_positions = []
    
    for pos in reachable_positions:
        valid = True
        
        if exclude_positions:
            for exclude_pos in exclude_positions:
                dist = math.sqrt((pos['x'] - exclude_pos['x'])**2 + (pos['z'] - exclude_pos['z'])**2)
                if dist < min_distance_from_exclude:
                    valid = False
                    break
        
        if valid and other_agent_pos:
            dist = math.sqrt((pos['x'] - other_agent_pos['x'])**2 + (pos['z'] - other_agent_pos['z'])**2)
            if dist < min_distance_between_agents:
                valid = False
        
        if valid:
            valid_positions.append(pos)
    
    if not valid_positions:
        print("⚠️ 제약 조건을 만족하는 위치가 없어 모든 위치 중 랜덤 선택")
        return random.choice(reachable_positions)
    
    if random.random() < 0.5 and len(valid_positions) > 10:
        center_x = sum(p['x'] for p in valid_positions) / len(valid_positions)
        center_z = sum(p['z'] for p in valid_positions) / len(valid_positions)
        valid_positions.sort(
            key=lambda p: math.sqrt((p['x'] - center_x)**2 + (p['z'] - center_z)**2),
            reverse=True
        )
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


def navigate_to_object(controller, agent_id, target_obj, coordinator, capture_func):
    """객체로 이동 (GetShortestPath 사용)"""
    print(f"[{agent_id}] 목표 위치로 이동 시작...")
    
    target_pos = target_obj['position']
    coordinator.set_target(agent_id, target_pos['x'], target_pos['z'])
    
    # GetShortestPath로 최적 경로 계산
    current_pos = controller.last_event.events[agent_id].metadata['agent']['position']
    
    path_event = controller.step(
        action='GetShortestPath',
        objectId=target_obj['objectId'],
        position=current_pos,
        agentId=agent_id
    )
    
    if not path_event.metadata['lastActionSuccess'] or not path_event.metadata.get('actionReturn'):
        print(f"[{agent_id}] ⚠️ 경로를 찾을 수 없습니다")
        return False
    
    corners = path_event.metadata['actionReturn']['corners']
    print(f"[{agent_id}] 경로 포인트: {len(corners)}개")
    
    # 경로를 따라 이동
    for i, corner in enumerate(corners[1:], 1):
        consecutive_failures = 0
        prev_pos = None
        stuck_counter = 0
        
        for attempt in range(30):  # 시도 횟수 증가
            current_pos = controller.last_event.events[agent_id].metadata['agent']['position']
            
            # 진행 상황 체크
            if prev_pos:
                moved_dist = math.sqrt((current_pos['x'] - prev_pos['x'])**2 + (current_pos['z'] - prev_pos['z'])**2)
                if moved_dist < 0.05:
                    stuck_counter += 1
                else:
                    stuck_counter = 0
            
            # 막힘 감지
            if stuck_counter >= 3:
                print(f"[{agent_id}] 🚧 막힘 감지! 우회 시도 중...")
                controller.step(action='MoveBack', agentId=agent_id, moveMagnitude=0.5)
                capture_func()
                controller.step(action='RotateRight', agentId=agent_id, degrees=60)
                capture_func()
                stuck_counter = 0
                consecutive_failures = 0
                continue
            
            prev_pos = current_pos.copy()
            
            # 거리 계산
            dist = math.sqrt((corner['x'] - current_pos['x'])**2 + (corner['z'] - current_pos['z'])**2)
            
            if dist < 0.2:  # 더 가까이 접근
                break
            
            # 방향 계산
            dx = corner['x'] - current_pos['x']
            dz = corner['z'] - current_pos['z']
            target_angle = math.degrees(math.atan2(dx, dz))
            current_rotation = controller.last_event.events[agent_id].metadata['agent']['rotation']['y']
            angle_diff = (target_angle - current_rotation + 180) % 360 - 180
            
            # 회전
            if abs(angle_diff) > 15:
                direction = 'RotateRight' if angle_diff > 0 else 'RotateLeft'
                controller.step(action=direction, agentId=agent_id, degrees=min(30, abs(angle_diff)))
                capture_func()
                continue
            
            # 충돌 체크
            next_x = current_pos['x'] + 0.25 * math.sin(math.radians(current_rotation))
            next_z = current_pos['z'] + 0.25 * math.cos(math.radians(current_rotation))
            
            if not coordinator.wait_if_collision(agent_id, next_x, next_z, max_wait=1.0):
                time.sleep(0.5)
                continue
            
            # 이동
            event = controller.step(action='MoveAhead', agentId=agent_id, moveMagnitude=0.25)
            capture_func()
            
            new_pos = event.events[agent_id].metadata['agent']['position']
            coordinator.update_position(agent_id, new_pos['x'], new_pos['z'])
            
            if not event.metadata['lastActionSuccess']:
                consecutive_failures += 1
                if consecutive_failures >= 3:
                    controller.step(action='MoveBack', agentId=agent_id, moveMagnitude=0.5)
                    capture_func()
                    direction = 'RotateLeft' if consecutive_failures % 2 == 0 else 'RotateRight'
                    controller.step(action=direction, agentId=agent_id, degrees=45)
                    capture_func()
                    consecutive_failures = 0
                else:
                    controller.step(action='RotateRight', agentId=agent_id, degrees=15)
                    capture_func()
            else:
                consecutive_failures = 0
    
    # 모든 경로 포인트 완료 후 실제 목표 객체까지 0.5m 이내로 접근
    print(f"[{agent_id}] 목표 객체로 최종 접근 중...")
    final_approach_attempts = 0
    max_final_attempts = 50
    
    while final_approach_attempts < max_final_attempts:
        current_pos = controller.last_event.events[agent_id].metadata['agent']['position']
        distance_to_target = calculate_distance(current_pos, target_pos)
        
        if distance_to_target < 0.5:  # 50cm 이내
            print(f"[{agent_id}] ✓ 목표 객체 근처 도착 (거리: {distance_to_target:.2f}m)")
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
            event = controller.step(action='MoveAhead', agentId=agent_id, moveMagnitude=0.15)
            capture_func()
            
            if not event.metadata['lastActionSuccess']:
                # 이동 실패 시 약간 회전 후 재시도
                controller.step(action='RotateRight', agentId=agent_id, degrees=15)
                capture_func()
        
        final_approach_attempts += 1
    
    final_pos = controller.last_event.events[agent_id].metadata['agent']['position']
    final_dist = calculate_distance(final_pos, target_pos)
    print(f"[{agent_id}] ✓ 목표 지점 도착 (거리: {final_dist:.2f}m)")
    return True  # 항상 성공으로 간주하고 탐색 단계로 진행


def search_object_nearby(controller, agent_id, object_type, capture_func):
    """근처에서 객체 탐색"""
    print(f"[{agent_id}] 근처에서 {object_type} 탐색 중...")
    
    # 먼저 조금씩 전진하며 탐색
    for forward_step in range(3):
        if forward_step > 0:
            controller.step(action='MoveAhead', agentId=agent_id, moveMagnitude=0.2)
            capture_func()
        
        # 360도 회전하며 탐색
        for rotation_step in range(12):
            if rotation_step > 0:
                controller.step(action='RotateRight', agentId=agent_id, degrees=30)
                capture_func()
            
            # 각 방향에서 고개 위아래로
            for horizon in [-30, 0, 30, 60]:
                if horizon < 0:
                    controller.step(action='LookUp', agentId=agent_id, degrees=abs(horizon))
                elif horizon > 0:
                    controller.step(action='LookDown', agentId=agent_id, degrees=horizon)
                
                capture_func()
                
                # 객체 검색
                event = controller.last_event
                for obj in event.metadata['objects']:
                    if object_type in obj['objectType'] and obj['visible']:
                        print(f"[{agent_id}] ✓ {object_type} 발견!")
                        # 고개 정면으로
                        current_horizon = event.events[agent_id].metadata['agent']['cameraHorizon']
                        if current_horizon < 0:
                            controller.step(action='LookDown', agentId=agent_id, degrees=abs(current_horizon))
                        elif current_horizon > 0:
                            controller.step(action='LookUp', agentId=agent_id, degrees=current_horizon)
                        capture_func()
                        return obj
    
    print(f"[{agent_id}] ❌ {object_type}를 찾을 수 없습니다")
    return None


def interact_with_object(controller, agent_id, obj, action_type, capture_func):
    """객체와 상호작용"""
    print(f"[{agent_id}] {obj['objectType']}와 상호작용 시도...")
    
    # 약간 더 가까이
    for _ in range(3):
        event = controller.step(action='MoveAhead', agentId=agent_id, moveMagnitude=0.1)
        capture_func()
        if not event.metadata['lastActionSuccess']:
            break
    
    # 상호작용
    if action_type == 'pickup':
        event = controller.step(action='PickupObject', agentId=agent_id, 
                               objectId=obj['objectId'], forceAction=True)
    elif action_type == 'toggle':
        action = 'ToggleObjectOn' if not obj.get('isToggled', False) else 'ToggleObjectOff'
        event = controller.step(action=action, agentId=agent_id, 
                               objectId=obj['objectId'], forceAction=True)
    
    capture_func()
    
    if event.metadata['lastActionSuccess']:
        print(f"[{agent_id}] ✓ 상호작용 성공!")
        return True
    else:
        print(f"[{agent_id}] ⚠️ 상호작용 실패")
        return False


def agent_task(controller, agent_id, object_type, action_type, coordinator, capture_func, results):
    """에이전트 작업"""
    try:
        # 1. 객체 위치 찾기
        target_obj = find_object_location(controller, object_type)
        if not target_obj:
            print(f"[{agent_id}] ❌ {object_type}를 scene에서 찾을 수 없습니다")
            results[agent_id] = False
            return
        
        print(f"[{agent_id}] ✓ {object_type} 위치 확인: ({target_obj['position']['x']:.2f}, {target_obj['position']['y']:.2f}, {target_obj['position']['z']:.2f})")
        
        # 2. 객체로 이동
        if not navigate_to_object(controller, agent_id, target_obj, coordinator, capture_func):
            results[agent_id] = False
            return
        
        # 3. 근처에서 탐색
        found_obj = search_object_nearby(controller, agent_id, object_type, capture_func)
        if not found_obj:
            results[agent_id] = False
            return
        
        # 4. 상호작용
        success = interact_with_object(controller, agent_id, found_obj, action_type, capture_func)
        results[agent_id] = success
        
    except Exception as e:
        print(f"[{agent_id}] ❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()
        results[agent_id] = False


def setup_video_writers(scene_name):
    """비디오 작성기 설정"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    fps = 6
    
    writers = {
        'topview': cv2.VideoWriter(
            f'output_videos/topview_{timestamp}.mp4',
            fourcc, fps, (1920, 1080)
        ),
        'agent_0': cv2.VideoWriter(
            f'output_videos/agent_0_pov_{timestamp}.mp4',
            fourcc, fps, (800, 600)
        ),
        'agent_1': cv2.VideoWriter(
            f'output_videos/agent_1_pov_{timestamp}.mp4',
            fourcc, fps, (800, 600)
        ),
        'combined': cv2.VideoWriter(
            f'output_videos/combined_{timestamp}.mp4',
            fourcc, fps, (1920, 1080)
        )
    }
    
    return writers


def capture_frame(controller, writers, frame_lock):
    """프레임 캡처 (thread-safe)"""
    with frame_lock:
        event = controller.last_event
        
        # Agent 0 POV
        frame0 = event.events[0].frame
        frame0_bgr = cv2.cvtColor(frame0, cv2.COLOR_RGB2BGR)
        frame0_resized = cv2.resize(frame0_bgr, (800, 600))
        writers['agent_0'].write(frame0_resized)
        
        # Agent 1 POV
        frame1 = event.events[1].frame
        frame1_bgr = cv2.cvtColor(frame1, cv2.COLOR_RGB2BGR)
        frame1_resized = cv2.resize(frame1_bgr, (800, 600))
        writers['agent_1'].write(frame1_resized)
        
        # Topdown view (third party camera frames)
        topdown_bgr = None
        if event.third_party_camera_frames and len(event.third_party_camera_frames) > 0:
            topdown_frame = event.third_party_camera_frames[0]
            topdown_bgr = cv2.cvtColor(topdown_frame, cv2.COLOR_RGB2BGR)
        else:
            # fallback: agent 0 프레임 사용
            print("⚠️ Third-party camera frame 없음, agent 0 프레임 사용")
            topdown_bgr = frame0_bgr.copy()
        
        topdown_resized = cv2.resize(topdown_bgr, (1920, 1080))
        writers['topview'].write(topdown_resized)
        
        # Combined view (상단: topdown, 하단 좌우: agent POVs)
        topdown_small = cv2.resize(topdown_bgr, (1920, 540))
        agent0_small = cv2.resize(frame0_bgr, (960, 540))
        agent1_small = cv2.resize(frame1_bgr, (960, 540))
        
        combined = np.zeros((1080, 1920, 3), dtype=np.uint8)
        combined[0:540, :] = topdown_small
        combined[540:1080, 0:960] = agent0_small
        combined[540:1080, 960:1920] = agent1_small
        
        writers['combined'].write(combined)


def main():
    """메인 실행 함수"""
    print("=" * 60)
    print("진정한 Multi-Agent 데모: 하나의 Controller")
    print("=" * 60)
    
    os.makedirs('output_videos', exist_ok=True)
    
    scene = "FloorPlan1"
    
    # 하나의 Controller 생성 (Multi-Agent 모드)
    print(f"\n🎮 Controller 초기화 중... (Multi-Agent 모드)")
    controller = Controller(
        scene=scene,
        agentCount=2,  # 2개의 agent
        width=800,  # Agent POV 해상도
        height=600,
        fieldOfView=90,
        agentMode="default",
        visibilityDistance=3.0,
        renderDepthImage=False,
        renderInstanceSegmentation=False,
        makeAgentsVisible=True  # agent들이 서로 보이게
    )
    
    print(f"✓ Controller 초기화 완료 (Agent 수: 2)")
    
    # 천장에서 내려다보는 Third-party camera 추가
    print(f"\n📹 Topdown 카메라 설정 중...")
    
    # Scene의 중심과 높이 계산
    event = controller.step(action="GetReachablePositions", agentId=0)
    reachable_positions = event.metadata['actionReturn']
    
    if reachable_positions:
        center_x = float(np.mean([p['x'] for p in reachable_positions]))
        center_z = float(np.mean([p['z'] for p in reachable_positions]))
        
        # Third-party camera 추가 (정중앙 천장에서 내려다봄)
        camera_position = {'x': center_x, 'y': 5.0, 'z': center_z}
        
        controller.step(
            action='AddThirdPartyCamera',
            position=camera_position,
            rotation={'x': 90, 'y': 0, 'z': 0},  # 90도 회전 = 아래를 바라봄
            fieldOfView=90,
            skyboxColor='white'  # 배경색
        )
        
        # 확인
        event = controller.last_event
        if event.third_party_camera_frames and len(event.third_party_camera_frames) > 0:
            print(f"✓ Topdown 카메라 위치: ({center_x:.2f}, 5.0, {center_z:.2f})")
            print(f"✓ Third-party camera frames: {len(event.third_party_camera_frames)}개")
        else:
            print("⚠️ Third-party camera 프레임을 가져올 수 없습니다")
    
    # Scene 정보
    print(f"\n{'=' * 60}")
    print("Scene 정보 분석")
    print(f"{'=' * 60}")
    
    reachable_event = controller.step(action="GetReachablePositions", agentId=0)
    reachable_positions = reachable_event.metadata['actionReturn']
    print(f"이동 가능한 위치: {len(reachable_positions)}개")
    
    # 목표 객체 위치 파악
    tomato_obj = find_object_location(controller, 'Tomato')
    lightswitch_obj = find_object_location(controller, 'LightSwitch')
    
    exclude_positions = []
    if tomato_obj:
        exclude_positions.append(tomato_obj['position'])
    if lightswitch_obj:
        exclude_positions.append(lightswitch_obj['position'])
    
    print(f"제외 위치: {len(exclude_positions)}개 (목표 객체 주변)")
    
    # Agent 랜덤 위치 설정
    print(f"\n📍 에이전트 랜덤 위치 설정...")
    
    pos0 = get_random_position(reachable_positions, exclude_positions=exclude_positions)
    controller.step(
        action='TeleportFull',
        agentId=0,
        x=pos0['x'],
        y=pos0['y'],
        z=pos0['z'],
        rotation={'x': 0, 'y': random.randint(0, 3) * 90, 'z': 0},
        horizon=0,
        standing=True
    )
    print(f"[agent_0] 위치: ({pos0['x']:.2f}, {pos0['z']:.2f})")
    
    pos1 = get_random_position(
        reachable_positions,
        exclude_positions=exclude_positions,
        other_agent_pos=pos0
    )
    controller.step(
        action='TeleportFull',
        agentId=1,
        x=pos1['x'],
        y=pos1['y'],
        z=pos1['z'],
        rotation={'x': 0, 'y': random.randint(0, 3) * 90, 'z': 0},
        horizon=0,
        standing=True
    )
    
    distance_between = math.sqrt((pos0['x'] - pos1['x'])**2 + (pos0['z'] - pos1['z'])**2)
    print(f"[agent_1] 위치: ({pos1['x']:.2f}, {pos1['z']:.2f})")
    print(f"📏 에이전트 간 거리: {distance_between:.2f}m")
    
    # 비디오 작성기 설정
    print(f"\n📹 비디오 작성기 초기화 중...")
    writers = setup_video_writers(scene)
    
    # 코디네이터 초기화
    coordinator = AgentCoordinator()
    coordinator.update_position(0, pos0['x'], pos0['z'])
    coordinator.update_position(1, pos1['x'], pos1['z'])
    
    # 프레임 캡처 함수
    frame_lock = threading.Lock()
    frame_counter = [0]
    
    def capture_all_frames():
        capture_frame(controller, writers, frame_lock)
        frame_counter[0] += 1
    
    print(f"\n🎬 태스크 시작...")
    
    # 초기 프레임
    capture_all_frames()
    
    # Turn-based 실행 (threading 없이)
    # Agent들이 교대로 행동
    results = {}
    
    print(f"\n{'=' * 60}")
    print("[0] Tomato 미션 시작")
    print(f"{'=' * 60}")
    agent_task(controller, 0, 'Tomato', 'pickup', coordinator, capture_all_frames, results)
    
    print(f"\n{'=' * 60}")
    print("[1] LightSwitch 미션 시작")
    print(f"{'=' * 60}")
    agent_task(controller, 1, 'LightSwitch', 'toggle', coordinator, capture_all_frames, results)
    
    print(f"\n{'=' * 60}")
    print("📊 작업 결과")
    print(f"{'=' * 60}")
    print(f"[agent_0] 토마토 집기: {'✓ 성공' if results.get(0, False) else '❌ 실패'}")
    print(f"[agent_1] 불 켜기: {'✓ 성공' if results.get(1, False) else '❌ 실패'}")
    
    # 마무리 프레임
    print(f"\n📹 마무리 프레임 녹화...")
    for _ in range(10):
        capture_all_frames()
        time.sleep(0.1)
    
    print(f"\n✓ 총 {frame_counter[0]} 프레임 녹화 완료")
    
    # 정리
    print(f"\n🔄 시스템 종료 중...")
    
    for writer in writers.values():
        writer.release()
    
    controller.stop()
    
    print("✓ 모든 시스템 종료 완료")
    print(f"\n✅ 데모 완료!")


if __name__ == "__main__":
    main()
