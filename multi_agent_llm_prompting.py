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
        
        # 1. 소스 객체로 이동
        print(f"[Agent{self.agent_id}] [1/4] {source_object}로 이동")
        found_source = navigate_to_object(self.controller, self.agent_id, source_object, self.capture_callback)
        if not found_source:
            print(f"[Agent{self.agent_id}] ❌ {source_object} 도달 실패")
            return False
        
        # 2. 소스 객체 찾기
        metadata = self.controller.last_event.events[self.agent_id].metadata
        visible_sources = [obj for obj in metadata['objects'] 
                          if obj['objectType'] == source_object and obj['visible']]
        if not visible_sources:
            print(f"[Agent{self.agent_id}] ❌ {source_object} 보이지 않음")
            return False
        
        source_obj = visible_sources[0]
        
        # 3. 자르기
        print(f"[Agent{self.agent_id}] [2/4] {source_object} 자르기")
        event = self.controller.step(
            action='SliceObject',
            objectId=source_obj['objectId'],
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
        
        # 4. 저장소로 이동
        print(f"[Agent{self.agent_id}] [3/4] {target_object}로 이동")
        found_storage = navigate_to_object(self.controller, self.agent_id, target_object, self.capture_callback)
        if not found_storage:
            print(f"[Agent{self.agent_id}] ❌ {target_object} 도달 실패")
            return False
        
        # 5. 저장소 객체 찾기
        metadata = self.controller.last_event.events[self.agent_id].metadata
        visible_storages = [obj for obj in metadata['objects'] 
                           if obj['objectType'] == target_object and obj['visible']]
        if not visible_storages:
            print(f"[Agent{self.agent_id}] ❌ {target_object} 보이지 않음")
            return False
        
        storage_obj = visible_storages[0]
        
        # 6. 열고 넣기
        print(f"[Agent{self.agent_id}] [4/4] {target_object}에 넣기")
        event = self.controller.step(
            action='OpenObject',
            objectId=storage_obj['objectId'],
            agentId=self.agent_id
        )
        self.capture_callback()
        
        if not event.metadata['lastActionSuccess']:
            print(f"[Agent{self.agent_id}] ❌ 열기 실패")
            return False
        
        event = self.controller.step(
            action='PutObject',
            objectId=storage_obj['objectId'],
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
        
        # 1. 스위치로 이동
        print(f"[Agent{self.agent_id}] [1/2] LightSwitch로 이동")
        found_switch = navigate_to_object(self.controller, self.agent_id, "LightSwitch", self.capture_callback)
        if not found_switch:
            print(f"[Agent{self.agent_id}] ❌ LightSwitch 도달 실패")
            return False
        
        # 2. 스위치 객체 찾기
        metadata = self.controller.last_event.events[self.agent_id].metadata
        visible_switches = [obj for obj in metadata['objects'] 
                           if obj['objectType'] == "LightSwitch" and obj['visible']]
        if not visible_switches:
            print(f"[Agent{self.agent_id}] ❌ LightSwitch 보이지 않음")
            return False
        
        light_switch = visible_switches[0]
        
        # 3. 토글
        print(f"[Agent{self.agent_id}] [2/2] 불 {action}")
        event = self.controller.step(
            action='ToggleObjectOn' if action == "켜기" else 'ToggleObjectOff',
            objectId=light_switch['objectId'],
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
            visibilityDistance=10.0,
            snapToGrid=False,
            renderDepthImage=False,
            renderInstanceSegmentation=False,
            targetFrameRate=15  # FPS 15로 설정
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
        
        # 에이전트 초기 배치 (시뮬레이션 준비 단계)
        # 객체와의 최소 거리를 4.0m로 늘려서 반드시 이동하도록 함
        print(f"\n🎬 에이전트 배치 중...\n")
        start_positions = []
        for i in range(num_agents):
            start_pos = get_random_position(
                reachable_positions, 
                exclude_positions=start_positions,
                object_positions=object_positions,
                min_distance_agents=3.0,
                min_distance_objects=4.0
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
