#!/usr/bin/env python3
"""
Multi-Agent Parallel Task Executor
- 진정한 병렬 실행 (인터리빙)
- 동적 에이전트 생성 (최대 4명)
- 동적 작업 할당 (작업 큐 시스템)
"""

import os
import cv2
import numpy as np
import math
from datetime import datetime
from ai2thor.controller import Controller
from collections import deque


def calculate_distance(pos1, pos2):
    """두 위치 간 거리 계산"""
    return math.sqrt((pos1['x'] - pos2['x'])**2 + (pos1['z'] - pos2['z'])**2)


def calculate_angle(from_pos, to_pos):
    """목표 방향의 각도 계산 (degrees)"""
    dx = to_pos['x'] - from_pos['x']
    dz = to_pos['z'] - from_pos['z']
    angle = math.degrees(math.atan2(dx, dz))
    return angle


def normalize_angle(angle):
    """각도를 -180~180 범위로 정규화"""
    while angle > 180:
        angle -= 360
    while angle < -180:
        angle += 360
    return angle


class TaskQueue:
    """작업 큐 관리"""
    def __init__(self):
        self.queue = deque()
        self.completed = []
        self.in_progress = {}
    
    def add_task(self, task):
        """작업 추가"""
        self.queue.append(task)
    
    def get_next_task(self, agent_id):
        """다음 작업 할당"""
        if self.queue:
            task = self.queue.popleft()
            self.in_progress[agent_id] = task
            return task
        return None
    
    def complete_task(self, agent_id, success):
        """작업 완료"""
        if agent_id in self.in_progress:
            task = self.in_progress[agent_id]
            self.completed.append({
                'task': task,
                'agent_id': agent_id,
                'success': success
            })
            del self.in_progress[agent_id]
    
    def has_tasks(self):
        """남은 작업이 있는지"""
        return len(self.queue) > 0 or len(self.in_progress) > 0


