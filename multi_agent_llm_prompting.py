#!/usr/bin/env python3
"""
Multi-Agent Task Executor based on Single Agent
- LLM을 통한 자연어 명령 분석 및 작업 분해
- 작업량에 맞는 최소 에이전트 생성 (최대 3명)
- 병렬 작업 수행
- 각 에이전트 POV만 저장 (topview 없음)
"""

import os
import sys
import cv2
import json
import random
import math
import requests
from datetime import datetime
from ai2thor.controller import Controller
from navigation_utils import navigate_to_object, calculate_distance, calculate_angle, normalize_angle


def query_ollama(prompt, model="llama3.2:3b"):
    """Ollama 로컬 LLM 쿼리"""
    try:
        response = requests.post(
            'http://localhost:11434/api/generate',
            json={
                'model': model,
                'prompt': prompt,
                'stream': False,
                'format': 'json'
            },
            timeout=60
        )
        
        if response.status_code == 200:
            result = response.json()
            response_text = result.get('response', '').strip()
            
            try:
                return json.loads(response_text)
            except json.JSONDecodeError as e:
                print(f"⚠️ JSON 파싱 오류: {e}")
                print(f"응답: {response_text[:200]}")
                return None
        else:
            print(f"❌ Ollama 요청 실패: {response.status_code}")
            return None
            
    except Exception as e:
        print(f"❌ Ollama 연결 오류: {e}")
        return None


def analyze_command(user_command):
    """LLM으로 사용자 명령 분석"""
    prompt = f"""You are a task planning assistant. Analyze the user's command and break it into executable tasks.

Available task types:
1. "slice_and_store": Cut an object and store it
   - Parameters: {{"source_object": "ObjectType", "target_object": "StorageType"}}
   - Example: "토마토를 썰어서 냉장고에 넣어줘" → {{"source_object": "Tomato", "target_object": "Fridge"}}

2. "toggle_light": Turn lights on/off
   - Parameters: {{"action": "켜기" or "끄기"}}
   - Example: "불을 꺼줘" → {{"action": "끄기"}}

3. "heat_object": Heat an object using microwave
   - Parameters: {{"object": "ObjectType"}}
   - Example: "빵을 데워줘" → {{"object": "Bread"}}

4. "clean_object": Clean an object using sink
   - Parameters: {{"object": "ObjectType"}}
   - Example: "접시를 씻어줘" → {{"object": "Plate"}}

Respond in JSON format:
{{
  "tasks": [
    {{
      "type": "task_type",
      "description": "작업 설명",
      "parameters": {{...}}
    }}
  ],
  "num_agents": <number>,
  "reasoning": "Why this number of agents"
}}

Rules:
- Independent tasks can run in parallel → use multiple agents
- Sequential/dependent tasks → use 1 agent
- Maximum 3 agents

Examples:

Input: "토마토를 썰어서 냉장고에 넣어주고, 불을 꺼줘"
Output:
{{
  "tasks": [
    {{
      "type": "slice_and_store",
      "description": "토마토를 썰어서 냉장고에 넣기",
      "parameters": {{"source_object": "Tomato", "target_object": "Fridge"}}
    }},
    {{
      "type": "toggle_light",
      "description": "불 끄기",
      "parameters": {{"action": "끄기"}}
    }}
  ],
  "num_agents": 2,
  "reasoning": "Two independent tasks that can run in parallel, so 2 agents needed."
}}

Input: "토마토를 썰어서 냉장고에 넣어줘"
Output:
{{
  "tasks": [
    {{
      "type": "slice_and_store",
      "description": "토마토를 썰어서 냉장고에 넣기",
      "parameters": {{"source_object": "Tomato", "target_object": "Fridge"}}
    }}
  ],
  "num_agents": 1,
  "reasoning": "One task, so only 1 agent needed."
}}

Now analyze: "{user_command}"
"""
    
    print("🤔 LLM 분석 중...")
    result = query_ollama(prompt)
    
    if result:
        print(f"✓ 분석 완료")
        print(f"  - 작업 수: {len(result['tasks'])}개")
        print(f"  - 필요 에이전트: {result['num_agents']}명")
        print(f"  - 분석: {result['reasoning']}")
        return result
    else:
        return None


