"""
AI2THOR Multi-Agent System with LLM-based Task Parsing
자연어 명령어를 받아 AI2THOR 에이전트를 생성하고 병렬로 작업을 수행하는 시스템
"""

import json
import os
import time
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
from ai2thor.controller import Controller
from openai import OpenAI


@dataclass
class TaskPlan:
    """작업 계획"""
    description: str
    actions: List[Dict[str, Any]]
    agent_id: Optional[str] = None
    dependencies: List[str] = field(default_factory=list)
    priority: int = 0


@dataclass
class AgentConfig:
    """에이전트 설정"""
    agent_id: str
    scene: str
    initial_position: Optional[Dict[str, float]] = None
    initial_rotation: Optional[Dict[str, float]] = None
    task_plan: Optional[TaskPlan] = None


class FunctionDatabase:
    """AI2THOR 함수 데이터베이스"""
    
    def __init__(self, db_path: str = "ai2thor_functions_db.json"):
        with open(db_path, 'r', encoding='utf-8') as f:
            self.functions = json.load(f)
    
    def search_by_keywords(self, keywords: List[str]) -> List[Tuple[str, Dict]]:
        """키워드로 함수 검색"""
        results = []
        for category, funcs in self.functions.items():
            for func_name, func_info in funcs.items():
                func_keywords = func_info.get('keywords', [])
                if any(kw.lower() in [fk.lower() for fk in func_keywords] for kw in keywords):
                    results.append((func_name, func_info))
        return results
    
    def get_function_info(self, func_name: str) -> Optional[Dict]:
        """함수 정보 가져오기"""
        for category, funcs in self.functions.items():
            if func_name in funcs:
                return funcs[func_name]
        return None
    
    def get_all_functions_summary(self) -> str:
        """모든 함수 요약 - 간단한 버전"""
        return """
Available Actions:
- MoveAhead, MoveBack, MoveLeft, MoveRight: Move agent (params: moveMagnitude)
- RotateLeft, RotateRight: Rotate agent (params: degrees)
- LookUp, LookDown: Look up/down (params: degrees)
- PickupObject, PutObject: Pick up or place objects (params: objectId)
- OpenObject, CloseObject: Open/close objects (params: objectId)
- ToggleObjectOn, ToggleObjectOff: Turn on/off objects (params: objectId)
- SliceObject: Slice objects (params: objectId)
- GetReachablePositions: Get all positions agent can reach
"""