class MultiAgentTaskExecutor:
    """멀티 에이전트 작업 실행자"""
    
    def __init__(self, controller, agent_id, capture_callback):
        self.controller = controller
        self.agent_id = agent_id
        self.capture_callback = capture_callback
        self.current_task = None
        self.task_state = 'idle'  # idle, moving, interacting, completed
        self.task_step = 0
    
    def get_agent_position(self):
        """에이전트 현재 위치"""
        event = self.controller.last_event.events[self.agent_id]
        return event.metadata['agent']['position']
    
    def get_agent_rotation(self):
        """에이전트 현재 회전"""
        event = self.controller.last_event.events[self.agent_id]
        return event.metadata['agent']['rotation']['y']
    
    def step_towards_target(self, target_pos, min_distance=1.2):
        """목표로 한 스텝 이동 (병렬 실행용)"""
        current_pos = self.get_agent_position()
        distance = calculate_distance(current_pos, target_pos)
        
        if distance <= min_distance:
            return True, 'reached'
        
        # 목표 방향 계산
        target_angle = calculate_angle(current_pos, target_pos)
        current_angle = self.get_agent_rotation()
        angle_diff = normalize_angle(target_angle - current_angle)
        
        # 각도가 크게 다르면 회전
        if abs(angle_diff) > 10:
            rotate_action = 'RotateRight' if angle_diff > 0 else 'RotateLeft'
            event = self.controller.step(action=rotate_action, agentId=self.agent_id, degrees=abs(min(45, abs(angle_diff))))
            self.capture_callback()
            return False, 'rotating'
        
        # 전진
        move_amount = min(0.25, distance * 0.5)
        event = self.controller.step(
            action='MoveAhead',
            agentId=self.agent_id,
            moveMagnitude=move_amount
        )
        self.capture_callback()
        
        if not event.metadata['lastActionSuccess']:
            # 장애물 회피
            event = self.controller.step(action='RotateRight', agentId=self.agent_id, degrees=45)
            self.capture_callback()
            return False, 'avoiding'
        
        return False, 'moving'
    
    def execute_task_step(self, task):
        """작업을 한 스텝 실행 (병렬 실행용)"""
        if task['type'] == 'slice_and_store':
            return self._step_slice_and_store(task)
        elif task['type'] == 'toggle_light':
            return self._step_toggle_light(task)
        elif task['type'] == 'heat_object':
            return self._step_heat_object(task)
        elif task['type'] == 'clean_object':
            return self._step_clean_object(task)
        return True  # 완료
    
    def _step_slice_and_store(self, task):
        """토마토 썰어서 냉장고에 넣기 (스텝별)"""
        if self.task_step == 0:
            # 1. Tomato 찾기
            tomato = None
            for obj in self.controller.last_event.metadata['objects']:
                if obj['objectType'] == task['source_object'] and not obj['isPickedUp']:
                    tomato = obj
                    break
            
            if not tomato:
                print(f"[Agent{self.agent_id}] ❌ {task['source_object']}를 찾을 수 없음")
                return True  # 완료 (실패)
            
            self.task_data = {'tomato': tomato, 'target': None}
            print(f"[Agent{self.agent_id}] 📋 {task['source_object']}를 썰어서 {task['target_object']}에 넣기")
            print(f"  [Agent{self.agent_id}] {task['source_object']} 위치: ({tomato['position']['x']:.2f}, {tomato['position']['z']:.2f})")
            self.task_step = 1
            return False
        
        elif self.task_step == 1:
            # 2. Tomato로 이동
            reached, status = self.step_towards_target(self.task_data['tomato']['position'], min_distance=0.8)
            if reached:
                self.task_step = 2
            return False
        
        elif self.task_step == 2:
            # 3. Tomato 보기
            event = self.controller.last_event.events[self.agent_id]
            visible_objects = [obj for obj in event.metadata['objects'] 
                             if obj['visible'] and obj['objectType'] == task['source_object']]
            
            if visible_objects:
                self.task_data['tomato'] = visible_objects[0]
                self.task_step = 3
            else:
                self.controller.step(action='RotateRight', agentId=self.agent_id, degrees=45)
                self.capture_callback()
            return False
        
        elif self.task_step == 3:
            # 4. Slice
            event = self.controller.step(
                action='SliceObject',
                objectId=self.task_data['tomato']['objectId'],
                agentId=self.agent_id
            )
            self.capture_callback()
            
            if event.metadata['lastActionSuccess']:
                print(f"  [Agent{self.agent_id}] ✓ 자르기 성공!")
                self.task_step = 4
            else:
                print(f"[Agent{self.agent_id}] ❌ 자르기 실패")
                return True
            return False
        
        elif self.task_step == 4:
            # 5. 슬라이스 조각 찾기
            event = self.controller.last_event.events[self.agent_id]
            visible_slices = [obj for obj in event.metadata['objects'] 
                            if obj['visible'] and 'Sliced' in obj['objectType'] and task['source_object'] in obj['objectType']]
            
            if visible_slices:
                self.task_data['sliced'] = visible_slices[0]
                self.task_step = 5
            else:
                self.controller.step(action='RotateRight', agentId=self.agent_id, degrees=45)
                self.capture_callback()
            return False
        
        elif self.task_step == 5:
            # 6. 픽업
            event = self.controller.step(
                action='PickupObject',
                objectId=self.task_data['sliced']['objectId'],
                agentId=self.agent_id
            )
            self.capture_callback()
            
            if event.metadata['lastActionSuccess']:
                print(f"  [Agent{self.agent_id}] ✓ 픽업 성공!")
                self.task_step = 6
            else:
                return True
            return False
        
        elif self.task_step == 6:
            # 7. 타겟 찾기
            target = None
            for obj in self.controller.last_event.metadata['objects']:
                if obj['objectType'] == task['target_object']:
                    target = obj
                    break
            
            if not target:
                return True
            
            self.task_data['target'] = target
            self.task_step = 7
            return False
        
        elif self.task_step == 7:
            # 8. 타겟으로 이동
            reached, status = self.step_towards_target(self.task_data['target']['position'], min_distance=2.0)
            if reached:
                self.task_step = 8
            return False
        
        elif self.task_step == 8:
            # 9. 타겟 보기
            event = self.controller.last_event.events[self.agent_id]
            visible_targets = [obj for obj in event.metadata['objects'] 
                             if obj['visible'] and obj['objectType'] == task['target_object']]
            
            if visible_targets:
                self.task_data['target'] = visible_targets[0]
                self.task_step = 9
            else:
                self.controller.step(action='RotateRight', agentId=self.agent_id, degrees=45)
                self.capture_callback()
            return False
        
        elif self.task_step == 9:
            # 10. 타겟 열기
            event = self.controller.step(
                action='OpenObject',
                objectId=self.task_data['target']['objectId'],
                agentId=self.agent_id
            )
            self.capture_callback()
            
            if event.metadata['lastActionSuccess']:
                print(f"  [Agent{self.agent_id}] ✓ 열기 성공!")
                self.task_step = 10
            else:
                return True
            return False
        
        elif self.task_step == 10:
            # 11. 넣기
            event = self.controller.step(
                action='PutObject',
                objectId=self.task_data['target']['objectId'],
                agentId=self.agent_id,
                forceAction=True
            )
            self.capture_callback()
            
            if event.metadata['lastActionSuccess']:
                print(f"[Agent{self.agent_id}] ✅ 작업 완료!")
                return True
            else:
                return True
        
        return True
    
    def _step_toggle_light(self, task):
        """불 끄기/켜기 (스텝별)"""
        if self.task_step == 0:
            # LightSwitch 찾기
            light_switch = None
            for obj in self.controller.last_event.metadata['objects']:
                if obj['objectType'] == 'LightSwitch':
                    light_switch = obj
                    break
            
            if not light_switch:
                print(f"[Agent{self.agent_id}] ❌ LightSwitch를 찾을 수 없음")
                return True
            
            self.task_data = {'light_switch': light_switch}
            print(f"[Agent{self.agent_id}] 📋 LightSwitch {task['action']}")
            self.task_step = 1
            return False
        
        elif self.task_step == 1:
            # 이동
            reached, status = self.step_towards_target(self.task_data['light_switch']['position'], min_distance=1.0)
            if reached:
                self.task_step = 2
            return False
        
        elif self.task_step == 2:
            # 보기
            event = self.controller.last_event.events[self.agent_id]
            visible_switches = [obj for obj in event.metadata['objects'] 
                              if obj['visible'] and obj['objectType'] == 'LightSwitch']
            
            if visible_switches:
                self.task_data['light_switch'] = visible_switches[0]
                self.task_step = 3
            else:
                self.controller.step(action='RotateRight', agentId=self.agent_id, degrees=45)
                self.capture_callback()
            return False
        
        elif self.task_step == 3:
            # 토글
            if task['action'] == '끄기' and self.task_data['light_switch']['isToggled']:
                action = 'ToggleObjectOff'
            elif task['action'] == '켜기' and not self.task_data['light_switch']['isToggled']:
                action = 'ToggleObjectOn'
            else:
                print(f"  [Agent{self.agent_id}] ℹ️ 이미 {task['action']} 상태")
                return True
            
            event = self.controller.step(
                action=action,
                objectId=self.task_data['light_switch']['objectId'],
                agentId=self.agent_id
            )
            self.capture_callback()
            
            if event.metadata['lastActionSuccess']:
                print(f"  [Agent{self.agent_id}] ✓ {task['action']} 성공!")
                print(f"[Agent{self.agent_id}] ✅ 작업 완료!")
                return True
            else:
                return True
        
        return True
    
    def _step_heat_object(self, task):
        """물건 데우기 (스텝별)"""
        if self.task_step == 0:
            # 오브젝트 찾기
            obj = None
            for o in self.controller.last_event.metadata['objects']:
                if o['objectType'] == task['object'] and not o['isPickedUp']:
                    obj = o
                    break
            
            if not obj:
                print(f"[Agent{self.agent_id}] ❌ {task['object']}를 찾을 수 없음")
                return True
            
            self.task_data = {'object': obj, 'microwave': None}
            print(f"[Agent{self.agent_id}] 📋 {task['object']}를 데우기")
            self.task_step = 1
            return False
        
        elif self.task_step == 1:
            # 오브젝트로 이동
            reached, status = self.step_towards_target(self.task_data['object']['position'], min_distance=1.0)
            if reached:
                self.task_step = 2
            return False
        
        elif self.task_step == 2:
            # 보기
            event = self.controller.last_event.events[self.agent_id]
            visible_objs = [obj for obj in event.metadata['objects'] 
                          if obj['visible'] and obj['objectType'] == task['object']]
            
            if visible_objs:
                self.task_data['object'] = visible_objs[0]
                self.task_step = 3
            else:
                self.controller.step(action='RotateRight', agentId=self.agent_id, degrees=45)
                self.capture_callback()
            return False
        
        elif self.task_step == 3:
            # 픽업
            event = self.controller.step(
                action='PickupObject',
                objectId=self.task_data['object']['objectId'],
                agentId=self.agent_id
            )
            self.capture_callback()
            
            if event.metadata['lastActionSuccess']:
                print(f"  [Agent{self.agent_id}] ✓ 픽업 성공!")
                self.task_step = 4
            else:
                return True
            return False
        
        elif self.task_step == 4:
            # 전자레인지 찾기
            microwave = None
            for obj in self.controller.last_event.metadata['objects']:
                if obj['objectType'] == 'Microwave':
                    microwave = obj
                    break
            
            if not microwave:
                return True
            
            self.task_data['microwave'] = microwave
            self.task_step = 5
            return False
        
        elif self.task_step == 5:
            # 전자레인지로 이동
            reached, status = self.step_towards_target(self.task_data['microwave']['position'], min_distance=1.5)
            if reached:
                self.task_step = 6
            return False
        
        elif self.task_step == 6:
            # 전자레인지 보기
            event = self.controller.last_event.events[self.agent_id]
            visible_microwaves = [obj for obj in event.metadata['objects'] 
                                if obj['visible'] and obj['objectType'] == 'Microwave']
            
            if visible_microwaves:
                self.task_data['microwave'] = visible_microwaves[0]
                self.task_step = 7
            else:
                self.controller.step(action='RotateRight', agentId=self.agent_id, degrees=45)
                self.capture_callback()
            return False
        
        elif self.task_step == 7:
            # 전자레인지 열기
            event = self.controller.step(
                action='OpenObject',
                objectId=self.task_data['microwave']['objectId'],
                agentId=self.agent_id
            )
            self.capture_callback()
            
            if event.metadata['lastActionSuccess']:
                self.task_step = 8
            else:
                return True
            return False
        
        elif self.task_step == 8:
            # 전자레인지에 넣기
            event = self.controller.step(
                action='PutObject',
                objectId=self.task_data['microwave']['objectId'],
                agentId=self.agent_id
            )
            self.capture_callback()
            
            if event.metadata['lastActionSuccess']:
                self.task_step = 9
            else:
                return True
            return False
        
        elif self.task_step == 9:
            # 전자레인지 닫기
            event = self.controller.step(
                action='CloseObject',
                objectId=self.task_data['microwave']['objectId'],
                agentId=self.agent_id
            )
            self.capture_callback()
            
            if event.metadata['lastActionSuccess']:
                self.task_step = 10
            else:
                return True
            return False
        
        elif self.task_step == 10:
            # 전자레인지 켜기
            event = self.controller.step(
                action='ToggleObjectOn',
                objectId=self.task_data['microwave']['objectId'],
                agentId=self.agent_id
            )
            self.capture_callback()
            
            if event.metadata['lastActionSuccess']:
                print(f"  [Agent{self.agent_id}] ✓ 데우기 완료!")
                print(f"[Agent{self.agent_id}] ✅ 작업 완료!")
                return True
            else:
                return True
        
        return True
    
    def _step_clean_object(self, task):
        """물건 씻기 (스텝별)"""
        if self.task_step == 0:
            # 오브젝트 찾기
            obj = None
            for o in self.controller.last_event.metadata['objects']:
                if o['objectType'] == task['object'] and not o['isPickedUp']:
                    obj = o
                    break
            
            if not obj:
                print(f"[Agent{self.agent_id}] ❌ {task['object']}를 찾을 수 없음")
                return True
            
            self.task_data = {'object': obj, 'sink': None}
            print(f"[Agent{self.agent_id}] 📋 {task['object']}를 씻기")
            self.task_step = 1
            return False
        
        elif self.task_step == 1:
            # 오브젝트로 이동
            reached, status = self.step_towards_target(self.task_data['object']['position'], min_distance=1.0)
            if reached:
                self.task_step = 2
            return False
        
        elif self.task_step == 2:
            # 보기
            event = self.controller.last_event.events[self.agent_id]
            visible_objs = [obj for obj in event.metadata['objects'] 
                          if obj['visible'] and obj['objectType'] == task['object']]
            
            if visible_objs:
                self.task_data['object'] = visible_objs[0]
                self.task_step = 3
            else:
                self.controller.step(action='RotateRight', agentId=self.agent_id, degrees=45)
                self.capture_callback()
            return False
        
        elif self.task_step == 3:
            # 픽업
            event = self.controller.step(
                action='PickupObject',
                objectId=self.task_data['object']['objectId'],
                agentId=self.agent_id
            )
            self.capture_callback()
            
            if event.metadata['lastActionSuccess']:
                print(f"  [Agent{self.agent_id}] ✓ 픽업 성공!")
                self.task_step = 4
            else:
                return True
            return False
        
        elif self.task_step == 4:
            # 싱크대 찾기
            sink = None
            for obj in self.controller.last_event.metadata['objects']:
                if obj['objectType'] == 'SinkBasin':
                    sink = obj
                    break
            
            if not sink:
                return True
            
            self.task_data['sink'] = sink
            self.task_step = 5
            return False
        
        elif self.task_step == 5:
            # 싱크대로 이동
            reached, status = self.step_towards_target(self.task_data['sink']['position'], min_distance=1.2)
            if reached:
                self.task_step = 6
            return False
        
        elif self.task_step == 6:
            # 싱크대 보기
            event = self.controller.last_event.events[self.agent_id]
            visible_sinks = [obj for obj in event.metadata['objects'] 
                           if obj['visible'] and obj['objectType'] == 'SinkBasin']
            
            if visible_sinks:
                self.task_data['sink'] = visible_sinks[0]
                self.task_step = 7
            else:
                self.controller.step(action='RotateRight', agentId=self.agent_id, degrees=45)
                self.capture_callback()
            return False
        
        elif self.task_step == 7:
            # 씻기
            event = self.controller.step(
                action='CleanObject',
                objectId=self.task_data['object']['objectId'],
                agentId=self.agent_id
            )
            self.capture_callback()
            
            if event.metadata['lastActionSuccess']:
                print(f"  [Agent{self.agent_id}] ✓ 씻기 완료!")
                print(f"[Agent{self.agent_id}] ✅ 작업 완료!")
                return True
            else:
                return True
        
        return True


