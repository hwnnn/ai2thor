#!/usr/bin/env python3
"""
Multi-Agent 데모 (Agent POV만 저장)
- Controller 1개, agentCount=2
- Agent 0: 토마토 자르기
- Agent 1: 불 켜기
- 각 agent의 POV 영상 저장
- 이동 동선 최적화 + 좌우 우회 로직
"""

import os
import cv2
import numpy as np
import random
import math
import threading
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


def try_move_sideways(controller, agent_id):
    """좌우로 이동 가능한지 확인하고 우회"""
    # 왼쪽 시도
    left_event = controller.step(action='MoveLeft', agentId=agent_id, moveMagnitude=0.25)
    if left_event.metadata['lastActionSuccess']:
        print(f"[agent_{agent_id}] ← 왼쪽으로 우회 성공")
        return True
    
    # 오른쪽 시도
    right_event = controller.step(action='MoveRight', agentId=agent_id, moveMagnitude=0.25)
    if right_event.metadata['lastActionSuccess']:
        print(f"[agent_{agent_id}] → 오른쪽으로 우회 성공")
        return True
    
    return False


def navigate_to_distance(controller, agent_id, target_pos, target_distance=0.3):
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
            controller.step(action=direction, agentId=agent_id, degrees=min(30, abs(angle_diff)))
            continue
        
        # 이동
        move_magnitude = min(0.25, distance - target_distance + 0.1)
        event = controller.step(action='MoveAhead', agentId=agent_id, moveMagnitude=move_magnitude)
        
        if not event.metadata['lastActionSuccess']:
            consecutive_failures += 1
            if consecutive_failures >= 3:
                print(f"[agent_{agent_id}] 🚧 막힘 감지, 좌우 우회 시도...")
                
                # 좌우로 우회 시도
                if try_move_sideways(controller, agent_id):
                    consecutive_failures = 0
                    continue
                
                # 좌우도 막혔으면 백스텝 + 회전
                print(f"[agent_{agent_id}] ⚠️ 좌우 모두 막힘, 백스텝 후 회전")
                controller.step(action='MoveBack', agentId=agent_id, moveMagnitude=0.3)
                controller.step(action='RotateRight', agentId=agent_id, degrees=45)
                consecutive_failures = 0
        else:
            consecutive_failures = 0
    
    final_pos = controller.last_event.events[agent_id].metadata['agent']['position']
    final_dist = calculate_distance(final_pos, target_pos)
    print(f"[agent_{agent_id}] ✓ 이동 완료 (거리: {final_dist:.2f}m)")
    return True


def search_and_interact(controller, agent_id, object_type, action_type):
    """상하좌우 회전하며 객체 탐색 및 상호작용"""
    print(f"[agent_{agent_id}] {object_type} 탐색 중 (상하좌우 회전)...")
    
    # 상하 시야각 조정
    for horizon_angle in [0, 30, -30, 15, -15]:
        # 시야각 조정
        if horizon_angle > 0:
            controller.step(action='LookUp', agentId=agent_id, degrees=abs(horizon_angle))
        elif horizon_angle < 0:
            controller.step(action='LookDown', agentId=agent_id, degrees=abs(horizon_angle))
        
        # 좌우 360도 회전
        for rotation_step in range(12):
            if rotation_step > 0:
                controller.step(action='RotateRight', agentId=agent_id, degrees=30)
            
            # 객체 확인
            event = controller.last_event
            for obj in event.events[agent_id].metadata['objects']:
                if obj['objectType'] == object_type and obj['visible']:
                    print(f"[agent_{agent_id}] ✓ {object_type} 발견!")
                    
                    # 시야각 원복
                    if horizon_angle < 0:
                        controller.step(action='LookDown', agentId=agent_id, degrees=abs(horizon_angle))
                    elif horizon_angle > 0:
                        controller.step(action='LookUp', agentId=agent_id, degrees=abs(horizon_angle))
                    
                    # 상호작용 시도
                    return try_interact(controller, agent_id, obj, action_type)
        
        # 시야각 원복
        if horizon_angle < 0:
            controller.step(action='LookDown', agentId=agent_id, degrees=abs(horizon_angle))
        elif horizon_angle > 0:
            controller.step(action='LookUp', agentId=agent_id, degrees=abs(horizon_angle))
    
    print(f"[agent_{agent_id}] ✗ {object_type}를 찾을 수 없습니다")
    return False


def try_interact(controller, agent_id, obj, action_type):
    """객체와 상호작용 시도"""
    print(f"[agent_{agent_id}] {obj['objectType']}와 상호작용 시도...")
    
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
        
        if event.metadata['lastActionSuccess']:
            print(f"[agent_{agent_id}] ✓ 상호작용 성공!")
            return True
        else:
            error_msg = event.metadata.get('errorMessage', 'Unknown')
            print(f"[agent_{agent_id}] ⚠️ 실패 ({attempt+1}/{max_attempts}): {error_msg}")
    
    return False


def agent_task(controller, agent_id, target_object_type, action_type, lock, video_writer):
    """에이전트 태스크 실행 (병렬)"""
    print(f"\n{'='*60}")
    print(f"[agent_{agent_id}] {target_object_type} 미션 시작")
    print(f"{'='*60}")
    
    try:
        # 1. 객체 위치 확인
        with lock:
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
        
        # 2. 목표 위치로 이동
        with lock:
            success = navigate_to_distance(controller, agent_id, target_obj['position'], target_distance=0.3)
        
        if not success:
            print(f"[agent_{agent_id}] ✗ 이동 실패")
            return False
        
        # 3. 객체 탐색 및 상호작용
        with lock:
            result = search_and_interact(controller, agent_id, target_object_type, action_type)
        
        return result
    
    except Exception as e:
        print(f"[agent_{agent_id}] ✗ 오류 발생: {e}")
        return False


