#!/usr/bin/env python3
"""
Multi-Agent Parallel Task Executor
- 진정한 병렬 실행 (인터리빙)
- 동적 에이전트 생성 (최대 3명)
- 동적 작업 할당 (작업 큐 시스템)
"""

import os
import cv2
import numpy as np
from datetime import datetime
from ai2thor.controller import Controller
from collections import deque
from navigation_utils import navigate_to_object, calculate_distance, calculate_angle, normalize_angle
from navigation_action import navigate_single_action



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
        self.task_step = 0
        self.task_data = {}
        self.nav_state = 'idle'  # idle, navigating, rotating, moving_back, interacting, completed
        self.rotation_attempts = 0
        self.max_rotation_attempts = 1  # 한 번만 회전 시도
    
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
    
    def execute_single_action(self, task):
        """한 번의 액션만 실행 (병렬 인터리빙용)"""
        if task['type'] == 'slice_and_store':
            return self._action_slice_and_store(task)
        elif task['type'] == 'toggle_light':
            return self._action_toggle_light(task)
        elif task['type'] == 'heat_object':
            return self._action_heat_object(task)
        elif task['type'] == 'clean_object':
            return self._action_clean_object(task)
        return True
    
    def _action_slice_and_store(self, task):
        """slice_and_store를 액션 단위로 실행"""
        if self.task_step == 0:
            # 초기화: 객체 찾기
            target_obj = None
            for obj in self.controller.last_event.metadata['objects']:
                if obj['objectType'] == task['source_object'] and not obj['isPickedUp']:
                    target_obj = obj
                    break
            
            if not target_obj:
                print(f"[Agent{self.agent_id}] ❌ {task['source_object']}를 찾을 수 없음")
                return True
            
            self.task_data = {
                'source_obj': target_obj,
                'nav_state': {},
                'phase': 'navigate_to_source'
            }
            print(f"[Agent{self.agent_id}] 📋 {task['source_object']}를 썰어서 {task['target_object']}에 넣기")
            self.task_step = 1
            return False
        
        elif self.task_step == 1:
            # 소스 객체로 네비게이션 (액션 단위)
            if self.task_data['phase'] == 'navigate_to_source':
                completed, new_state, found_obj = navigate_single_action(
                    self.controller,
                    self.agent_id,
                    self.task_data['nav_state'],
                    self.task_data['source_obj'],
                    self.capture_callback
                )
                self.task_data['nav_state'] = new_state
                
                if completed:
                    if found_obj:
                        print(f"  [Agent{self.agent_id}] ✓ {task['source_object']} 도달!")
                        self.task_data['source_obj'] = found_obj
                        self.task_step = 2
                    else:
                        print(f"[Agent{self.agent_id}] ❌ {task['source_object']} 네비게이션 실패")
                        return True
                return False
        
        elif self.task_step == 2:
            # 자르기
            event = self.controller.step(
                action='SliceObject',
                objectId=self.task_data['source_obj']['objectId'],
                agentId=self.agent_id
            )
            self.capture_callback()
            
            if event.metadata['lastActionSuccess']:
                print(f"  [Agent{self.agent_id}] ✓ 자르기 성공!")
                self.task_step = 3
            else:
                print(f"[Agent{self.agent_id}] ❌ 자르기 실패")
                return True
            return False
        
        elif self.task_step == 3:
            # 슬라이스 조각 찾기 (한 번만 회전)
            event = self.controller.last_event.events[self.agent_id]
            visible_slices = [obj for obj in event.metadata['objects']
                            if 'Sliced' in obj['objectType'] and 
                            task['source_object'] in obj['objectType'] and
                            obj['visible']]
            
            if visible_slices:
                self.task_data['sliced'] = visible_slices[0]
                print(f"  [Agent{self.agent_id}] ✓ 슬라이스 발견!")
                self.task_step = 4
            else:
                # 상하 시야 확인
                look_step = self.task_data.get('look_step', 0)
                if look_step == 0:
                    # 아래 확인
                    print(f"  [Agent{self.agent_id}] 👇 아래 확인")
                    self.controller.step(action='LookDown', agentId=self.agent_id)
                    self.capture_callback()
                    self.task_data['look_step'] = 1
                elif look_step == 1:
                    # 위 확인
                    print(f"  [Agent{self.agent_id}] 👆 위 확인")
                    self.controller.step(action='LookUp', agentId=self.agent_id)
                    self.controller.step(action='LookUp', agentId=self.agent_id)
                    self.capture_callback()
                    self.task_data['look_step'] = 2
                else:
                    # 시선 정면으로 복구
                    self.controller.step(action='LookDown', agentId=self.agent_id)
                    self.capture_callback()
                    print(f"[Agent{self.agent_id}] ❌ 슬라이스를 찾을 수 없음")
                    return True
            return False
        
        elif self.task_step == 4:
            # 픽업
            event = self.controller.step(
                action='PickupObject',
                objectId=self.task_data['sliced']['objectId'],
                agentId=self.agent_id
            )
            self.capture_callback()
            
            if event.metadata['lastActionSuccess']:
                print(f"  [Agent{self.agent_id}] ✓ 픽업 성공!")
                self.task_step = 5
            else:
                return True
            return False
        
        elif self.task_step == 5:
            # 타겟 객체 찾기
            if self.task_data.get('phase') != 'navigate_to_target':
                target_obj = None
                for obj in self.controller.last_event.metadata['objects']:
                    if obj['objectType'] == task['target_object']:
                        target_obj = obj
                        break
                
                if not target_obj:
                    print(f"[Agent{self.agent_id}] ❌ {task['target_object']}를 찾을 수 없음")
                    return True
                
                self.task_data['target_obj'] = target_obj
                self.task_data['nav_state'] = {}
                self.task_data['phase'] = 'navigate_to_target'
            
            # 타겟으로 네비게이션
            completed, new_state, found_obj = navigate_single_action(
                self.controller,
                self.agent_id,
                self.task_data['nav_state'],
                self.task_data['target_obj'],
                self.capture_callback
            )
            self.task_data['nav_state'] = new_state
            
            if completed:
                if found_obj:
                    print(f"  [Agent{self.agent_id}] ✓ {task['target_object']} 도달!")
                    self.task_data['target_obj'] = found_obj
                    self.task_step = 6
                else:
                    print(f"[Agent{self.agent_id}] ❌ {task['target_object']} 네비게이션 실패")
                    return True
            return False
        
        elif self.task_step == 6:
            # 타겟 열기
            event = self.controller.step(
                action='OpenObject',
                objectId=self.task_data['target_obj']['objectId'],
                agentId=self.agent_id
            )
            self.capture_callback()
            
            if event.metadata['lastActionSuccess']:
                print(f"  [Agent{self.agent_id}] ✓ 열기 성공!")
                self.task_step = 7
            else:
                return True
            return False
        
        elif self.task_step == 7:
            # 넣기
            event = self.controller.step(
                action='PutObject',
                objectId=self.task_data['target_obj']['objectId'],
                agentId=self.agent_id
            )
            self.capture_callback()
            
            if event.metadata['lastActionSuccess']:
                print(f"  [Agent{self.agent_id}] ✓ 넣기 성공!")
                self.task_step = 8
            else:
                return True
            return False
        
        elif self.task_step == 8:
            # 닫기
            event = self.controller.step(
                action='CloseObject',
                objectId=self.task_data['target_obj']['objectId'],
                agentId=self.agent_id
            )
            self.capture_callback()
            
            print(f"[Agent{self.agent_id}] ✅ 작업 완료!")
            return True
        
        return True
    
    def _action_toggle_light(self, task):
        """toggle_light를 액션 단위로 실행"""
        if self.task_step == 0:
            # 라이트 스위치 찾기
            light_switch = None
            for obj in self.controller.last_event.metadata['objects']:
                if obj['objectType'] == 'LightSwitch':
                    light_switch = obj
                    break
            
            if not light_switch:
                print(f"[Agent{self.agent_id}] ❌ LightSwitch를 찾을 수 없음")
                return True
            
            self.task_data = {
                'light_switch': light_switch,
                'nav_state': {}
            }
            print(f"[Agent{self.agent_id}] 📋 LightSwitch {task['action']}")
            self.task_step = 1
            return False
        
        elif self.task_step == 1:
            # 네비게이션
            completed, new_state, found_obj = navigate_single_action(
                self.controller,
                self.agent_id,
                self.task_data['nav_state'],
                self.task_data['light_switch'],
                self.capture_callback
            )
            self.task_data['nav_state'] = new_state
            
            if completed:
                if found_obj:
                    print(f"  [Agent{self.agent_id}] ✓ LightSwitch 도달!")
                    self.task_data['light_switch'] = found_obj
                    self.task_step = 2
                else:
                    print(f"[Agent{self.agent_id}] ❌ LightSwitch 네비게이션 실패")
                    return True
            return False
        
        elif self.task_step == 2:
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
    
    def _action_heat_object(self, task):
        """heat_object를 액션 단위로 실행"""
        if self.task_step == 0:
            # 대상 객체 찾기
            target_obj = None
            for obj in self.controller.last_event.metadata['objects']:
                if obj['objectType'] == task['object']:
                    target_obj = obj
                    break
            
            if not target_obj:
                print(f"[Agent{self.agent_id}] ❌ {task['object']}를 찾을 수 없음")
                return True
            
            self.task_data = {
                'target_obj': target_obj,
                'nav_state': {},
                'phase': 'navigate_to_object'
            }
            print(f"[Agent{self.agent_id}] 📋 {task['object']}를 전자레인지에 데우기")
            self.task_step = 1
            return False
        
        elif self.task_step == 1:
            # 객체로 네비게이션
            if self.task_data['phase'] == 'navigate_to_object':
                completed, new_state, found_obj = navigate_single_action(
                    self.controller,
                    self.agent_id,
                    self.task_data['nav_state'],
                    self.task_data['target_obj'],
                    self.capture_callback
                )
                self.task_data['nav_state'] = new_state
                
                if completed:
                    if found_obj:
                        print(f"  [Agent{self.agent_id}] ✓ {task['object']} 도달!")
                        self.task_data['target_obj'] = found_obj
                        self.task_step = 2
                    else:
                        print(f"[Agent{self.agent_id}] ❌ {task['object']} 네비게이션 실패")
                        return True
            return False
        
        elif self.task_step == 2:
            # 픽업
            event = self.controller.step(
                action='PickupObject',
                objectId=self.task_data['target_obj']['objectId'],
                agentId=self.agent_id
            )
            self.capture_callback()
            
            if event.metadata['lastActionSuccess']:
                print(f"  [Agent{self.agent_id}] ✓ 픽업 성공!")
                self.task_step = 3
            else:
                return True
            return False
        
        elif self.task_step == 3:
            # Microwave 찾기
            if self.task_data.get('phase') != 'navigate_to_microwave':
                microwave = None
                for obj in self.controller.last_event.metadata['objects']:
                    if obj['objectType'] == 'Microwave':
                        microwave = obj
                        break
                
                if not microwave:
                    print(f"[Agent{self.agent_id}] ❌ Microwave를 찾을 수 없음")
                    return True
                
                self.task_data['microwave'] = microwave
                self.task_data['nav_state'] = {}
                self.task_data['phase'] = 'navigate_to_microwave'
            
            # Microwave로 네비게이션
            completed, new_state, found_obj = navigate_single_action(
                self.controller,
                self.agent_id,
                self.task_data['nav_state'],
                self.task_data['microwave'],
                self.capture_callback
            )
            self.task_data['nav_state'] = new_state
            
            if completed:
                if found_obj:
                    print(f"  [Agent{self.agent_id}] ✓ Microwave 도달!")
                    self.task_data['microwave'] = found_obj
                    self.task_step = 4
                else:
                    print(f"[Agent{self.agent_id}] ❌ Microwave 네비게이션 실패")
                    return True
            return False
        
        elif self.task_step == 4:
            # Microwave 열기
            event = self.controller.step(
                action='OpenObject',
                objectId=self.task_data['microwave']['objectId'],
                agentId=self.agent_id
            )
            self.capture_callback()
            
            if event.metadata['lastActionSuccess']:
                print(f"  [Agent{self.agent_id}] ✓ Microwave 열기 성공!")
                self.task_step = 5
            else:
                return True
            return False
        
        elif self.task_step == 5:
            # 넣기
            event = self.controller.step(
                action='PutObject',
                objectId=self.task_data['microwave']['objectId'],
                agentId=self.agent_id
            )
            self.capture_callback()
            
            if event.metadata['lastActionSuccess']:
                print(f"  [Agent{self.agent_id}] ✓ 넣기 성공!")
                self.task_step = 6
            else:
                return True
            return False
        
        elif self.task_step == 6:
            # 닫기
            event = self.controller.step(
                action='CloseObject',
                objectId=self.task_data['microwave']['objectId'],
                agentId=self.agent_id
            )
            self.capture_callback()
            
            if event.metadata['lastActionSuccess']:
                print(f"  [Agent{self.agent_id}] ✓ 닫기 성공!")
                self.task_step = 7
            else:
                return True
            return False
        
        elif self.task_step == 7:
            # 켜기
            event = self.controller.step(
                action='ToggleObjectOn',
                objectId=self.task_data['microwave']['objectId'],
                agentId=self.agent_id
            )
            self.capture_callback()
            
            print(f"[Agent{self.agent_id}] ✅ 작업 완료!")
            return True
        
        return True
    
    def _action_clean_object(self, task):
        """clean_object를 액션 단위로 실행"""
        if self.task_step == 0:
            # 대상 객체 찾기
            target_obj = None
            for obj in self.controller.last_event.metadata['objects']:
                if obj['objectType'] == task['object']:
                    target_obj = obj
                    break
            
            if not target_obj:
                print(f"[Agent{self.agent_id}] ❌ {task['object']}를 찾을 수 없음")
                return True
            
            self.task_data = {
                'target_obj': target_obj,
                'nav_state': {},
                'phase': 'navigate_to_object'
            }
            print(f"[Agent{self.agent_id}] 📋 {task['object']}를 싱크대에서 씻기")
            self.task_step = 1
            return False
        
        elif self.task_step == 1:
            # 객체로 네비게이션
            if self.task_data['phase'] == 'navigate_to_object':
                completed, new_state, found_obj = navigate_single_action(
                    self.controller,
                    self.agent_id,
                    self.task_data['nav_state'],
                    self.task_data['target_obj'],
                    self.capture_callback
                )
                self.task_data['nav_state'] = new_state
                
                if completed:
                    if found_obj:
                        print(f"  [Agent{self.agent_id}] ✓ {task['object']} 도달!")
                        self.task_data['target_obj'] = found_obj
                        self.task_step = 2
                    else:
                        print(f"[Agent{self.agent_id}] ❌ {task['object']} 네비게이션 실패")
                        return True
            return False
        
        elif self.task_step == 2:
            # 픽업
            event = self.controller.step(
                action='PickupObject',
                objectId=self.task_data['target_obj']['objectId'],
                agentId=self.agent_id
            )
            self.capture_callback()
            
            if event.metadata['lastActionSuccess']:
                print(f"  [Agent{self.agent_id}] ✓ 픽업 성공!")
                self.task_step = 3
            else:
                return True
            return False
        
        elif self.task_step == 3:
            # SinkBasin 찾기
            if self.task_data.get('phase') != 'navigate_to_sink':
                sink = None
                for obj in self.controller.last_event.metadata['objects']:
                    if obj['objectType'] == 'SinkBasin':
                        sink = obj
                        break
                
                if not sink:
                    print(f"[Agent{self.agent_id}] ❌ SinkBasin을 찾을 수 없음")
                    return True
                
                self.task_data['sink'] = sink
                self.task_data['nav_state'] = {}
                self.task_data['phase'] = 'navigate_to_sink'
            
            # SinkBasin으로 네비게이션
            completed, new_state, found_obj = navigate_single_action(
                self.controller,
                self.agent_id,
                self.task_data['nav_state'],
                self.task_data['sink'],
                self.capture_callback
            )
            self.task_data['nav_state'] = new_state
            
            if completed:
                if found_obj:
                    print(f"  [Agent{self.agent_id}] ✓ SinkBasin 도달!")
                    self.task_data['sink'] = found_obj
                    self.task_step = 4
                else:
                    print(f"[Agent{self.agent_id}] ❌ SinkBasin 네비게이션 실패")
                    return True
            return False
        
        elif self.task_step == 4:
            # 싱크대에 넣고 물로 씻기
            event = self.controller.step(
                action='CleanObject',
                objectId=self.task_data['target_obj']['objectId'],
                agentId=self.agent_id
            )
            self.capture_callback()
            
            print(f"[Agent{self.agent_id}] ✅ 작업 완료!")
            return True
        
        return True
    
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
            # 2. Tomato로 이동 및 찾기 (걸어서 이동)
            found_obj = navigate_to_object(
                self.controller, 
                self.agent_id, 
                self.task_data['tomato'],
                self.capture_callback
            )
            
            if found_obj:
                self.task_data['tomato'] = found_obj
                print(f"  [Agent{self.agent_id}] ✓ {task['source_object']} 발견!")
                self.task_step = 2
            else:
                print(f"[Agent{self.agent_id}] ❌ {task['source_object']}를 찾을 수 없음")
                return True
            return False
        
        elif self.task_step == 2:
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
            # 5. 슬라이스 조각 바로 픽업 시도 (자른 후 바로 옆에 있음)
            sliced_type = task['source_object'] + 'Sliced'
            
            # 주변을 빠르게 스캔 (모든 회전마다 캡처)
            for rotation_count in range(4):  # 90도씩 4번 회전
                event = self.controller.last_event.events[self.agent_id]
                visible_slices = [obj for obj in event.metadata['objects']
                                if 'Sliced' in obj['objectType'] and 
                                task['source_object'] in obj['objectType'] and
                                obj['visible']]
                
                if visible_slices:
                    self.task_data['sliced'] = visible_slices[0]
                    print(f"  [Agent{self.agent_id}] ✓ {sliced_type} 발견!")
                    self.task_step = 5
                    return False
                
                # 상하 시야 확인
                if rotation_count == 0:
                    print(f"  [Agent{self.agent_id}] 👇 아래 확인")
                    self.controller.step(action='LookDown', agentId=self.agent_id)
                    self.capture_callback()
                elif rotation_count == 1:
                    print(f"  [Agent{self.agent_id}] 👆 위 확인")
                    self.controller.step(action='LookUp', agentId=self.agent_id)
                    self.controller.step(action='LookUp', agentId=self.agent_id)
                    self.capture_callback()
                elif rotation_count == 2:
                    # 시선 정면으로 복구
                    self.controller.step(action='LookDown', agentId=self.agent_id)
                    self.capture_callback()
            
            print(f"[Agent{self.agent_id}] ❌ {sliced_type}를 찾을 수 없음")
            return True
        
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
            # 7. 타겟 찾기 및 이동 (내장 네비게이션)
            target = None
            for obj in self.controller.last_event.metadata['objects']:
                if obj['objectType'] == task['target_object']:
                    target = obj
                    break
            
            if not target:
                print(f"[Agent{self.agent_id}] ❌ {task['target_object']}를 찾을 수 없음")
                return True
            
            # 직접 상호작용 가능한 위치로 이동
            found_obj = navigate_to_object(
                self.controller,
                self.agent_id,
                target,
                self.capture_callback
            )
            
            if found_obj:
                self.task_data['target'] = found_obj
                print(f"  [Agent{self.agent_id}] ✓ {task['target_object']} 발견!")
                self.task_step = 7
            else:
                print(f"[Agent{self.agent_id}] ❌ {task['target_object']}와 상호작용 불가")
                return True
            return False
        
        elif self.task_step == 7:
            # 8. 타겟 열기
            event = self.controller.step(
                action='OpenObject',
                objectId=self.task_data['target']['objectId'],
                agentId=self.agent_id
            )
            self.capture_callback()
            
            if event.metadata['lastActionSuccess']:
                print(f"  [Agent{self.agent_id}] ✓ 열기 성공!")
                self.task_step = 8
            else:
                return True
            return False
        
        elif self.task_step == 8:
            # 9. 넣기
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
            # LightSwitch 찾기 및 이동 (내장 네비게이션)
            light_switch = None
            for obj in self.controller.last_event.metadata['objects']:
                if obj['objectType'] == 'LightSwitch':
                    light_switch = obj
                    break
            
            if not light_switch:
                print(f"[Agent{self.agent_id}] ❌ LightSwitch를 찾을 수 없음")
                return True
            
            # 직접 상호작용 가능한 위치로 이동
            found_obj = navigate_to_object(
                self.controller,
                self.agent_id,
                light_switch,
                self.capture_callback
            )
            
            if found_obj:
                self.task_data = {'light_switch': found_obj}
                print(f"[Agent{self.agent_id}] 📋 LightSwitch {task['action']}")
                print(f"  [Agent{self.agent_id}] ✓ LightSwitch 발견!")
                self.task_step = 1
            else:
                print(f"[Agent{self.agent_id}] ❌ LightSwitch와 상호작용 불가")
                return True
            return False
        
        elif self.task_step == 1:
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
            # 오브젝트 찾기 및 이동 (내장 네비게이션)
            obj = None
            for o in self.controller.last_event.metadata['objects']:
                if o['objectType'] == task['object'] and not o['isPickedUp']:
                    obj = o
                    break
            
            if not obj:
                print(f"[Agent{self.agent_id}] ❌ {task['object']}를 찾을 수 없음")
                return True
            
            # 직접 상호작용 가능한 위치로 이동
            found_obj = navigate_to_object(
                self.controller,
                self.agent_id,
                obj,
                self.capture_callback
            )
            
            if found_obj:
                self.task_data = {'object': found_obj, 'microwave': None}
                print(f"[Agent{self.agent_id}] 📋 {task['object']}를 데우기")
                print(f"  [Agent{self.agent_id}] ✓ {task['object']} 발견!")
                self.task_step = 1
            else:
                print(f"[Agent{self.agent_id}] ❌ {task['object']}와 상호작용 불가")
                return True
            return False
        
        elif self.task_step == 1:
            # 픽업
            event = self.controller.step(
                action='PickupObject',
                objectId=self.task_data['object']['objectId'],
                agentId=self.agent_id
            )
            self.capture_callback()
            
            if event.metadata['lastActionSuccess']:
                print(f"  [Agent{self.agent_id}] ✓ 픽업 성공!")
                self.task_step = 2
            else:
                return True
            return False
        
        elif self.task_step == 2:
            # 전자레인지 찾기 및 이동 (내장 네비게이션)
            microwave = None
            for obj in self.controller.last_event.metadata['objects']:
                if obj['objectType'] == 'Microwave':
                    microwave = obj
                    break
            
            if not microwave:
                print(f"[Agent{self.agent_id}] ❌ Microwave를 찾을 수 없음")
                return True
            
            # 직접 상호작용 가능한 위치로 이동
            found_obj = navigate_to_object(
                self.controller,
                self.agent_id,
                microwave,
                self.capture_callback
            )
            
            if found_obj:
                self.task_data['microwave'] = found_obj
                print(f"  [Agent{self.agent_id}] ✓ Microwave 발견!")
                self.task_step = 3
            else:
                print(f"[Agent{self.agent_id}] ❌ Microwave와 상호작용 불가")
                return True
            return False
        
        elif self.task_step == 3:
            # 전자레인지 열기
            event = self.controller.step(
                action='OpenObject',
                objectId=self.task_data['microwave']['objectId'],
                agentId=self.agent_id
            )
            self.capture_callback()
            
            if event.metadata['lastActionSuccess']:
                self.task_step = 4
            else:
                return True
            return False
        
        elif self.task_step == 4:
            # 전자레인지에 넣기
            event = self.controller.step(
                action='PutObject',
                objectId=self.task_data['microwave']['objectId'],
                agentId=self.agent_id
            )
            self.capture_callback()
            
            if event.metadata['lastActionSuccess']:
                self.task_step = 5
            else:
                return True
            return False
        
        elif self.task_step == 5:
            # 전자레인지 닫기
            event = self.controller.step(
                action='CloseObject',
                objectId=self.task_data['microwave']['objectId'],
                agentId=self.agent_id
            )
            self.capture_callback()
            
            if event.metadata['lastActionSuccess']:
                self.task_step = 6
            else:
                return True
            return False
        
        elif self.task_step == 6:
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
            # 오브젝트 찾기 및 이동 (내장 네비게이션)
            obj = None
            for o in self.controller.last_event.metadata['objects']:
                if o['objectType'] == task['object'] and not o['isPickedUp']:
                    obj = o
                    break
            
            if not obj:
                print(f"[Agent{self.agent_id}] ❌ {task['object']}를 찾을 수 없음")
                return True
            
            # 직접 상호작용 가능한 위치로 이동
            found_obj = navigate_to_object(
                self.controller,
                self.agent_id,
                obj,
                self.capture_callback
            )
            
            if found_obj:
                self.task_data = {'object': found_obj, 'sink': None}
                print(f"[Agent{self.agent_id}] 📋 {task['object']}를 씻기")
                print(f"  [Agent{self.agent_id}] ✓ {task['object']} 발견!")
                self.task_step = 1
            else:
                print(f"[Agent{self.agent_id}] ❌ {task['object']}와 상호작용 불가")
                return True
            return False
        
        elif self.task_step == 1:
            # 픽업
            event = self.controller.step(
                action='PickupObject',
                objectId=self.task_data['object']['objectId'],
                agentId=self.agent_id
            )
            self.capture_callback()
            
            if event.metadata['lastActionSuccess']:
                print(f"  [Agent{self.agent_id}] ✓ 픽업 성공!")
                self.task_step = 2
            else:
                return True
            return False
        
        elif self.task_step == 2:
            # 싱크대 찾기 및 이동 (내장 네비게이션)
            sink = None
            for obj in self.controller.last_event.metadata['objects']:
                if obj['objectType'] == 'SinkBasin':
                    sink = obj
                    break
            
            if not sink:
                print(f"[Agent{self.agent_id}] ❌ SinkBasin을 찾을 수 없음")
                return True
            
            # 직접 상호작용 가능한 위치로 이동
            found_obj = navigate_to_object(
                self.controller,
                self.agent_id,
                sink,
                self.capture_callback
            )
            
            if found_obj:
                self.task_data['sink'] = found_obj
                print(f"  [Agent{self.agent_id}] ✓ SinkBasin 발견!")
                self.task_step = 3
            else:
                print(f"[Agent{self.agent_id}] ❌ SinkBasin과 상호작용 불가")
                return True
            return False
        
        elif self.task_step == 3:
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
    num_agents = min(len(tasks), 3)  # 최대 3명
    
    print(f"\n🤖 에이전트 수: {num_agents}명")
    print(f"📋 작업 수: {len(tasks)}개")
    
    # 출력 디렉토리
    output_dir = 'output_videos'
    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # 비디오 설정
    fps = 6
    fourcc = cv2.VideoWriter_fourcc(*'avc1')
    
    frame_count = 0
    controller = None
    video_writers = {}
    
    def capture_frame():
        """모든 프레임 캡처 (원본 해상도)"""
        nonlocal frame_count
        
        event = controller.last_event
        for i in range(num_agents):
            if event.events[i].frame is not None and event.events[i].frame.size > 0:
                frame = event.events[i].frame
                # 원본 해상도 그대로 사용 (resize 제거)
                agent_bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
                
                # 텍스트 오버레이: Agent 번호와 Frame 번호
                cv2.putText(agent_bgr, f"Agent {i}", (10, 30), 
                           cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
                cv2.putText(agent_bgr, f"Frame {frame_count + 1}", (10, 70), 
                           cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
                
                video_writers[f'agent{i}'].write(agent_bgr)
        
        frame_count += 1
        print(f"[FRAME {frame_count}]", flush=True)  # 디버그 로그
    
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
        
        # Controller 초기화 후 비디오 라이터 생성 (원본 해상도 사용)
        for i in range(num_agents):
            video_writers[f'agent{i}'] = cv2.VideoWriter(
                os.path.join(output_dir, f'parallel_agent{i}_{timestamp}.mp4'),
                fourcc, fps, (controller.last_event.events[i].frame.shape[1], 
                             controller.last_event.events[i].frame.shape[0])
            )
        
        print("✓ 초기화 완료")
        
        # 에이전트 시작 위치 설정
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
            capture_frame()  # 초기 위치 프레임 캡처
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
                        
                        # 작업 완료 후 다음 작업 할당하지 않음 (가만히 서있기)
                        # next_task = task_queue.get_next_task(agent_id)
                        # if next_task:
                        #     executor.current_task = next_task
        
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
        
        # 마무리
        print(f"\n📹 마무리 중...")
        
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