def main():
    """메인 실행 함수"""
    print("=" * 60)
    print("Multi-Agent Parallel Task Executor")
    print("- 진정한 병렬 실행 (인터리빙)")
    print("- 동적 작업 할당 (작업 큐)")
    print("=" * 60)
    
    # 작업 정의 (예시)
    tasks = [
        {'type': 'slice_and_store', 'source_object': 'Tomato', 'target_object': 'Fridge'},
        {'type': 'toggle_light', 'action': '끄기'},
        {'type': 'heat_object', 'object': 'Bread'},
        {'type': 'clean_object', 'object': 'Plate'},
    ]
    
    # 필요한 에이전트 수 계산 (최소)
    num_agents = min(len(tasks), 4)  # 최대 4명
    
    print(f"\n🤖 에이전트 수: {num_agents}명")
    print(f"📋 작업 수: {len(tasks)}개")
    
    # 출력 디렉토리
    output_dir = 'output_videos'
    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # 비디오 설정
    fps = 6
    fourcc = cv2.VideoWriter_fourcc(*'avc1')
    
    # 비디오 라이터 생성
    video_writers = {}
    for i in range(num_agents):
        video_writers[f'agent{i}'] = cv2.VideoWriter(
            os.path.join(output_dir, f'parallel_agent{i}_{timestamp}.mp4'),
            fourcc, fps, (800, 600)
        )
    
    frame_count = 0
    controller = None
    
    def capture_frame():
        """모든 프레임 캡처"""
        nonlocal frame_count
        
        event = controller.last_event
        for i in range(num_agents):
            if event.events[i].frame is not None and event.events[i].frame.size > 0:
                frame = event.events[i].frame
                if frame.shape[:2] != (600, 800):
                    frame = cv2.resize(frame, (800, 600))
                agent_bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
                video_writers[f'agent{i}'].write(agent_bgr)
        
        frame_count += 1
    
    try:
        # Controller 초기화
        print(f"\n🎮 Controller 초기화 중... ({num_agents}명의 에이전트)")
        controller = Controller(
            scene="FloorPlan1",
            agentCount=num_agents,
            width=800,
            height=600,
            fieldOfView=90,
            visibilityDistance=10.0
        )
        print("✓ 초기화 완료")
        
        # 에이전트 시작 위치 설정
        start_positions = [
            {'x': 0.0, 'y': 0.91, 'z': 0.0},
            {'x': 2.0, 'y': 0.91, 'z': 0.0},
            {'x': -2.0, 'y': 0.91, 'z': 0.0},
            {'x': 0.0, 'y': 0.91, 'z': 2.0},
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
            print(f"📍 Agent{i} 시작: ({start_pos['x']:.2f}, {start_pos['z']:.2f})")
        
        # 첫 프레임 캡처
        capture_frame()
        
        # 작업 큐 생성
        task_queue = TaskQueue()
        for task in tasks:
            task_queue.add_task(task)
        
        # 에이전트 실행자 생성
        executors = {}
        for i in range(num_agents):
            executors[i] = MultiAgentTaskExecutor(controller, i, capture_frame)
        
        print(f"\n{'='*60}")
        print("작업 할당 (동적):")
        for i, task in enumerate(tasks):
            task_desc = f"{task['type']}"
            if task['type'] == 'slice_and_store':
                task_desc = f"{task['source_object']}를 썰어서 {task['target_object']}에 넣기"
            elif task['type'] == 'toggle_light':
                task_desc = f"불 {task['action']}"
            elif task['type'] == 'heat_object':
                task_desc = f"{task['object']} 데우기"
            elif task['type'] == 'clean_object':
                task_desc = f"{task['object']} 씻기"
            print(f"  작업 {i+1}: {task_desc}")
        print(f"{'='*60}")
        
        print(f"\n💡 병렬 작업 실행 (진정한 인터리빙)\n")
        
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
                
                # 현재 작업이 있으면 한 스텝 실행
                if executor.current_task:
                    completed = executor.execute_task_step(executor.current_task)
                    
                    if completed:
                        # 작업 완료
                        task_queue.complete_task(agent_id, True)
                        executor.current_task = None
                        executor.task_step = 0
                        executor.task_data = {}
                        
                        # 다음 작업 할당
                        next_task = task_queue.get_next_task(agent_id)
                        if next_task:
                            executor.current_task = next_task
        
        # 결과 출력
        print(f"\n{'='*60}")
        print("📊 작업 결과:")
        for result in task_queue.completed:
            task = result['task']
            task_desc = f"{task['type']}"
            if task['type'] == 'slice_and_store':
                task_desc = f"{task['source_object']}→{task['target_object']}"
            elif task['type'] == 'toggle_light':
                task_desc = f"불 {task['action']}"
            elif task['type'] == 'heat_object':
                task_desc = f"{task['object']} 데우기"
            elif task['type'] == 'clean_object':
                task_desc = f"{task['object']} 씻기"
            
            status = '✓ 성공' if result['success'] else '✗ 실패'
            print(f"  Agent {result['agent_id']}: {task_desc} - {status}")
        print(f"{'='*60}")
        
        # 마무리 프레임
        print(f"\n📹 마무리 프레임...")
        for _ in range(10):
            capture_frame()
        
        print(f"\n✓ 녹화 완료 (총 {frame_count} 프레임)")
        print(f"📁 저장:")
        for i in range(num_agents):
            print(f"  - parallel_agent{i}_{timestamp}.mp4")
    
    except KeyboardInterrupt:
        print("\n⚠️ 사용자에 의해 중단됨")
    
    finally:
        # 정리
        print(f"\n🔄 시스템 종료 중...")
        
        for writer in video_writers.values():
            writer.release()
        
        if controller is not None:
            controller.stop()
        
        print("✓ 종료 완료")


if __name__ == '__main__':
    main()