def capture_video_frames(controller, agent_id, video_writer, lock, stop_event):
    """비디오 프레임 캡처 (별도 스레드)"""
    frame_count = 0
    
    while not stop_event.is_set():
        try:
            with lock:
                event = controller.last_event
                if event and len(event.events) > agent_id:
                    frame = event.events[agent_id].frame
                    if frame is not None and frame.size > 0:
                        # BGR 변환 및 저장
                        frame_bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
                        frame_resized = cv2.resize(frame_bgr, (800, 600))
                        video_writer.write(frame_resized)
                        frame_count += 1
        except Exception as e:
            print(f"[capture_{agent_id}] 프레임 캡처 오류: {e}")
        
        # 짧은 대기 (너무 빠르게 캡처하지 않도록)
        stop_event.wait(0.1)
    
    print(f"[capture_{agent_id}] 총 {frame_count} 프레임 캡처 완료")


def main():
    print("="*60)
    print("Multi-Agent 병렬 처리 데모")
    print("="*60)
    
    # 출력 디렉토리
    output_dir = 'output_videos'
    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # 비디오 작성기
    fps = 10
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    
    video_writers = {
        'agent_0': cv2.VideoWriter(
            os.path.join(output_dir, f'agent_0_pov_{timestamp}.mp4'),
            fourcc, fps, (800, 600)
        ),
        'agent_1': cv2.VideoWriter(
            os.path.join(output_dir, f'agent_1_pov_{timestamp}.mp4'),
            fourcc, fps, (800, 600)
        )
    }
    
    # Thread-safe lock
    controller_lock = threading.Lock()
    stop_event = threading.Event()
    
    try:
        # Controller 초기화 (2 agents)
        print("\n🎮 Controller 초기화 중... (2 agents)")
        controller = Controller(
            scene="FloorPlan1",
            agentCount=2,
            width=800,
            height=600,
            fieldOfView=90,
            visibilityDistance=10.0,
            makeAgentsVisible=False
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
        
        # 목표 객체 위치
        event = controller.last_event
        all_objects = event.events[0].metadata['objects']
        target_objects = []
        for obj in all_objects:
            if obj['objectType'] in ['Tomato', 'LightSwitch']:
                target_objects.append(obj)
        
        exclude_positions = [obj['position'] for obj in target_objects]
        
        # Agent 0, 1 랜덤 위치 설정
        print("\n📍 Agent 0, 1 랜덤 위치 설정...")
        pos_0 = get_random_position(reachable_positions, exclude_positions)
        pos_1 = get_random_position(reachable_positions, exclude_positions, other_agent_pos=pos_0)
        
        controller.step(action='TeleportFull', agentId=0, **pos_0, rotation={'x': 0, 'y': 0, 'z': 0}, horizon=0, standing=True)
        controller.step(action='TeleportFull', agentId=1, **pos_1, rotation={'x': 0, 'y': 0, 'z': 0}, horizon=0, standing=True)
        
        print(f"[agent_0] 위치: ({pos_0['x']:.2f}, {pos_0['z']:.2f})")
        print(f"[agent_1] 위치: ({pos_1['x']:.2f}, {pos_1['z']:.2f})")
        print(f"📏 에이전트 간 거리: {calculate_distance(pos_0, pos_1):.2f}m")
        
        # 비디오 캡처 스레드 시작
        print("\n📹 비디오 캡처 시작...")
        capture_thread_0 = threading.Thread(
            target=capture_video_frames,
            args=(controller, 0, video_writers['agent_0'], controller_lock, stop_event)
        )
        capture_thread_1 = threading.Thread(
            target=capture_video_frames,
            args=(controller, 1, video_writers['agent_1'], controller_lock, stop_event)
        )
        
        capture_thread_0.start()
        capture_thread_1.start()
        
        print("\n🎬 태스크 시작 (순차 실행 - Controller는 thread-safe하지 않음)...")
        
        # Agent 0: 토마토 자르기
        success_0 = agent_task(controller, 0, 'Tomato', 'slice', controller_lock, video_writers['agent_0'])
        
        # Agent 1: 불 켜기
        success_1 = agent_task(controller, 1, 'LightSwitch', 'toggle', controller_lock, video_writers['agent_1'])
        
        # 결과
        print(f"\n{'='*60}")
        print("📊 작업 결과")
        print(f"{'='*60}")
        print(f"[agent_0] 토마토 자르기: {'✓ 성공' if success_0 else '✗ 실패'}")
        print(f"[agent_1] 불 켜기: {'✓ 성공' if success_1 else '✗ 실패'}")
        
        # 비디오 캡처 종료
        print("\n📹 비디오 캡처 종료 중...")
        stop_event.set()
        capture_thread_0.join(timeout=5)
        capture_thread_1.join(timeout=5)
        
        print(f"\n✓ 비디오 저장 완료")
        print(f"  - Agent 0 POV: agent_0_pov_{timestamp}.mp4")
        print(f"  - Agent 1 POV: agent_1_pov_{timestamp}.mp4")
        
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
