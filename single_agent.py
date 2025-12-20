#!/usr/bin/env python3
"""
Single Agent Task Executor (Third Party Camera)
- 단일 에이전트가 명령어 기반 작업을 수행
- 예: "토마토를 썰어서 냉장고에 넣어둬" → 토마토 찾기 → 자르기 → 냉장고 열기 → 넣기
- 초기 위치 무작위, 최적 경로 계산, 장애물 회피
- Agent POV + Third Party Camera 녹화
"""

import os
import cv2
import numpy as np
import random
import math
from datetime import datetime
from ai2thor.controller import Controller
from navigation_utils import navigate_to_object, calculate_distance


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


def try_move_sideways(controller, capture_callback):
    """좌우로 이동 가능한지 확인하고 우회"""
    left_event = controller.step(action='MoveLeft', moveMagnitude=0.25)
    capture_callback()
    if left_event.metadata['lastActionSuccess']:
        print("  ← 왼쪽으로 우회")
        return True
    
    right_event = controller.step(action='MoveRight', moveMagnitude=0.25)
    capture_callback()
    if right_event.metadata['lastActionSuccess']:
        print("  → 오른쪽으로 우회")
        return True
    
    return False


def closest_node(target, nodes):
    """타겟에 가장 가까운 노드 반환"""
    return min(nodes, key=lambda p: calculate_distance(p, target))


def build_graph(nodes, grid=0.25, slack=1e-3):
    """격자 기반 인접 리스트 생성"""
    adj = {i: [] for i in range(len(nodes))}
    for i, a in enumerate(nodes):
        for j, b in enumerate(nodes):
            if i == j:
                continue
            if abs(a['y'] - b['y']) > 1e-3:
                continue
            dist = calculate_distance(a, b)
            if dist <= grid + slack:
                adj[i].append(j)
    return adj


def smart_object_search(controller, object_type, capture_callback):
    """스마트 객체 탐색: 3단계 전략"""
    # 1단계: 빠른 스캔 (3번 회전, 120도씩)
    for i in range(3):
        if i > 0:
            controller.step(action='RotateRight', degrees=120)
            capture_callback()
        
        event = controller.last_event
        visible_objs = [obj for obj in event.metadata['objects']
                       if obj['visible'] and obj['objectType'] == object_type]
        if visible_objs:
            return visible_objs[0]
    
    # 2단계: Horizon 조정 (-30°, 30°, 60°)
    for horizon in [-30, 30, 60]:
        if horizon < 0:
            controller.step(action='LookUp', degrees=abs(horizon))
        else:
            controller.step(action='LookDown', degrees=horizon)
        capture_callback()
        
        for rotation_count in range(3):
            if rotation_count > 0:
                controller.step(action='RotateRight', degrees=120)
                capture_callback()
            
            event = controller.last_event
            visible_objs = [obj for obj in event.metadata['objects']
                           if obj['visible'] and obj['objectType'] == object_type]
            if visible_objs:
                # Horizon 복구
                if horizon < 0:
                    controller.step(action='LookDown', degrees=abs(horizon))
                else:
                    controller.step(action='LookUp', degrees=horizon)
                capture_callback()
                return visible_objs[0]
        
        # Horizon 복구
        if horizon < 0:
            controller.step(action='LookDown', degrees=abs(horizon))
        else:
            controller.step(action='LookUp', degrees=horizon)
        capture_callback()
    
    # 3단계: 전체 탐색 (360도)
    for _ in range(8):
        controller.step(action='RotateRight', degrees=45)
        capture_callback()
        
        event = controller.last_event
        visible_objs = [obj for obj in event.metadata['objects']
                       if obj['visible'] and obj['objectType'] == object_type]
        if visible_objs:
            return visible_objs[0]
    
    return None