class LLMTaskPlanner:
    """LLM 기반 작업 계획기 (GPT-4 또는 로컬 gpt-oss 사용)"""
    
    def __init__(self, function_db: FunctionDatabase, api_key: Optional[str] = None, use_local: bool = False):
        self.function_db = function_db
        self.use_local = use_local
        
        if use_local:
            # Ollama 로컬 서버 사용 (gpt-oss 또는 다른 모델)
            self.client = OpenAI(
                base_url="http://localhost:11434/v1",
                api_key="ollama"  # Ollama는 API 키가 필요없지만 형식상 필요
            )
            self.model = "llama3.2:3b"  # 균형잡힌 3B 모델 (속도 + 품질)
            print(f"🚀 Using local LLM: {self.model} via Ollama")
        else:
            # OpenAI API 사용
            self.client = OpenAI(api_key=api_key or os.environ.get("OPENAI_API_KEY"))
            self.model = "gpt-4"
            print("🌐 Using OpenAI GPT-4")
    
    def parse_natural_language_command(self, command: str, context: Optional[Dict] = None) -> List[TaskPlan]:
        """자연어 명령을 TaskPlan 리스트로 변환"""
        
        # 함수 데이터베이스 요약
        functions_summary = self.function_db.get_all_functions_summary()
        
        # 컨텍스트 정보
        context_str = json.dumps(context, indent=2) if context else "None"
        
        prompt = f"""You are an AI2THOR task planning expert. Given a natural language command in Korean or English, 
you need to decompose it into multiple sub-tasks and determine the MINIMUM number of agents needed.

Available AI2THOR Functions:
{functions_summary}

Current Context:
{context_str}

User Command:
{command}

Please analyze this command and create a detailed execution plan. 

CRITICAL: Your response MUST be valid JSON ONLY. No explanations, no markdown, no extra text.
Return ONLY a valid JSON object with this EXACT structure:

{{
    "analysis": "Brief analysis of the command",
    "num_agents": 2,
    "reasoning": "Why this many agents are needed",
    "tasks": [
        {{
            "description": "Task description",
            "agent_id": "agent_1",
            "actions": [
                {{
                    "action": "MoveAhead",
                    "parameters": {{"moveMagnitude": 1.0}},
                    "reason": "Why this action"
                }}
            ],
            "dependencies": [],
            "priority": 1
        }}
    ]
}}

IMPORTANT GUIDELINES:
1. MINIMIZE the number of agents - only create multiple agents if tasks can truly run in parallel
2. Sequential tasks should use ONE agent
3. Parallel tasks need multiple agents
4. Break down commands into simple AI2THOR actions
5. RESPOND WITH VALID JSON ONLY - no other text, no markdown code blocks
5. Use appropriate action names from the function list above
6. For object interactions, use proper action sequences:
   - To slice: PickupObject (knife) -> SliceObject (objectId)
   - To toggle: ToggleObjectOn or ToggleObjectOff
   - To put in fridge: PickupObject -> OpenObject (fridge) -> PutObject -> CloseObject
7. Consider task dependencies and set priorities accordingly

Return ONLY valid JSON, no additional text."""

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "You are a JSON generator. Always respond with valid JSON only. No explanations, no markdown, no code blocks."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=4096,
            temperature=0.3  # 더 일관된 출력을 위해 낮춤
        )
        
        # 응답 파싱
        response_text = response.choices[0].message.content.strip()
        
        # JSON 추출 (```json ... ``` 형태로 올 수 있음)
        if "```json" in response_text:
            json_start = response_text.find("```json") + 7
            json_end = response_text.find("```", json_start)
            response_text = response_text[json_start:json_end].strip()
        elif "```" in response_text:
            json_start = response_text.find("```") + 3
            json_end = response_text.find("```", json_start)
            response_text = response_text[json_start:json_end].strip()
        
        # JSON 시작/끝 찾기 (마크다운 블록이 없는 경우)
        if not response_text.startswith("{"):
            brace_start = response_text.find("{")
            if brace_start != -1:
                response_text = response_text[brace_start:]
        
        if not response_text.endswith("}"):
            brace_end = response_text.rfind("}")
            if brace_end != -1:
                response_text = response_text[:brace_end+1]
        
        try:
            plan_data = json.loads(response_text)
        except json.JSONDecodeError as e:
            print(f"Failed to parse LLM response: {e}")
            print(f"Response text: {response_text}")
            raise
        
        # TaskPlan 객체로 변환
        task_plans = []
        for task in plan_data.get('tasks', []):
            task_plan = TaskPlan(
                description=task['description'],
                actions=task['actions'],
                agent_id=task.get('agent_id'),
                dependencies=task.get('dependencies', []),
                priority=task.get('priority', 0)
            )
            task_plans.append(task_plan)
        
        return task_plans, plan_data.get('num_agents', 1), plan_data.get('analysis', '')


