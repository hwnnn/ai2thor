#!/usr/bin/env python3
"""
AI Multi-Agent Executor (Non-interactive)
- 명령을 인자로 받아서 자동 실행
"""

import sys
import os
import cv2
import json
import requests
from datetime import datetime
from ai2thor.controller import Controller
from multi_agent_parallel import MultiAgentTaskExecutor, TaskQueue


def query_ollama(prompt, model="llama3.2:3b"):
    """Ollama LLM에 프롬프트 전송"""
    try:
        response = requests.post(
            'http://localhost:11434/api/generate',
            json={
                'model': model,
                'prompt': prompt,
                'stream': False,
                'format': 'json'
            },
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            return json.loads(result['response'])
        else:
            print(f"❌ Ollama 오류: {response.status_code}")
            return None
    
    except requests.exceptions.ConnectionError:
        print("❌ Ollama 서버에 연결할 수 없습니다. 'ollama serve'를 실행했는지 확인하세요.")
        return None
    except Exception as e:
        print(f"❌ LLM 쿼리 오류: {e}")
        return None


def analyze_command(user_command):
    """사용자 명령을 분석하여 작업 목록 생성"""
    
    prompt = f"""You are a task planning assistant for a kitchen robot system in AI2-THOR simulation.

User command: "{user_command}"

Analyze the command and break it down into individual tasks. Each task should be one of these types:

1. slice_and_store: Slice an object and store it in a container
   - source_object: object to slice (e.g., "Tomato", "Potato", "Apple")
   - target_object: container (e.g., "Fridge", "Microwave")

2. toggle_light: Turn light on or off
   - action: "켜기" or "끄기"

3. heat_object: Heat an object in microwave
   - object: object to heat (e.g., "Bread", "Potato")

4. clean_object: Clean an object in sink
   - object: object to clean (e.g., "Plate", "Cup", "Bowl")

Available objects in AI2-THOR FloorPlan1:
- Food: Tomato, Potato, Apple, Bread, Egg
- Containers: Fridge, Microwave, Cabinet, Drawer
- Utensils: Plate, Cup, Bowl, Knife, Spoon
- Appliances: LightSwitch, SinkBasin, Toaster

Return your response as a JSON object with this structure:
{{
  "tasks": [
    {{
      "type": "task_type",
      "description": "human readable description",
      "parameters": {{}}
    }}
  ],
  "num_agents": number,
  "reasoning": "brief explanation"
}}

The num_agents should be EXACTLY equal to the number of tasks (1-3).
IMPORTANT: num_agents MUST match the number of tasks.
- 1 task = 1 agent
- 2 tasks = 2 agents
- 3 tasks = 3 agents

Examples:

Input: "토마토를 썰어서 냉장고에 넣고, 불을 꺼줘"
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


def convert_to_task_format(llm_result):
    """LLM 결과를 실행 가능한 작업 포맷으로 변환"""
    tasks = []
    for task_info in llm_result['tasks']:
        task = {'type': task_info['type']}
        task.update(task_info['parameters'])
        tasks.append(task)
    return tasks


def main():
    """메인 실행 함수"""
    print("=" * 60)
    print("AI-Powered Multi-Agent Task Executor")
    print("=" * 60)
    
    # 명령 받기 (인자 또는 기본값)
    if len(sys.argv) > 1:
        user_command = ' '.join(sys.argv[1:])
    else:
        user_command = "토마토를 썰어서 냉장고에 넣고, 불을 꺼줘"
        print(f"\n💡 기본 명령 사용: '{user_command}'")
        print("   (다른 명령: python ai_executor.py '명령어')\n")
    
    print(f"\n📝 명령: {user_command}")
    
    # LLM으로 명령 분석
    llm_result = analyze_command(user_command)
    
    if not llm_result:
        print("❌ 명령 분석 실패")
        return
    
    # 작업 변환
    tasks = convert_to_task_format(llm_result)
    # 작업 수에 맞춰 에이전트 수 결정 (최소값 사용)
    num_agents = min(len(tasks), llm_result.get('num_agents', len(tasks)), 3)
    
    print(f"\n{'='*60}")
    print("📋 실행 계획:")
    for i, task_info in enumerate(llm_result['tasks'], 1):
        print(f"  {i}. {task_info['description']}")
    print(f"\n🤖 에이전트: {num_agents}명")
    print(f"{'='*60}\n")
    
    # 출력 디렉토리
    output_dir = 'output_videos'
    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # 비디오 설정
    fps = 6
    fourcc = cv2.VideoWriter_fourcc(*'avc1')
    
    frame_count = [0]
    controller = None
    video_writers = {}
    
    def capture_frame_wrapper():
        """프레임 캡처 (원본 해상도)"""
        event = controller.last_event
        for i in range(num_agents):
            if event.events[i].frame is not None and event.events[i].frame.size > 0:
                frame = event.events[i].frame
                # 원본 해상도 그대로 사용 (resize 제거)
                agent_bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
                
                # 텍스트 오버레이: Agent 번호와 Frame 번호
                cv2.putText(agent_bgr, f"Agent {i}", (10, 30), 
                           cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
                cv2.putText(agent_bgr, f"Frame {frame_count[0] + 1}", (10, 70), 
                           cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
                
                video_writers[f'agent{i}'].write(agent_bgr)
        frame_count[0] += 1
        print(f"[FRAME {frame_count[0]}]", flush=True)  # 디버그 로그
    
    try:
        # Controller 초기화
        print(f"🎮 Controller 초기화 중... ({num_agents}명)")
        controller = Controller(
            scene="FloorPlan1",
            agentCount=num_agents,
            width=800,
            height=600,
            fieldOfView=90,
            visibilityDistance=10.0
        )
        
        # Controller 초기화 후 비디오 라이터 생성 (원본 해상도 사용)
        for i in range(num_agents):
            video_writers[f'agent{i}'] = cv2.VideoWriter(
                os.path.join(output_dir, f'ai_agent{i}_{timestamp}.mp4'),
                fourcc, fps, (controller.last_event.events[i].frame.shape[1], 
                             controller.last_event.events[i].frame.shape[0])
            )
        
        print("✓ 초기화 완료\n")
        
        # 에이전트 시작 위치
        start_positions = [
            {'x': 0.0, 'y': 0.91, 'z': 0.0},
            {'x': 2.0, 'y': 0.91, 'z': 0.0},
            {'x': -2.0, 'y': 0.91, 'z': 0.0},
        ]
        
        for i in range(num_agents):
            start_pos = start_positions[i % len(start_positions)]
            controller.step(
                action='TeleportFull',
                agentId=i,
                **start_pos,
                rotation={'x': 0, 'y': 0, 'z': 0},
                horizon=0,
                standing=True
            )
            capture_frame_wrapper()  # 초기 위치 프레임 캡처
            print(f"📍 Agent{i}: ({start_pos['x']:.2f}, {start_pos['z']:.2f})")
        
        capture_frame_wrapper()
        
        # 작업 큐 생성
        task_queue = TaskQueue()
        for task in tasks:
            task_queue.add_task(task)
        
        # 에이전트 실행자 생성
        executors = {}
        for i in range(num_agents):
            executors[i] = MultiAgentTaskExecutor(controller, i, capture_frame_wrapper)
        
        print(f"\n💡 병렬 작업 실행 시작\n")
        
        # 초기 작업 할당
        for agent_id in range(num_agents):
            task = task_queue.get_next_task(agent_id)
            if task:
                executors[agent_id].current_task = task
        
        # 병렬 실행 (인터리빙)
        max_iterations = 1000
        iteration = 0
        
        while task_queue.has_tasks() and iteration < max_iterations:
            iteration += 1
            
            # 모든 에이전트가 한 스텝씩 실행
            for agent_id in range(num_agents):
                executor = executors[agent_id]
                
                if executor.current_task:
                    completed = executor.execute_task_step(executor.current_task)
                    
                    if completed:
                        task_queue.complete_task(agent_id, True)
                        executor.current_task = None
                        executor.task_step = 0
                        executor.task_data = {}
                        
                        # 다음 작업 할당
                        next_task = task_queue.get_next_task(agent_id)
                        if next_task:
                            executor.current_task = next_task
        
        # 결과
        print(f"\n{'='*60}")
        print("📊 작업 결과:")
        for i, result in enumerate(task_queue.completed, 1):
            task_info = llm_result['tasks'][i-1] if i <= len(llm_result['tasks']) else {'description': 'Unknown'}
            status = '✓ 성공' if result['success'] else '✗ 실패'
            print(f"  {i}. {task_info['description']} (Agent {result['agent_id']}) - {status}")
        print(f"{'='*60}")
        
        # 마무리
        print(f"\n📹 마무리 중...")
        
        print(f"\n✓ 녹화 완료 (총 {frame_count[0]} 프레임)")
        print(f"📁 저장:")
        for i in range(num_agents):
            print(f"  - ai_agent{i}_{timestamp}.mp4")
    
    except KeyboardInterrupt:
        print("\n⚠️ 중단됨")
    
    finally:
        print(f"\n🔄 종료 중...")
        for writer in video_writers.values():
            writer.release()
        if controller:
            controller.stop()
        print("✓ 완료")


if __name__ == '__main__':
    main()