def bfs_path(nodes, adj, start_pos, goal_pos):
    """BFS로 최단 경로 계산"""
    start_idx = nodes.index(closest_node(start_pos, nodes))
    goal_idx = nodes.index(closest_node(goal_pos, nodes))

    queue = [start_idx]
    parent = {start_idx: None}
    while queue:
        cur = queue.pop(0)
        if cur == goal_idx:
            break
        for nxt in adj[cur]:
            if nxt not in parent:
                parent[nxt] = cur
                queue.append(nxt)

    if goal_idx not in parent:
        return []

    path = []
    cur = goal_idx
    while cur is not None:
        path.append(cur)
        cur = parent[cur]
    return list(reversed(path))


class TaskExecutor:
    """작업 실행 클래스"""
    
    def __init__(self, controller, reachable_positions, graph, capture_callback):
        self.controller = controller
        self.reachable_positions = reachable_positions
        self.graph = graph
        self.capture_frame = capture_callback
        
    def move_to_target(self, goal_pos, stop_distance=0.5, max_replans=5):
        """AI2-THOR 경로 찾기를 사용하여 목표로 이동"""
        stuck_counter = 0
        last_position = None
        max_attempts = 50
        
        for attempt in range(max_attempts):
            current_pos = self.controller.last_event.metadata['agent']['position']
            dist = calculate_distance(current_pos, goal_pos)
            
            if dist <= stop_distance:
                return True
            
            # stuck 체크
            if last_position:
                movement = calculate_distance(current_pos, last_position)
                if movement < 0.05:
                    stuck_counter += 1
                else:
                    stuck_counter = 0
            last_position = current_pos
            
            # stuck 회피
            if stuck_counter >= 3:
                print(f"  🔄 막힘 감지, 회피 중...")
                self.controller.step(action='MoveBack', moveMagnitude=0.3)
                self.capture_frame()
                self.controller.step(action='RotateRight', degrees=60)
                self.capture_frame()
                stuck_counter = 0
                continue
            
            # GetShortestPathToPoint 사용
            path_result = self.controller.step(
                action='GetShortestPathToPoint',
                position=goal_pos
            )
            
            if path_result.metadata['lastActionSuccess']:
                corners = path_result.metadata['actionReturn']['corners']
                if corners and len(corners) > 1:
                    next_wp = corners[1]
                    
                    # 방향 계산 및 회전
                    dx = next_wp['x'] - current_pos['x']
                    dz = next_wp['z'] - current_pos['z']
                    target_angle = math.degrees(math.atan2(dx, dz))
                    current_rot = self.controller.last_event.metadata['agent']['rotation']['y']
                    angle_diff = (target_angle - current_rot + 180) % 360 - 180
                    
                    if abs(angle_diff) > 20:
                        direction = 'RotateRight' if angle_diff > 0 else 'RotateLeft'
                        self.controller.step(action=direction, degrees=min(45, abs(angle_diff)))
                        self.capture_frame()
                        continue
                    
                    # 이동
                    wp_dist = calculate_distance(current_pos, next_wp)
                    move_mag = min(0.25, wp_dist * 0.8)
                    evt = self.controller.step(action='MoveAhead', moveMagnitude=move_mag)
                    self.capture_frame()
                    
                    if not evt.metadata['lastActionSuccess']:
                        stuck_counter += 1
                    continue
            
            # 경로 찾기 실패 시 직접 이동
            dx = goal_pos['x'] - current_pos['x']
            dz = goal_pos['z'] - current_pos['z']
            target_angle = math.degrees(math.atan2(dx, dz))
            current_rot = self.controller.last_event.metadata['agent']['rotation']['y']
            angle_diff = (target_angle - current_rot + 180) % 360 - 180
            
            if abs(angle_diff) > 20:
                direction = 'RotateRight' if angle_diff > 0 else 'RotateLeft'
                self.controller.step(action=direction, degrees=min(45, abs(angle_diff)))
                self.capture_frame()
                continue
            
            move_mag = min(0.25, dist * 0.8)
            evt = self.controller.step(action='MoveAhead', moveMagnitude=move_mag)
            self.capture_frame()
            
            if not evt.metadata['lastActionSuccess']:
                stuck_counter += 1
        
        return calculate_distance(self.controller.last_event.metadata['agent']['position'], goal_pos) <= stop_distance
    
    def approach_and_face(self, goal_pos, stop_distance=0.5):
        """타겟을 향해 정면을 맞추고 더 근접"""
        stuck_counter = 0
        last_position = None
        
        for _ in range(15):
            current_pos = self.controller.last_event.metadata['agent']['position']
            dist = calculate_distance(current_pos, goal_pos)
            
            if dist <= stop_distance:
                return True
            
            # stuck 체크
            if last_position:
                movement = calculate_distance(current_pos, last_position)
                if movement < 0.05:
                    stuck_counter += 1
                    if stuck_counter >= 3:
                        print("  🔄 막힘 감지, 회피")
                        self.controller.step(action='MoveBack', moveMagnitude=0.2)
                        self.capture_frame()
                        self.controller.step(action='RotateRight', degrees=45)
                        self.capture_frame()
                        stuck_counter = 0
                else:
                    stuck_counter = 0
            last_position = current_pos
            
            # 방향 계산 및 회전
            dx = goal_pos['x'] - current_pos['x']
            dz = goal_pos['z'] - current_pos['z']
            target_angle = math.degrees(math.atan2(dx, dz))
            current_rot = self.controller.last_event.metadata['agent']['rotation']['y']
            angle_diff = (target_angle - current_rot + 180) % 360 - 180
            
            if abs(angle_diff) > 5:
                direction = 'RotateRight' if angle_diff > 0 else 'RotateLeft'
                self.controller.step(action=direction, degrees=min(30, abs(angle_diff)))
                self.capture_frame()
                continue
            
            # 이동
            step_mag = max(0.05, min(0.2, dist - stop_distance / 2))
            evt = self.controller.step(action='MoveAhead', moveMagnitude=step_mag)
            self.capture_frame()
            
            if not evt.metadata['lastActionSuccess']:
                stuck_counter += 1
        
        return calculate_distance(self.controller.last_event.metadata['agent']['position'], goal_pos) <= stop_distance
    
    def find_object(self, object_type):
        """씬에서 특정 타입의 객체 찾기"""
        objects = self.controller.last_event.metadata['objects']
        for obj in objects:
            if obj['objectType'] == object_type:
                return obj
        return None
    
    def scan_and_find_visible_object(self, object_type, max_retries=2):
        """회전하며 객체를 시야에서 찾기 (재이동 포함)"""
        print(f"  🔍 {object_type} 탐색 중...")
        
        for retry in range(max_retries):
            # 스마트 탐색 사용
            found_obj = smart_object_search(self.controller, object_type, self.capture_frame)
            
            if found_obj:
                print(f"  ✓ {object_type} 발견!")
                return found_obj
            
            # 못 찾으면 조금 이동 후 재시도
            if retry < max_retries - 1:
                print(f"  ⚠️  {object_type} 못 찾음, 재이동 시도 {retry + 1}/{max_retries - 1}")
                self.controller.step(action='MoveAhead', moveMagnitude=0.3)
                self.capture_frame()
        
        return None
    
    def pickup_object(self, obj):
        """객체 픽업"""
        print(f"  📦 {obj['objectType']} 픽업 시도...")
        
        for attempt in range(6):
            event = self.controller.step(
                action='PickupObject',
                objectId=obj['objectId'],
                forceAction=False
            )
            self.capture_frame()
            
            if event.metadata['lastActionSuccess']:
                print(f"  ✓ 픽업 성공!")
                return True
            else:
                error_msg = event.metadata.get('errorMessage', 'Unknown')
                print(f"  ⚠️ 시도 {attempt+1}/6: {error_msg}")
                
                if attempt < 5:
                    # 약간 위치 조정
                    self.controller.step(action='MoveAhead', moveMagnitude=0.1)
                    self.capture_frame()
        
        return False
    
    def slice_object(self, obj):
        """객체 자르기"""
        print(f"  🔪 {obj['objectType']} 자르기 시도...")
        
        for attempt in range(8):
            event = self.controller.step(
                action='SliceObject',
                objectId=obj['objectId'],
                forceAction=True
            )
            self.capture_frame()
            
            if event.metadata['lastActionSuccess']:
                print(f"  ✓ 자르기 성공!")
                return True
            else:
                error_msg = event.metadata.get('errorMessage', 'Unknown')
                print(f"  ⚠️ 시도 {attempt+1}/8: {error_msg}")
        
        return False
    
    def open_object(self, obj):
        """객체 열기 (냉장고, 캐비닛 등)"""
        print(f"  🚪 {obj['objectType']} 열기 시도...")
        
        for attempt in range(6):
            event = self.controller.step(
                action='OpenObject',
                objectId=obj['objectId'],
                forceAction=False
            )
            self.capture_frame()
            
            if event.metadata['lastActionSuccess']:
                print(f"  ✓ 열기 성공!")
                return True
            else:
                error_msg = event.metadata.get('errorMessage', 'Unknown')
                if 'already' in error_msg.lower() or 'open' in error_msg.lower():
                    print(f"  (이미 열려있음)")
                    return True
                print(f"  ⚠️ 시도 {attempt+1}/6: {error_msg}")
        
        return False
    
    def put_object(self, receptacle_obj):
        """들고 있는 객체를 수용체에 놓기"""
        print(f"  📥 {receptacle_obj['objectType']}에 놓기 시도...")
        
        for attempt in range(6):
            event = self.controller.step(
                action='PutObject',
                objectId=receptacle_obj['objectId'],
                forceAction=False,
                placeStationary=True
            )
            self.capture_frame()
            
            if event.metadata['lastActionSuccess']:
                print(f"  ✓ 놓기 성공!")
                return True
            else:
                error_msg = event.metadata.get('errorMessage', 'Unknown')
                print(f"  ⚠️ 시도 {attempt+1}/6: {error_msg}")
                
                if attempt < 5:
                    # 약간 위치/각도 조정
                    self.controller.step(action='MoveAhead', moveMagnitude=0.1)
                    self.capture_frame()
        
        return False
    
    def execute_task_slice_and_store(self, item_name, storage_name):
        """
        작업: 아이템을 찾아 자르고 저장소에 넣기
        예: "토마토를 썰어서 냉장고에 넣어둬"
        """
        print(f"\n{'='*60}")
        print(f"📋 작업: {item_name}을(를) 썰어서 {storage_name}에 넣기")
        print(f"{'='*60}")
        
        # 1단계: 아이템 찾기
        print(f"\n[1/5] {item_name} 찾기")
        item = self.find_object(item_name)
        if not item:
            print(f"❌ {item_name}을(를) 찾을 수 없음")
            return False
        
        print(f"  위치: ({item['position']['x']:.2f}, {item['position']['y']:.2f}, {item['position']['z']:.2f})")
        
        # 2단계: 걸어서 이동
        print(f"\n[2/5] {item_name}으로 이동")
        found_item = navigate_to_object(self.controller, None, item, self.capture_frame)
        
        if not found_item:
            print(f"❌ {item_name}와 상호작용 불가")
            return False
        
        print(f"  ✓ {item_name} 발견!")
        
        # 3단계: 자르기
        print(f"\n[3/5] {item_name} 자르기")
        event = self.controller.step(
            action='SliceObject',
            objectId=found_item['objectId']
        )
        self.capture_frame()
        
        if not event.metadata['lastActionSuccess']:
            print(f"❌ {item_name} 자르기 실패")
            return False
        
        print(f"  ✓ 자르기 완료!")
        
        # 자른 조각 찾기
        sliced_name = f"{item_name}Sliced"
        for rotation_count in range(4):
            event = self.controller.last_event
            visible_slices = [obj for obj in event.metadata['objects']
                            if 'Sliced' in obj['objectType'] and 
                            item_name in obj['objectType'] and
                            obj['visible']]
            
            if visible_slices:
                sliced_item = visible_slices[0]
                print(f"  ✓ {sliced_name} 발견!")
                break
            
            if rotation_count < 3:
                self.controller.step(action='RotateRight', degrees=90)
                self.capture_frame()
        else:
            print(f"❌ {sliced_name}을(를) 찾을 수 없음")
            return False
        
        # 픽업
        print(f"  📦 {sliced_name} 픽업 시도...")
        event = self.controller.step(
            action='PickupObject',
            objectId=sliced_item['objectId']
        )
        self.capture_frame()
        
        if not event.metadata['lastActionSuccess']:
            print(f"❌ 픽업 실패")
            return False
        
        print(f"  ✓ 픽업 성공!")
        
        # 4단계: 저장소 찾기 및 이동
        print(f"\n[4/5] {storage_name} 찾기 및 이동")
        storage = self.find_object(storage_name)
        if not storage:
            print(f"❌ {storage_name}을(를) 찾을 수 없음")
            return False
        
        print(f"  위치: ({storage['position']['x']:.2f}, {storage['position']['y']:.2f}, {storage['position']['z']:.2f})")
        
        found_storage = navigate_to_object(self.controller, None, storage, self.capture_frame)
        
        if not found_storage:
            print(f"❌ {storage_name}와 상호작용 불가")
            return False
        
        print(f"  ✓ {storage_name} 발견!")
        
        # 5단계: 저장소 열고 넣기
        print(f"\n[5/5] {storage_name}에 넣기")
        
        # 열기
        print(f"  🚪 {storage_name} 여는 중...")
        event = self.controller.step(
            action='OpenObject',
            objectId=found_storage['objectId']
        )
        self.capture_frame()
        
        if not event.metadata['lastActionSuccess']:
            print(f"❌ 열기 실패")
            return False
        
        print(f"  ✓ 열기 성공!")
        
        # 넣기
        print(f"  📥 {storage_name}에 놓는 중...")
        event = self.controller.step(
            action='PutObject',
            objectId=found_storage['objectId'],
            forceAction=True
        )
        self.capture_frame()
        
        if not event.metadata['lastActionSuccess']:
            print(f"❌ 놓기 실패")
            return False
        
        print(f"  ✓ 놓기 성공!")
        print(f"\n✅ 작업 완료!")
        return True