class AI2THORAgent:
    """AI2THOR 에이전트 (각 에이전트는 독립적인 Controller를 가짐)"""
    
    def __init__(self, config: AgentConfig):
        self.config = config
        self.controller = None
        self.execution_log = []
        self.lock = threading.Lock()
    
    def initialize(self, **kwargs):
        """Controller 초기화"""
        init_params = {
            'agentMode': 'default',
            'visibilityDistance': 1.5,
            'scene': self.config.scene,
            'gridSize': 0.25,
            'snapToGrid': True,
            'rotateStepDegrees': 90,
            'renderDepthImage': False,
            'renderInstanceSegmentation': False,
            'width': 800,  # POV 비디오와 일치
            'height': 600,  # POV 비디오와 일치
            'fieldOfView': 90
        }
        init_params.update(kwargs)
        
        self.controller = Controller(**init_params)
        
        # 초기 위치로 텔레포트
        if self.config.initial_position or self.config.initial_rotation:
            teleport_params = {'action': 'Teleport'}
            if self.config.initial_position:
                teleport_params['position'] = self.config.initial_position
            if self.config.initial_rotation:
                teleport_params['rotation'] = self.config.initial_rotation
            self.controller.step(**teleport_params)
        
        print(f"[{self.config.agent_id}] Initialized in scene {self.config.scene}")
    
    def execute_action(self, action_dict: Dict[str, Any]) -> Dict[str, Any]:
        """단일 액션 실행 (개선된 객체 상호작용)"""
        with self.lock:
            action_name = action_dict['action']
            parameters = action_dict.get('parameters', {})
            reason = action_dict.get('reason', '')
            
            print(f"[{self.config.agent_id}] Executing: {action_name} - {reason}")
            
            try:
                # 객체 ID가 필요한 경우 자동으로 찾기
                if 'objectId' in parameters and not parameters.get('objectId'):
                    # 파라미터에 objectType이 있으면 해당 타입의 객체 찾기
                    if 'objectType' in parameters:
                        visible_objects = self.controller.last_event.metadata['objects']
                        matching_objects = [obj for obj in visible_objects 
                                          if obj['objectType'] == parameters['objectType'] 
                                          and obj['visible']]
                        if matching_objects:
                            parameters['objectId'] = matching_objects[0]['objectId']
                            print(f"[{self.config.agent_id}] Found object: {parameters['objectId']}")
                        else:
                            return {
                                'success': False,
                                'action': action_name,
                                'error': f"No visible {parameters['objectType']} found",
                                'agent_position': self.controller.last_event.metadata['agent']['position'],
                                'objects_visible': 0
                            }
                
                # forceAction을 True로 설정하여 거리 제약 완화
                if action_name in ['PickupObject', 'OpenObject', 'CloseObject', 
                                  'ToggleObjectOn', 'ToggleObjectOff', 'SliceObject']:
                    if 'forceAction' not in parameters:
                        parameters['forceAction'] = True
                
                event = self.controller.step(action=action_name, **parameters)
                
                result = {
                    'success': event.metadata['lastActionSuccess'],
                    'action': action_name,
                    'error': event.metadata.get('errorMessage', ''),
                    'agent_position': event.metadata['agent']['position'],
                    'objects_visible': len([obj for obj in event.metadata['objects'] if obj['visible']])
                }
                
                self.execution_log.append({
                    'action': action_name,
                    'parameters': parameters,
                    'reason': reason,
                    'result': result
                })
                
                if result['success']:
                    print(f"[{self.config.agent_id}] ✓ Action succeeded")
                else:
                    print(f"[{self.config.agent_id}] ✗ Action failed: {result['error']}")
                
                return result
                
            except Exception as e:
                error_result = {
                    'success': False,
                    'action': action_name,
                    'error': str(e),
                    'agent_position': None,
                    'objects_visible': 0
                }
                print(f"[{self.config.agent_id}] ✗ Exception: {e}")
                return error_result
    
    def execute_task_plan(self, task_plan: TaskPlan) -> Dict[str, Any]:
        """TaskPlan 실행"""
        print(f"\n[{self.config.agent_id}] Starting task: {task_plan.description}")
        
        results = []
        for i, action_dict in enumerate(task_plan.actions, 1):
            print(f"[{self.config.agent_id}] Action {i}/{len(task_plan.actions)}")
            result = self.execute_action(action_dict)
            results.append(result)
            
            # 실패 시 중단할지 결정 (기본적으로 계속 진행)
            if not result['success']:
                print(f"[{self.config.agent_id}] Warning: Action failed but continuing...")
        
        summary = {
            'agent_id': self.config.agent_id,
            'task_description': task_plan.description,
            'total_actions': len(task_plan.actions),
            'successful_actions': sum(1 for r in results if r['success']),
            'failed_actions': sum(1 for r in results if not r['success']),
            'results': results,
            'execution_log': self.execution_log
        }
        
        print(f"[{self.config.agent_id}] Task completed: {summary['successful_actions']}/{summary['total_actions']} actions succeeded\n")
        
        return summary
    
    def get_current_state(self) -> Dict[str, Any]:
        """현재 상태 가져오기"""
        if not self.controller:
            return {}
        
        event = self.controller.step(action='Done')
        return {
            'agent_position': event.metadata['agent']['position'],
            'agent_rotation': event.metadata['agent']['rotation'],
            'camera_horizon': event.metadata['agent']['cameraHorizon'],
            'objects_in_view': [
                {
                    'objectId': obj['objectId'],
                    'objectType': obj['objectType'],
                    'position': obj['position'],
                    'distance': obj['distance']
                }
                for obj in event.metadata['objects'] if obj['visible']
            ]
        }
    
    def shutdown(self):
        """Controller 종료"""
        if self.controller:
            self.controller.stop()
            print(f"[{self.config.agent_id}] Shutdown complete")


