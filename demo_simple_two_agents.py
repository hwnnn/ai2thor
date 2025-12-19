#!/usr/bin/env python3
"""
간단한 두 에이전트 데모: 토마토 자르기 + 불 켜기
- Agent 1: 토마토를 찾아서 상호작용
- Agent 2: 불 켜는 버튼(LightSwitch) 찾아서 누르기
- 각 agent의 POV 영상 + Topdown view 영상 저장
- 개선된 탐색 로직: 이동 -> 고개 상하좌우 움직임 -> 객체 발견 or 재이동
- 부드러운 영상: 모든 동작마다 프레임 캡처
"""

import os
import cv2
import numpy as np
from datetime import datetime
from ai2thor.controller import Controller


def get_scene_info(controller):
    """
    Scene의 정보를 가져오기
    - Scene 경계 (bounds)
    - 모든 객체 목록과 위치
    - 이동 가능한 위치들
    """
    event = controller.last_event
    
    # Scene 경계
    if 'sceneBounds' in event.metadata:
        bounds = event.metadata['sceneBounds']
        print(f"\n📐 Scene 경계:")
        print(f"  Center: ({bounds['center']['x']:.2f}, {bounds['center']['y']:.2f}, {bounds['center']['z']:.2f})")
        print(f"  Size: ({bounds['size']['x']:.2f}, {bounds['size']['y']:.2f}, {bounds['size']['z']:.2f})")
    
    # 이동 가능한 위치
    reachable_event = controller.step("GetReachablePositions")
    reachable_positions = reachable_event.metadata['actionReturn']
    if reachable_positions:
        x_coords = [p['x'] for p in reachable_positions]
        z_coords = [p['z'] for p in reachable_positions]
        print(f"\n🗺️  이동 가능 영역:")
        print(f"  X 범위: [{min(x_coords):.2f}, {max(x_coords):.2f}]")
        print(f"  Z 범위: [{min(z_coords):.2f}, {max(z_coords):.2f}]")
        print(f"  총 {len(reachable_positions)}개 위치")
    
    # 모든 객체 목록
    objects = event.metadata['objects']
    object_types = {}
    for obj in objects:
        obj_type = obj['objectType']
        if obj_type not in object_types:
            object_types[obj_type] = []
        object_types[obj_type].append({
            'id': obj['objectId'],
            'position': obj['position'],
            'visible': obj['visible']
        })
    
    print(f"\n📦 Scene 내 객체 종류: {len(object_types)}개")
    for obj_type, objs in sorted(object_types.items())[:10]:  # 처음 10개만 표시
        print(f"  {obj_type}: {len(objs)}개")
    
    return {
        'bounds': event.metadata.get('sceneBounds'),
        'reachable_positions': reachable_positions,
        'objects': object_types
    }


def find_object_in_scene(controller, object_type):
    """
    Scene 전체에서 특정 타입의 객체 찾기 (metadata 사용)
    
    Returns:
        객체 정보 또는 None
    """
    event = controller.last_event
    for obj in event.metadata['objects']:
        if object_type in obj['objectType']:
            return obj
    return None


def calculate_distance(pos1, pos2):
    """두 위치 사이의 거리 계산"""
    import math
    return math.sqrt(
        (pos1['x'] - pos2['x'])**2 +
        (pos1['z'] - pos2['z'])**2
    )