def main():
    print("="*60)
    print("Single Agent Task Executor")
    print("- 명령어 기반 작업 수행")
    print("- Third Party Camera + Agent POV 녹화")
    print("="*60)
    
    # 출력 디렉토리
    output_dir = 'output_videos'
    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # 비디오 설정
    fps = 6
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    
    frame_count = 0
    controller = None
    video_writers = {}
    
    def capture_frame():
        """프레임 캡처 (원본 해상도)"""
        nonlocal frame_count
        event = controller.last_event
        
        # Third party camera
        if event.third_party_camera_frames and len(event.third_party_camera_frames) > 0:
            topdown_frame = event.third_party_camera_frames[0]
            if topdown_frame is not None and topdown_frame.size > 0:
                # 원본 해상도 그대로 사용 (resize 제거)
                topdown_bgr = cv2.cvtColor(topdown_frame, cv2.COLOR_RGB2BGR)
                
                # 텍스트 오버레이: Top View와 Frame 번호
                cv2.putText(topdown_bgr, "Top View", (10, 30), 
                           cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
                cv2.putText(topdown_bgr, f"Frame {frame_count + 1}", (10, 70), 
                           cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
                
                video_writers['topview'].write(topdown_bgr)
        
        # Agent POV
        if event.frame is not None and event.frame.size > 0:
            # 원본 해상도 그대로 사용 (resize 제거)
            agent_bgr = cv2.cvtColor(event.frame, cv2.COLOR_RGB2BGR)
            
            # 텍스트 오버레이: Agent 0와 Frame 번호
            cv2.putText(agent_bgr, "Agent 0", (10, 30), 
                       cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
            cv2.putText(agent_bgr, f"Frame {frame_count + 1}", (10, 70), 
                       cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
            
            video_writers['agent_pov'].write(agent_bgr)
        
        frame_count += 1
    
    try:
        # Controller 초기화
        print("\n🎮 Controller 초기화 중...")
        controller = Controller(
            scene="FloorPlan1",
            agentCount=1,
            width=800,
            height=600,
            fieldOfView=90,
            visibilityDistance=10.0
        )
        
        # Controller 초기화 후 비디오 라이터 생성 (원본 해상도 사용)
        video_writers = {
            'topview': cv2.VideoWriter(
                os.path.join(output_dir, f'task_topview_{timestamp}.mp4'),
                fourcc, fps, (controller.last_event.frame.shape[1], 
                             controller.last_event.frame.shape[0])
            ),
            'agent_pov': cv2.VideoWriter(
                os.path.join(output_dir, f'task_agent_{timestamp}.mp4'),
                fourcc, fps, (controller.last_event.frame.shape[1], 
                             controller.last_event.frame.shape[0])
            )
        }
        
        print("✓ 초기화 완료")
        
        # Scene 정보
        reachable_positions = controller.step(action='GetReachablePositions').metadata['actionReturn']
        center_x = sum(p['x'] for p in reachable_positions) / len(reachable_positions)
        center_z = sum(p['z'] for p in reachable_positions) / len(reachable_positions)
        graph = build_graph(reachable_positions, grid=0.25)
        
        print(f"\n📍 Scene: {len(reachable_positions)}개 위치")
        
        # Scene 크기 계산
        padding = 0.8
        min_x = min(p['x'] for p in reachable_positions) - padding
        max_x = max(p['x'] for p in reachable_positions) + padding
        min_z = min(p['z'] for p in reachable_positions) - padding
        max_z = max(p['z'] for p in reachable_positions) + padding
        scene_width = max_x - min_x
        scene_depth = max_z - min_z
        
        all_objects = controller.last_event.metadata['objects']
        max_y = max(
            obj['position']['y'] + obj.get('axisAlignedBoundingBox', {}).get('size', {}).get('y', 0) / 2
            for obj in all_objects if obj['position']['y'] > 0
        )
        scene_height = max_y
        
        # 카메라 설정
        aspect_ratio = 800 / 600
        ceiling_margin = 0.01
        preferred_fov = 95.0
        
        half_fov = math.radians(preferred_fov / 2)
        height_for_depth = (scene_depth / 2) / math.tan(half_fov)
        height_for_width = (scene_width / 2) / (math.tan(half_fov) * aspect_ratio)
        required_height = max(height_for_depth, height_for_width)
        camera_height = min(max(1.5, scene_height - ceiling_margin), required_height + 0.3)
        
        # Third Party Camera 설치
        print(f"\n📹 Topdown 카메라 설치...")
        event = controller.step(
            action="AddThirdPartyCamera",
            position=dict(x=center_x, y=camera_height, z=center_z),
            rotation=dict(x=90, y=0, z=0),
            fieldOfView=preferred_fov
        )
        
        if event.metadata['lastActionSuccess']:
            print(f"✓ 카메라 설치 완료 (높이: {camera_height:.2f}m, FOV: {preferred_fov}°)")
            capture_frame()
        else:
            print(f"⚠️ 카메라 설치 실패")
        
        # 에이전트 무작위 시작 위치
        start_pos = get_random_position(reachable_positions)
        controller.step(
            action='TeleportFull',
            **start_pos,
            rotation={'x': 0, 'y': 0, 'z': 0},
            horizon=0,
            standing=True
        )
        print(f"📍 에이전트 시작: ({start_pos['x']:.2f}, {start_pos['z']:.2f})")
        capture_frame()
        
        # 작업 실행기 생성
        executor = TaskExecutor(controller, reachable_positions, graph, capture_frame)
        
        # 작업 수행: "토마토를 썰어서 냉장고에 넣어둬"
        success = executor.execute_task_slice_and_store("Tomato", "Fridge")
        
        # 결과
        print(f"\n{'='*60}")
        print(f"📊 작업 결과: {'✓ 성공' if success else '✗ 실패'}")
        print(f"{'='*60}")
        
        # 마무리
        print(f"\n✓ 녹화 완료 (총 {frame_count} 프레임)")
        print(f"📁 저장: task_topview_{timestamp}.mp4, task_agent_{timestamp}.mp4")
        
    finally:
        print("\n🔄 시스템 종료 중...")
        for writer in video_writers.values():
            writer.release()
        
        if controller is not None:
            controller.stop()
        print("✓ 종료 완료")


if __name__ == "__main__":
    main()