def get_random_position(reachable_positions, exclude_positions=None, object_positions=None, min_distance_agents=3.0, min_distance_objects=2.5):
    """이동 가능한 위치 중 최적 위치 선택 (agent들 및 객체들과 최대한 멀리)"""
    
    # 각 위치에 대해 점수 계산 (거리의 합)
    position_scores = []
    
    for pos in reachable_positions:
        total_distance = 0
        valid = True
        
        # 다른 agent들과의 거리 체크
        if exclude_positions:
            for exclude_pos in exclude_positions:
                dist = calculate_distance(pos, exclude_pos)
                if dist < min_distance_agents:
                    valid = False
                    break
                total_distance += dist
        
        if not valid:
            continue
        
        # 객체들과의 거리 체크
        if object_positions:
            for obj_pos in object_positions:
                dist = calculate_distance(pos, obj_pos)
                if dist < min_distance_objects:
                    valid = False
                    break
                total_distance += dist
        
        if valid:
            position_scores.append((pos, total_distance))
    
    # 점수가 높은 위치들 중에서 선택 (상위 20%)
    if not position_scores:
        return random.choice(reachable_positions)
    
    position_scores.sort(key=lambda x: x[1], reverse=True)
    top_positions = position_scores[:max(1, len(position_scores) // 5)]
    
    return random.choice(top_positions)[0]


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


def move_to_target(controller, agent_id, goal_pos, capture_callback, stop_distance=1.0, max_iterations=200):
    """목표 위치로 이동 (개선된 충돌 회피 로직)"""
    step_kwargs = {'agentId': agent_id}
    stuck_count = 0
    last_distance = float('inf')
    avoidance_direction = 'right'  # 회피 시도 방향 (right/left 번갈아가며)
    
    for iteration in range(max_iterations):
        metadata = controller.last_event.events[agent_id].metadata
        current_pos = metadata['agent']['position']
        current_rot = metadata['agent']['rotation']['y']
        
        dist = calculate_distance(current_pos, goal_pos)
        
        # 목표 도착
        if dist <= stop_distance:
            return True
        
        # 진행 상황 체크
        if dist >= last_distance - 0.05:
            stuck_count += 1
            if stuck_count >= 5:
                print(f"  [Agent{agent_id}] ⚠️ 진행 없음, 우회 시도")
                # 좌우 회피 (번갈아가며)
                controller.step(action='MoveBack', moveMagnitude=0.3, **step_kwargs)
                capture_callback()
                
                rotate_action = 'RotateRight' if avoidance_direction == 'right' else 'RotateLeft'
                controller.step(action=rotate_action, degrees=45, **step_kwargs)
                capture_callback()
                
                # 방향 전환
                avoidance_direction = 'left' if avoidance_direction == 'right' else 'right'
                stuck_count = 0
                continue
        else:
            stuck_count = 0
        
        last_distance = dist
        
        # 목표 방향 계산
        target_angle = calculate_angle(current_pos, goal_pos)
        angle_diff = normalize_angle(target_angle - current_rot)
        
        # 방향 조정
        if abs(angle_diff) > 15:
            direction = 'RotateRight' if angle_diff > 0 else 'RotateLeft'
            controller.step(action=direction, degrees=min(30, abs(angle_diff)), **step_kwargs)
            capture_callback()
        else:
            # 전진
            event = controller.step(action='MoveAhead', moveMagnitude=0.25, **step_kwargs)
            capture_callback()
            
            if not event.metadata['lastActionSuccess']:
                # 충돌 시 스마트 회피
                print(f"  [Agent{agent_id}] 🚧 충돌 감지, {avoidance_direction} 회피 시도")
                
                # 1. 후진
                controller.step(action='MoveBack', moveMagnitude=0.2, **step_kwargs)
                capture_callback()
                
                # 2. 현재 방향으로 45도 회전
                rotate_action = 'RotateRight' if avoidance_direction == 'right' else 'RotateLeft'
                controller.step(action=rotate_action, degrees=45, **step_kwargs)
                capture_callback()
                
                # 3. 전진 시도
                attempt1 = controller.step(action='MoveAhead', moveMagnitude=0.25, **step_kwargs)
                capture_callback()
                
                if not attempt1.metadata['lastActionSuccess']:
                    # 실패 시 반대 방향 시도
                    print(f"  [Agent{agent_id}] 🔄 {avoidance_direction} 실패, 반대 방향 시도")
                    
                    # 정면으로 복귀
                    opposite_rotate = 'RotateLeft' if avoidance_direction == 'right' else 'RotateRight'
                    controller.step(action=opposite_rotate, degrees=45, **step_kwargs)
                    capture_callback()
                    
                    # 반대 방향으로 45도 회전
                    controller.step(action=opposite_rotate, degrees=45, **step_kwargs)
                    capture_callback()
                    
                    # 전진 시도
                    attempt2 = controller.step(action='MoveAhead', moveMagnitude=0.25, **step_kwargs)
                    capture_callback()
                    
                    if not attempt2.metadata['lastActionSuccess']:
                        # 둘 다 실패 시 원래 방향으로 복귀
                        print(f"  [Agent{agent_id}] ⚠️ 양쪽 회피 실패, 원래 방향으로 복귀")
                        rotate_action = 'RotateRight' if avoidance_direction == 'right' else 'RotateLeft'
                        controller.step(action=rotate_action, degrees=45, **step_kwargs)
                        capture_callback()
                    else:
                        # 반대 방향 성공 - 다음엔 이 방향부터 시도
                        avoidance_direction = 'left' if avoidance_direction == 'right' else 'right'
                        print(f"  [Agent{agent_id}] ✓ 반대 방향 회피 성공")
                else:
                    print(f"  [Agent{agent_id}] ✓ {avoidance_direction} 회피 성공")
    
    return calculate_distance(controller.last_event.events[agent_id].metadata['agent']['position'], goal_pos) <= stop_distance


def approach_and_face(controller, agent_id, target_obj, capture_callback):
    """목표 객체에 접근하고 바라보기"""
    step_kwargs = {'agentId': agent_id}
    
    for iteration in range(15):
        metadata = controller.last_event.events[agent_id].metadata
        current_pos = metadata['agent']['position']
        obj_pos = target_obj['position']
        
        dist = calculate_distance(current_pos, obj_pos)
        
        if dist <= 1.5:
            # 객체 방향 바라보기
            target_angle = calculate_angle(current_pos, obj_pos)
            current_angle = metadata['agent']['rotation']['y']
            angle_diff = normalize_angle(target_angle - current_angle)
            
            if abs(angle_diff) > 5:
                direction = 'RotateRight' if angle_diff > 0 else 'RotateLeft'
                controller.step(action=direction, degrees=min(30, abs(angle_diff)), **step_kwargs)
                capture_callback()
            else:
                return True
        else:
            # 더 가까이 이동
            if move_to_target(controller, agent_id, obj_pos, capture_callback, stop_distance=1.2, max_iterations=10):
                continue
            else:
                return False
    
    return False


class AgentTaskExecutor:
    """단일 에이전트 작업 실행자"""
    
    def __init__(self, controller, agent_id, reachable_positions, graph, capture_callback):
        self.controller = controller
        self.agent_id = agent_id
        self.reachable_positions = reachable_positions
        self.graph = graph
        self.capture_callback = capture_callback
    
    def find_object(self, object_type):
        """씬에서 특정 타입의 객체 찾기"""
        objects = self.controller.last_event.events[self.agent_id].metadata['objects']
        for obj in objects:
            if obj['objectType'] == object_type:
                return obj
        return None
    
    def execute_slice_and_store(self, source_object, target_object):
        """토마토를 썰어서 냉장고에 넣기"""
        print(f"\n[Agent{self.agent_id}] 🎯 작업: {source_object} → {target_object}")
        
        # 1. 소스 객체 찾기
        print(f"[Agent{self.agent_id}] [1/5] {source_object} 찾기")
        source_obj = self.find_object(source_object)
        if not source_obj:
            print(f"[Agent{self.agent_id}] ❌ {source_object} 없음")
            return False
        
        # 2. 소스 객체로 이동
        print(f"[Agent{self.agent_id}] [2/5] {source_object}로 이동")
        found_source = navigate_to_object(self.controller, self.agent_id, source_obj, self.capture_callback)
        if not found_source:
            print(f"[Agent{self.agent_id}] ❌ {source_object} 도달 실패")
            return False
        
        # 3. 자르기
        print(f"[Agent{self.agent_id}] [3/5] {source_object} 자르기")
        event = self.controller.step(
            action='SliceObject',
            objectId=found_source['objectId'],
            agentId=self.agent_id
        )
        self.capture_callback()
        
        if not event.metadata['lastActionSuccess']:
            print(f"[Agent{self.agent_id}] ❌ 자르기 실패")
            return False
        
        print(f"[Agent{self.agent_id}] ✓ 자르기 성공")
        
        # 슬라이스 찾기 (상하 시야 확인)
        sliced_type = source_object + "Sliced"
        for look_step in range(3):
            metadata = self.controller.last_event.events[self.agent_id].metadata
            visible_slices = [obj for obj in metadata['objects']
                            if sliced_type in obj['objectType'] and obj['visible']]
            
            if visible_slices:
                sliced_item = visible_slices[0]
                break
            
            if look_step == 0:
                print(f"[Agent{self.agent_id}] 👇 아래 확인")
                self.controller.step(action='LookDown', agentId=self.agent_id)
            elif look_step == 1:
                print(f"[Agent{self.agent_id}] 👆 위 확인")
                self.controller.step(action='LookUp', agentId=self.agent_id)
                self.controller.step(action='LookUp', agentId=self.agent_id)
            else:
                self.controller.step(action='LookDown', agentId=self.agent_id)
            
            self.capture_callback()
        else:
            print(f"[Agent{self.agent_id}] ❌ {sliced_type} 찾기 실패")
            return False
        
        # 픽업
        print(f"[Agent{self.agent_id}] 📦 {sliced_type} 픽업")
        event = self.controller.step(
            action='PickupObject',
            objectId=sliced_item['objectId'],
            agentId=self.agent_id
        )
        self.capture_callback()
        
        if not event.metadata['lastActionSuccess']:
            print(f"[Agent{self.agent_id}] ❌ 픽업 실패")
            return False
        
        # 4. 저장소 찾기 및 이동
        print(f"[Agent{self.agent_id}] [4/5] {target_object}로 이동")
        storage_obj = self.find_object(target_object)
        if not storage_obj:
            print(f"[Agent{self.agent_id}] ❌ {target_object} 없음")
            return False
        
        found_storage = navigate_to_object(self.controller, self.agent_id, storage_obj, self.capture_callback)
        if not found_storage:
            print(f"[Agent{self.agent_id}] ❌ {target_object} 도달 실패")
            return False
        
        # 5. 열고 넣기
        print(f"[Agent{self.agent_id}] [5/5] {target_object}에 넣기")
        event = self.controller.step(
            action='OpenObject',
            objectId=found_storage['objectId'],
            agentId=self.agent_id
        )
        self.capture_callback()
        
        if not event.metadata['lastActionSuccess']:
            print(f"[Agent{self.agent_id}] ❌ 열기 실패")
            return False
        
        event = self.controller.step(
            action='PutObject',
            objectId=found_storage['objectId'],
            forceAction=True,
            agentId=self.agent_id
        )
        self.capture_callback()
        
        if not event.metadata['lastActionSuccess']:
            print(f"[Agent{self.agent_id}] ❌ 넣기 실패")
            return False
        
        print(f"[Agent{self.agent_id}] ✅ 작업 완료!")
        return True
    
    def execute_toggle_light(self, action):
        """전등 켜기/끄기"""
        print(f"\n[Agent{self.agent_id}] 🎯 작업: 불 {action}")
        
        # 전등 스위치 찾기
        light_switch = self.find_object("LightSwitch")
        if not light_switch:
            print(f"[Agent{self.agent_id}] ❌ LightSwitch 없음")
            return False
        
        # 스위치로 이동
        print(f"[Agent{self.agent_id}] [1/2] LightSwitch로 이동")
        found_switch = navigate_to_object(self.controller, self.agent_id, light_switch, self.capture_callback)
        if not found_switch:
            print(f"[Agent{self.agent_id}] ❌ LightSwitch 도달 실패")
            return False
        
        # 토글
        print(f"[Agent{self.agent_id}] [2/2] 불 {action}")
        event = self.controller.step(
            action='ToggleObjectOn' if action == "켜기" else 'ToggleObjectOff',
            objectId=found_switch['objectId'],
            agentId=self.agent_id
        )
        self.capture_callback()
        
        if not event.metadata['lastActionSuccess']:
            print(f"[Agent{self.agent_id}] ❌ 토글 실패")
            return False
        
        print(f"[Agent{self.agent_id}] ✅ 작업 완료!")
        return True


def main():
    print("=" * 60)
    print("Multi-Agent Task Executor (Based on Single Agent)")
    print("=" * 60)
    
    # 명령 받기
    if len(sys.argv) > 1:
        user_command = ' '.join(sys.argv[1:])
    else:
        user_command = "토마토를 썰어서 냉장고에 넣고, 불을 꺼줘"
        print(f"\n💡 기본 명령 사용: '{user_command}'")
    
    print(f"\n📝 명령: {user_command}")
    
    # LLM 분석
    llm_result = analyze_command(user_command)
    if not llm_result:
        print("❌ 명령 분석 실패")
        return
    
    tasks = llm_result['tasks']
    num_agents = min(len(tasks), llm_result.get('num_agents', len(tasks)), 3)
    
    print(f"\n{'='*60}")
    print("📋 실행 계획:")
    for i, task_info in enumerate(tasks, 1):
        print(f"  {i}. {task_info['description']}")
    print(f"\n🤖 에이전트: {num_agents}명")
    print(f"{'='*60}\n")
    
    # 출력 디렉토리
    output_dir = 'output_videos'
    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # 비디오 설정
    fps = 30
    fourcc = cv2.VideoWriter_fourcc(*'avc1')
    
    frame_count = [0]
    controller = None
    video_writers = {}
    
    def capture_frame():
        """프레임 캡처"""
        event = controller.last_event
        for i in range(num_agents):
            if event.events[i].frame is not None and event.events[i].frame.size > 0:
                frame = event.events[i].frame
                agent_bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
                
                # 텍스트 오버레이
                cv2.putText(agent_bgr, f"Agent {i}", (10, 30), 
                           cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
                cv2.putText(agent_bgr, f"Frame {frame_count[0] + 1}", (10, 70), 
                           cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
                
                video_writers[i].write(agent_bgr)
        
        frame_count[0] += 1
    
    try:
        # Controller 초기화
        print("🎮 Controller 초기화 중...")
        controller = Controller(
            scene="FloorPlan1",
            agentCount=num_agents,
            width=800,
            height=600,
            fieldOfView=90,
            visibilityDistance=10.0
        )
        
        # 비디오 라이터 생성
        for i in range(num_agents):
            video_writers[i] = cv2.VideoWriter(
                os.path.join(output_dir, f'agent{i}_{timestamp}.mp4'),
                fourcc, fps, 
                (controller.last_event.events[i].frame.shape[1],
                 controller.last_event.events[i].frame.shape[0])
            )
        
        print("✓ 초기화 완료\n")
        
        # Scene 정보
        reachable_positions = controller.step(action='GetReachablePositions').metadata['actionReturn']
        graph = build_graph(reachable_positions, grid=0.25)
        
        # 모든 객체 위치 수집
        all_objects = controller.last_event.metadata['objects']
        object_positions = [obj['position'] for obj in all_objects]
        print(f"📦 씬 내 객체 수: {len(object_positions)}개")
        
        # 에이전트 시작 위치 (agent끼리, 객체들과도 최대한 멀리)
        start_positions = []
        for i in range(num_agents):
            start_pos = get_random_position(
                reachable_positions, 
                exclude_positions=start_positions,
                object_positions=object_positions,
                min_distance_agents=3.0,
                min_distance_objects=2.5
            )
            start_positions.append(start_pos)
            controller.step(
                action='TeleportFull',
                agentId=i,
                **start_pos,
                rotation={'x': 0, 'y': 0, 'z': 0},
                horizon=0,
                standing=True
            )
            print(f"[FRAME {frame_count[0] + 1}]")
            print(f"📍 Agent{i}: ({start_pos['x']:.2f}, {start_pos['z']:.2f})")
            capture_frame()
        
        print(f"\n💡 작업 실행 시작\n")
        
        # 에이전트 실행자 생성
        executors = []
        for i in range(num_agents):
            executor = AgentTaskExecutor(controller, i, reachable_positions, graph, capture_frame)
            executors.append(executor)
        
        # 작업 할당 및 실행
        results = []
        for i, task in enumerate(tasks):
            agent_id = i % num_agents
            task_type = task['type']
            params = task['parameters']
            
            if task_type == 'slice_and_store':
                success = executors[agent_id].execute_slice_and_store(
                    params['source_object'],
                    params['target_object']
                )
            elif task_type == 'toggle_light':
                success = executors[agent_id].execute_toggle_light(params['action'])
            else:
                print(f"[Agent{agent_id}] ❌ 지원하지 않는 작업: {task_type}")
                success = False
            
            results.append({
                'agent_id': agent_id,
                'task': task['description'],
                'success': success
            })
        
        # 결과 출력
        print(f"\n{'='*60}")
        print("📊 작업 결과:")
        for result in results:
            status = '✓' if result['success'] else '✗'
            print(f"  Agent{result['agent_id']}: {status} {result['task']}")
        print(f"{'='*60}")
        
        print(f"\n✓ 녹화 완료 (총 {frame_count[0]} 프레임)")
        for i in range(num_agents):
            print(f"📁 Agent{i}: agent{i}_{timestamp}.mp4")
        
    finally:
        print("\n🔄 종료 중...")
        for writer in video_writers.values():
            writer.release()
        
        if controller is not None:
            controller.stop()
        print("✓ 완료")


if __name__ == "__main__":
    main()