def navigate_to_object(controller, agent_id, target_obj, capture_func, max_steps=20):
    """
    객체 근처까지 이동 (경로 계획)
    
    Returns:
        성공 여부
    """
    target_pos = target_obj['position']
    print(f"[{agent_id}] 목표 위치로 이동: ({target_pos['x']:.2f}, {target_pos['z']:.2f})")
    
    for step in range(max_steps):
        # 현재 위치
        agent_pos = controller.last_event.metadata['agent']['position']
        distance = calculate_distance(agent_pos, target_pos)
        
        print(f"[{agent_id}] 현재 거리: {distance:.2f}m")
        
        # 충분히 가까우면 종료
        if distance < 1.5:
            print(f"[{agent_id}] ✓ 목표 근처 도착!")
            return True
        
        # 목표를 향해 회전
        # 목표 방향 계산
        import math
        dx = target_pos['x'] - agent_pos['x']
        dz = target_pos['z'] - agent_pos['z']
        target_angle = math.degrees(math.atan2(dx, dz))
        
        # 현재 방향
        current_rotation = controller.last_event.metadata['agent']['rotation']['y']
        
        # 각도 차이 계산
        angle_diff = target_angle - current_rotation
        
        # -180 ~ 180 범위로 정규화
        while angle_diff > 180:
            angle_diff -= 360
        while angle_diff < -180:
            angle_diff += 360
        
        # 회전
        if abs(angle_diff) > 15:
            if angle_diff > 0:
                controller.step('RotateRight', degrees=min(30, abs(angle_diff)))
            else:
                controller.step('RotateLeft', degrees=min(30, abs(angle_diff)))
            capture_func()
        
        # 앞으로 이동
        event = controller.step('MoveAhead', moveMagnitude=0.25)
        capture_func()
        
        if not event.metadata['lastActionSuccess']:
            # 이동 실패 시 장애물 우회
            print(f"[{agent_id}] 장애물 감지, 우회 중...")
            controller.step('RotateRight', degrees=45)
            capture_func()
            event = controller.step('MoveAhead', moveMagnitude=0.25)
            capture_func()
            if not event.metadata['lastActionSuccess']:
                controller.step('RotateLeft', degrees=90)
                capture_func()
                controller.step('MoveAhead', moveMagnitude=0.25)
                capture_func()
    
    print(f"[{agent_id}] ⚠️ 목표 근처 도달 실패")
    return False


def look_for_object_nearby(controller, agent_id, object_type, capture_func):
    """
    현재 위치에서 고개를 돌리며 객체 찾기 (근거리 정밀 탐색)
    
    Returns:
        객체 또는 None
    """
    print(f"[{agent_id}] 근처에서 {object_type} 정밀 탐색 중...")
    
    # 360도 회전하며 탐색
    for rotation_step in range(12):
        if rotation_step > 0:
            controller.step('RotateRight', degrees=30)
            capture_func()
        
        # 각 방향에서 위아래 탐색
        horizon_sequence = [-30, 0, 30, 0]
        
        for i, target_horizon in enumerate(horizon_sequence):
            if i > 0:
                prev_horizon = horizon_sequence[i-1]
                diff = target_horizon - prev_horizon
                
                if diff < 0:
                    controller.step(action='LookUp', degrees=abs(diff))
                elif diff > 0:
                    controller.step(action='LookDown', degrees=diff)
                
                capture_func()
            
            # 객체 검색
            event = controller.last_event
            for obj in event.metadata['objects']:
                if object_type in obj['objectType'] and obj['visible']:
                    print(f"[{agent_id}] ✓ {object_type} 시야 확보!")
                    return obj
    
    print(f"[{agent_id}] ⚠️ {object_type}를 시야에서 찾지 못함")
    return None


def interact_with_object(controller, agent_id, obj, action_type, capture_func):
    """
    객체와 상호작용 (객체가 시야에 있는 상태에서)
    
    Returns:
        성공 여부
    """
    print(f"[{agent_id}] 상호작용 시도...")
    
    # 상호작용
    if action_type == 'pickup':
        event = controller.step(action='PickupObject', objectId=obj['objectId'], forceAction=True)
    elif action_type == 'toggle':
        action = 'ToggleObjectOn' if not obj.get('isToggled', False) else 'ToggleObjectOff'
        event = controller.step(action=action, objectId=obj['objectId'], forceAction=True)
    else:
        print(f"[{agent_id}] ❌ 알 수 없는 액션: {action_type}")
        return False
    
    capture_func()
    
    if event.metadata['lastActionSuccess']:
        print(f"[{agent_id}] ✓ 상호작용 성공!")
        return True
    else:
        error_msg = event.metadata.get('errorMessage', 'Unknown error')
        print(f"[{agent_id}] ❌ 상호작용 실패: {error_msg}")
        return False