class MultiAgentOrchestrator:
    """멀티 에이전트 오케스트레이터"""
    
    def __init__(self, function_db: FunctionDatabase, llm_planner: LLMTaskPlanner):
        self.function_db = function_db
        self.llm_planner = llm_planner
        self.agents: Dict[str, AI2THORAgent] = {}
        self.visualizer = None  # 시각화 객체
    
    def enable_visualization(self, output_dir: str = "output_videos"):
        """시각화 활성화"""
        try:
            from multi_agent_visualizer import MultiAgentVisualizer
            self.visualizer = MultiAgentVisualizer(output_dir)
            print("✅ 시각화 시스템 활성화됨")
        except ImportError:
            print("⚠️  multi_agent_visualizer.py를 찾을 수 없습니다. 시각화 비활성화됨")
            self.visualizer = None
    
    def execute_natural_language_command(
        self, 
        command: str, 
        scene: str = "FloorPlan1",
        context: Optional[Dict] = None,
        max_agents: int = 5,
        enable_video: bool = False,
        video_duration: int = 30
    ) -> Dict[str, Any]:
        """자연어 명령어를 받아 실행"""
        
        print(f"\n{'='*80}")
        print(f"Processing command: {command}")
        print(f"{'='*80}\n")
        
        # 1. LLM으로 작업 계획 수립
        print("Step 1: Planning tasks with LLM...")
        task_plans, num_agents, analysis = self.llm_planner.parse_natural_language_command(command, context)
        
        print(f"\nAnalysis: {analysis}")
        print(f"Number of agents needed: {num_agents}")
        print(f"Number of tasks: {len(task_plans)}\n")
        
        # 2. 에이전트 생성 및 초기화
        print("Step 2: Creating and initializing agents...")
        num_agents = min(num_agents, max_agents)  # 최대 에이전트 수 제한
        
        for i in range(num_agents):
            agent_id = f"agent_{i+1}"
            config = AgentConfig(
                agent_id=agent_id,
                scene=scene
            )
            agent = AI2THORAgent(config)
            agent.initialize()
            self.agents[agent_id] = agent
        
        # 시각화 초기화 (옵션)
        if enable_video and self.visualizer:
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            self.visualizer.initialize_top_view_camera(scene, num_agents)
            self.visualizer.setup_video_writers(self.agents, timestamp)
            print(f"✅ 비디오 녹화 활성화 ({video_duration}초)")
        
        # 3. 작업 할당 및 병렬 실행
        print("\nStep 3: Executing tasks in parallel...")
        
        # 우선순위와 의존성에 따라 작업 정렬
        sorted_tasks = sorted(task_plans, key=lambda t: (-t.priority, len(t.dependencies)))
        
        results = []
        frame_count = 0
        start_time = time.time()
        
        with ThreadPoolExecutor(max_workers=num_agents) as executor:
            # agent_id가 지정된 작업들을 해당 에이전트에 할당
            future_to_task = {}
            
            for task_plan in sorted_tasks:
                # agent_id가 없으면 사용 가능한 에이전트에 할당
                if not task_plan.agent_id or task_plan.agent_id not in self.agents:
                    available_agents = [aid for aid in self.agents.keys() 
                                      if aid not in [t.agent_id for t in sorted_tasks if t.agent_id]]
                    if available_agents:
                        task_plan.agent_id = available_agents[0]
                    else:
                        task_plan.agent_id = list(self.agents.keys())[0]
                
                agent = self.agents[task_plan.agent_id]
                future = executor.submit(agent.execute_task_plan, task_plan)
                future_to_task[future] = task_plan
            
            # 결과 수집하면서 지속적으로 비디오 녹화
            completed = 0
            total_tasks = len(future_to_task)
            recording = enable_video  # 녹화 상태 추적
            
            while recording or completed < total_tasks:
                # 비디오 프레임 캡처 (0.1초마다 = 10 FPS)
                if recording and self.visualizer:
                    self.visualizer.capture_frame(self.agents, frame_count)
                    frame_count += 1
                
                # 완료된 작업 확인
                done_futures = [f for f in future_to_task if f.done()]
                for future in done_futures:
                    if future in future_to_task:
                        task_plan = future_to_task.pop(future)
                        try:
                            result = future.result()
                            results.append(result)
                            completed += 1
                        except Exception as e:
                            print(f"Task {task_plan.description} generated an exception: {e}")
                            results.append({
                                'agent_id': task_plan.agent_id,
                                'task_description': task_plan.description,
                                'error': str(e)
                            })
                            completed += 1
                
                # video_duration 초과 시 녹화 중단
                if recording and (time.time() - start_time) >= video_duration:
                    print(f"\n⏱️  비디오 녹화 시간 종료 ({video_duration}초)")
                    recording = False
                
                # 녹화도 끝나고 작업도 모두 완료되면 종료
                if not recording and completed >= total_tasks:
                    break
                
                time.sleep(0.1)  # 10 FPS
        
        # 4. 결과 집계
        print("\nStep 4: Aggregating results...")
        
        summary = {
            'command': command,
            'analysis': analysis,
            'num_agents': num_agents,
            'num_tasks': len(task_plans),
            'task_results': results,
            'agent_final_states': {
                agent_id: agent.get_current_state()
                for agent_id, agent in self.agents.items()
            }
        }
        
        # 통계
        total_actions = sum(r.get('total_actions', 0) for r in results)
        successful_actions = sum(r.get('successful_actions', 0) for r in results)
        
        print(f"\n{'='*80}")
        print(f"Execution Summary:")
        print(f"  Total agents: {num_agents}")
        print(f"  Total tasks: {len(task_plans)}")
        print(f"  Total actions: {total_actions}")
        print(f"  Successful actions: {successful_actions}/{total_actions}")
        print(f"{'='*80}\n")
        
        return summary
    
    def shutdown_all_agents(self):
        """모든 에이전트 및 시각화 종료"""
        print("\nShutting down all agents...")
        
        # 시각화 종료
        if self.visualizer:
            self.visualizer.close()
            self.visualizer = None
        
        # 에이전트 종료
        for agent in self.agents.values():
            agent.shutdown()
        self.agents.clear()


def main():
    """메인 실행 함수"""
    
    # 시스템 초기화
    print("Initializing Multi-Agent System...")
    function_db = FunctionDatabase()
    llm_planner = LLMTaskPlanner(function_db)
    orchestrator = MultiAgentOrchestrator(function_db, llm_planner)
    
    # 예제 명령어 실행
    commands = [
        "Create 3 agents. Have agent 1 move to the kitchen and pick up an apple, agent 2 go to the living room and turn on the TV, and agent 3 explore the bedroom and open all drawers.",
        
        "Spawn 2 agents in a kitchen. Have them work together to prepare a meal: one agent should gather ingredients (apple, bread, egg) from the fridge, while the other agent should clean the counter and turn on the microwave.",
        
        "Create 4 agents to search for all keys in the house. Each agent should explore a different room (kitchen, living room, bedroom, bathroom) and report back any keys they find.",
    ]
    
    try:
        # 첫 번째 명령어만 실행 (예제)
        command = commands[0]
        result = orchestrator.execute_natural_language_command(
            command=command,
            scene="FloorPlan1",
            max_agents=5
        )
        
        # 결과 저장
        output_file = "multi_agent_execution_result.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        
        print(f"\nResults saved to: {output_file}")
        
    finally:
        # 정리
        orchestrator.shutdown_all_agents()


if __name__ == "__main__":
    main()