def main():
    """메인 실행 함수"""
    print("=" * 60)
    print("간단한 두 에이전트 데모: 토마토 + 불 켜기")
    print("=" * 60)
    
    # 출력 디렉토리
    os.makedirs('output_videos', exist_ok=True)
    os.makedirs('output_images', exist_ok=True)
    
    scene = "FloorPlan1"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    print(f"\n🎮 에이전트 1 초기화...")
    agent1 = Controller(
        agentMode="default",
        scene=scene,
        gridSize=0.25,
        width=800,
        height=600,
        fieldOfView=90
    )
    print("✓ Agent 1 초기화 완료")
    
    print(f"\n🎮 에이전트 2 초기화...")
    agent2 = Controller(
        agentMode="default",
        scene=scene,
        gridSize=0.25,
        width=800,
        height=600,
        fieldOfView=90
    )
    print("✓ Agent 2 초기화 완료")
    
    # Scene 정보 가져오기
    print(f"\n{'=' * 60}")
    print("Scene 정보 분석")
    print(f"{'=' * 60}")
    scene_info = get_scene_info(agent1)
    
    print(f"\n📹 Topdown view 카메라 초기화...")
    topview = Controller(
        scene=scene,
        width=1920,
        height=1080,
        fieldOfView=90,
        agentMode='default'
    )
    
    # 탑뷰 위치 설정 - scene_info를 기반으로 자동 계산
    if scene_info['bounds']:
        center = scene_info['bounds']['center']
        size = scene_info['bounds']['size']
        topview_x = center['x']
        topview_z = center['z']
        topview_y = center['y'] + size['y'] / 2 + 1.0  # 천장 위
    else:
        # bounds가 없으면 수동 설정
        topview_x = 0.0
        topview_y = 3.5
        topview_z = 0.0
    
    topview.step(
        action='Teleport',
        position=dict(x=topview_x, y=topview_y, z=topview_z),
        rotation=dict(x=90, y=0, z=0),  # x=90: 완전히 아래를 바라봄
        horizon=0,
        standing=True
    )
    print(f"✓ Topdown view 위치: ({topview_x:.2f}, {topview_y:.2f}, {topview_z:.2f})")
    print(f"  카메라 각도: rotation=(90, 0, 0) - 아래를 바라봄")
    
    # 비디오 작성기 설정
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    
    topview_video = cv2.VideoWriter(
        f'output_videos/topview_{timestamp}.mp4',
        fourcc, 10, (1920, 1080)
    )
    agent1_video = cv2.VideoWriter(
        f'output_videos/agent_1_pov_{timestamp}.mp4',
        fourcc, 10, (800, 600)
    )
    agent2_video = cv2.VideoWriter(
        f'output_videos/agent_2_pov_{timestamp}.mp4',
        fourcc, 10, (800, 600)
    )
    
    print(f"\n✓ 비디오 작성기 설정 완료")
    
    # 에이전트 위치 설정 - 랜덤하게
    print(f"\n📍 에이전트 위치 설정 (랜덤)...")
    
    # 이동 가능한 위치 가져오기
    reachable_event = agent1.step("GetReachablePositions")
    reachable_positions = reachable_event.metadata['actionReturn']
    
    import random
    
    # Agent 1: 랜덤 위치
    agent1_pos = random.choice(reachable_positions)
    agent1.step(
        action='Teleport',
        position=agent1_pos,
        rotation={'x': 0, 'y': random.randint(0, 359), 'z': 0}
    )
    print(f"✓ Agent 1 위치: ({agent1_pos['x']:.2f}, {agent1_pos['y']:.2f}, {agent1_pos['z']:.2f})")
    
    # Agent 2: 랜덤 위치 (Agent 1과 다른 위치)
    agent2_pos = random.choice([p for p in reachable_positions 
                                if calculate_distance(p, agent1_pos) > 1.0])
    agent2.step(
        action='Teleport',
        position=agent2_pos,
        rotation={'x': 0, 'y': random.randint(0, 359), 'z': 0}
    )
    print(f"✓ Agent 2 위치: ({agent2_pos['x']:.2f}, {agent2_pos['y']:.2f}, {agent2_pos['z']:.2f})")
    
    # 프레임 수집 함수
    frame_count = 0
    
    def capture_all_frames():
        """모든 카메라에서 프레임 캡처 (자동으로 frame_count 증가)"""
        nonlocal frame_count
        
        # Topview
        event = topview.step("Pass")
        if event.frame is not None:
            top_frame = cv2.cvtColor(event.frame, cv2.COLOR_RGB2BGR)
            topview_video.write(top_frame)
        
        # Agent 1 POV
        event = agent1.step("Pass")
        if event.frame is not None:
            a1_frame = cv2.cvtColor(event.frame, cv2.COLOR_RGB2BGR)
            agent1_video.write(a1_frame)
        
        # Agent 2 POV
        event = agent2.step("Pass")
        if event.frame is not None:
            a2_frame = cv2.cvtColor(event.frame, cv2.COLOR_RGB2BGR)
            agent2_video.write(a2_frame)
        
        frame_count += 1
    
    print(f"\n🎬 태스크 시작...")
    
    try:
        # 초기 프레임
        capture_all_frames()
        
        # Agent 1: 토마토 찾기 (새로운 방식)
        print(f"\n{'=' * 60}")
        print("[agent_1] 🍅 토마토 미션")
        print(f"{'=' * 60}")
        
        # 1. Scene에서 토마토 위치 파악
        tomato = find_object_in_scene(agent1, 'Tomato')
        if tomato:
            print(f"[agent_1] ✓ 토마토 위치 파악: ({tomato['position']['x']:.2f}, {tomato['position']['z']:.2f})")
            
            # 2. 토마토 근처로 이동
            if navigate_to_object(agent1, 'agent_1', tomato, capture_all_frames):
                # 3. 토마토를 시야에서 찾기
                tomato_visible = look_for_object_nearby(agent1, 'agent_1', 'Tomato', capture_all_frames)
                
                if tomato_visible:
                    # 4. 상호작용
                    interact_with_object(agent1, 'agent_1', tomato_visible, 'pickup', capture_all_frames)
        else:
            print(f"[agent_1] ❌ 토마토가 scene에 없습니다")
        
        # Agent 2: 라이트 스위치 찾기 (새로운 방식)
        print(f"\n{'=' * 60}")
        print("[agent_2] 💡 라이트 스위치 미션")
        print(f"{'=' * 60}")
        
        # 1. Scene에서 라이트 스위치 위치 파악
        light_switch = find_object_in_scene(agent2, 'LightSwitch')
        if light_switch:
            print(f"[agent_2] ✓ 라이트 스위치 위치 파악: ({light_switch['position']['x']:.2f}, {light_switch['position']['z']:.2f})")
            
            # 2. 라이트 스위치 근처로 이동
            if navigate_to_object(agent2, 'agent_2', light_switch, capture_all_frames):
                # 3. 라이트 스위치를 시야에서 찾기
                switch_visible = look_for_object_nearby(agent2, 'agent_2', 'LightSwitch', capture_all_frames)
                
                if switch_visible:
                    # 4. 상호작용
                    interact_with_object(agent2, 'agent_2', switch_visible, 'toggle', capture_all_frames)
        else:
            print(f"[agent_2] ❌ 라이트 스위치가 scene에 없습니다")
        
        # 추가 프레임 (마무리 움직임 - 부드럽게)
        print(f"\n📹 마무리 프레임 녹화...")
        # Agent 1: 천천히 360도 회전
        for _ in range(12):
            agent1.step('RotateRight', degrees=30)
            capture_all_frames()
        
        # Agent 2: 천천히 360도 회전
        for _ in range(12):
            agent2.step('RotateLeft', degrees=30)
            capture_all_frames()
        
        # 두 에이전트가 동시에 고개 숙이고 올리기
        for _ in range(3):
            agent1.step('LookDown', degrees=20)
            agent2.step('LookDown', degrees=20)
            capture_all_frames()
        for _ in range(3):
            agent1.step('LookUp', degrees=20)
            agent2.step('LookUp', degrees=20)
            capture_all_frames()
        
        print(f"\n✓ 총 {frame_count} 프레임 녹화 완료")
        
    except Exception as e:
        print(f"\n❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # 정리
        print(f"\n🔄 시스템 종료 중...")
        topview_video.release()
        agent1_video.release()
        agent2_video.release()
        print("✓ 비디오 저장 완료")
        
        agent1.stop()
        agent2.stop()
        topview.stop()
        print("✓ 모든 컨트롤러 종료")
    
    # 결과 확인
    print(f"\n{'=' * 60}")
    print("📹 생성된 비디오 파일")
    print(f"{'=' * 60}")
    
    for filename in [f'topview_{timestamp}.mp4', f'agent_1_pov_{timestamp}.mp4', f'agent_2_pov_{timestamp}.mp4']:
        filepath = os.path.join('output_videos', filename)
        if os.path.exists(filepath):
            size_kb = os.path.getsize(filepath) / 1024
            print(f"✓ {filename} ({size_kb:.1f} KB)")
    
    print(f"\n✅ 데모 완료!")


if __name__ == "__main__":
    main()
