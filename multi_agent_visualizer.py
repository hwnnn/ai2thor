"""
Multi-Agent Visualization System
여러 에이전트의 동작을 동시에 시각화하는 시스템
- 탑뷰 카메라: 모든 에이전트를 위에서 내려다보는 시점
- 에이전트 1인칭 뷰: 각 에이전트의 시점
"""

import cv2
import numpy as np
from typing import Dict, List, Tuple
from ai2thor.controller import Controller
import os
from datetime import datetime
from multi_agent_system import AI2THORAgent


class MultiAgentVisualizer:
    """멀티-에이전트 시각화 클래스"""
    
    def __init__(self, output_dir: str = "output_videos"):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
        
        self.top_view_controller = None  # Topview 전용 별도 controller
        self.video_writers = {}
        self.fps = 6  # 초당 6프레임 (더 느린 재생)
        
    def initialize_top_view_camera(self, scene: str, agent_count: int = 3):
        """탑뷰 카메라 초기화 (별도 Controller 사용)"""
        print("📹 탑뷰 카메라 초기화 중...")
        
        # Topview 전용 Controller 생성 (높은 위치에서 아래를 바라봄)
        self.top_view_controller = Controller(
            scene=scene,
            width=1920,
            height=1080,
            fieldOfView=90,
            agentMode='default'
        )
        
        # 씬 중앙 위치 계산
        event = self.top_view_controller.step("GetReachablePositions")
        reachable_positions = event.metadata['actionReturn']
        
        if reachable_positions:
            center_x = float(np.mean([p['x'] for p in reachable_positions]))
            center_z = float(np.mean([p['z'] for p in reachable_positions]))
            
            # 높은 위치에서 아래를 바라보도록 초기화
            # y=5.0으로 충분히 높게, rotation x=90으로 아래를 봄
            self.top_view_controller.step(
                action='Initialize',
                gridSize=0.25,
                cameraY=5.0,  # 카메라 높이
                makeAgentsVisible=False  # agent를 보이지 않게
            )
            
            # 중앙 위치로 텔레포트
            self.top_view_controller.step(
                action='Teleport',
                position=dict(x=center_x, y=5.0, z=center_z),
                rotation=dict(x=90, y=0, z=0),  # 아래를 바라봄
                horizon=0,
                standing=True
            )
            
            # 프레임 확인
            event = self.top_view_controller.step("Pass")
            if event.frame is not None:
                avg_pixel = np.mean(event.frame)
                print(f"✓ 탑뷰 카메라 위치: ({center_x:.2f}, 5.0, {center_z:.2f})")
                print(f"✓ 첫 프레임 평균 픽셀: {avg_pixel:.2f}")
            else:
                print("⚠️ 탑뷰 프레임을 가져올 수 없습니다")
        
        return self.top_view_controller
    
    def setup_video_writers(self, agents: Dict[str, AI2THORAgent], timestamp: str = None):
        """비디오 작성기 설정"""
        if timestamp is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # mp4v 코덱 사용 (MP4 컨테이너와 완벽 호환)
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        
        # 탑뷰 비디오
        top_view_path = os.path.join(self.output_dir, f"topview_{timestamp}.mp4")
        writer = cv2.VideoWriter(top_view_path, fourcc, self.fps, (1920, 1080))
        if writer.isOpened():
            self.video_writers['topview'] = writer
            print(f"✓ 탑뷰 비디오: {top_view_path}")
        else:
            print(f"✗ 탑뷰 비디오 생성 실패: {top_view_path}")
        
        # 각 에이전트 1인칭 뷰
        for agent_id in agents.keys():
            agent_path = os.path.join(self.output_dir, f"{agent_id}_pov_{timestamp}.mp4")
            writer = cv2.VideoWriter(agent_path, fourcc, self.fps, (800, 600))
            if writer.isOpened():
                self.video_writers[agent_id] = writer
                print(f"✓ {agent_id} POV: {agent_path}")
            else:
                print(f"✗ {agent_id} POV 생성 실패: {agent_path}")
        
        # 통합 뷰 (탑뷰 + 모든 에이전트 POV를 한 화면에)
        combined_path = os.path.join(self.output_dir, f"combined_{timestamp}.mp4")
        writer = cv2.VideoWriter(combined_path, fourcc, self.fps, (1920, 1080))
        if writer.isOpened():
            self.video_writers['combined'] = writer
            print(f"✓ 통합 뷰: {combined_path}")
        else:
            print(f"✗ 통합 뷰 생성 실패: {combined_path}")
    
    def capture_frame(self, agents: Dict[str, AI2THORAgent], frame_count: int = 0):
        """현재 프레임 캡처 (안전 장치 강화)"""
        # 탑뷰 프레임 (별도 Controller 사용)
        if self.top_view_controller and 'topview' in self.video_writers:
            try:
                # Pass 액션으로 상태 업데이트
                event = self.top_view_controller.step("Pass")
                if event.frame is not None and len(event.frame.shape) == 3:
                    top_frame = cv2.cvtColor(event.frame, cv2.COLOR_RGB2BGR)
                else:
                    top_frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
            except Exception as e:
                # 에러 시 빈 프레임 생성
                top_frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
            
            # 에이전트 위치 마킹
            top_frame = self._mark_agent_positions(top_frame, agents)
            
            # 프레임 정보 오버레이
            top_frame = self._add_overlay(
                top_frame, 
                f"Top View - Frame {frame_count}",
                position='top'
            )
            
            # 프레임 쓰기 전 검증
            if self.video_writers['topview'].isOpened():
                self.video_writers['topview'].write(top_frame)
        
        # 각 에이전트 1인칭 뷰
        agent_frames = []
        for agent_id, agent in agents.items():
            if agent.controller and agent_id in self.video_writers:
                try:
                    event = agent.controller.step("Pass")
                    if event.frame is not None and len(event.frame.shape) == 3:
                        pov_frame = cv2.cvtColor(event.frame, cv2.COLOR_RGB2BGR)
                    else:
                        pov_frame = np.zeros((600, 800, 3), dtype=np.uint8)
                except Exception as e:
                    # 에러 시 빈 프레임 생성
                    pov_frame = np.zeros((600, 800, 3), dtype=np.uint8)
                
                # 에이전트 정보 오버레이
                pov_frame = self._add_overlay(
                    pov_frame,
                    f"{agent_id} POV - Frame {frame_count}",
                    position='top'
                )
                
                # 프레임 쓰기 전 검증
                if self.video_writers[agent_id].isOpened():
                    self.video_writers[agent_id].write(pov_frame)
                
                # 통합 뷰용으로 리사이즈
                resized = cv2.resize(pov_frame, (640, 480))
                agent_frames.append(resized)
        
        # 통합 뷰 생성
        if agent_frames and 'combined' in self.video_writers:
            combined = self._create_combined_view(top_frame, agent_frames, frame_count)
            if self.video_writers['combined'].isOpened():
                self.video_writers['combined'].write(combined)
    
    def _mark_agent_positions(self, frame: np.ndarray, agents: Dict[str, AI2THORAgent]) -> np.ndarray:
        """탑뷰에 에이전트 위치 표시"""
        frame_copy = frame.copy()
        
        colors = {
            'agent_1': (0, 255, 0),    # 초록
            'agent_2': (255, 0, 0),    # 파랑
            'agent_3': (0, 0, 255),    # 빨강
            'agent_4': (255, 255, 0),  # 청록
            'agent_5': (255, 0, 255),  # 마젠타
        }
        
        for agent_id, agent in agents.items():
            if agent.controller:
                try:
                    event = agent.controller.step("Pass")
                    pos = event.metadata['agent']['position']
                    
                    # 3D 위치를 2D 화면 좌표로 변환 (간단한 투영)
                    # 실제 씬 크기에 따라 스케일 조정 필요
                    x_screen = int((pos['x'] + 5) * 100)  # 스케일 조정
                    y_screen = int((pos['z'] + 5) * 100)
                    
                    # 화면 범위 내로 제한
                    x_screen = max(0, min(x_screen, frame.shape[1] - 1))
                    y_screen = max(0, min(y_screen, frame.shape[0] - 1))
                    
                    # 원과 텍스트 그리기
                    color = colors.get(agent_id, (255, 255, 255))
                    cv2.circle(frame_copy, (x_screen, y_screen), 20, color, -1)
                    cv2.circle(frame_copy, (x_screen, y_screen), 22, (255, 255, 255), 2)
                    
                    # 에이전트 ID 표시
                    cv2.putText(
                        frame_copy,
                        agent_id.replace('agent_', 'A'),
                        (x_screen - 10, y_screen + 5),
                        cv2.FONT_HERSHEY_DUPLEX,
                        0.6,
                        (255, 255, 255),
                        2
                    )
                except Exception as e:
                    # 컨트롤러가 닫혔거나 오류 발생 시 무시
                    pass
        
        return frame_copy
    
    def _add_overlay(self, frame: np.ndarray, text: str, position: str = 'top') -> np.ndarray:
        """프레임에 텍스트 오버레이 추가"""
        frame_copy = frame.copy()
        
        # 반투명 배경
        overlay = frame_copy.copy()
        if position == 'top':
            cv2.rectangle(overlay, (0, 0), (frame.shape[1], 60), (0, 0, 0), -1)
        else:
            cv2.rectangle(overlay, (0, frame.shape[0] - 60), (frame.shape[1], frame.shape[0]), (0, 0, 0), -1)
        
        frame_copy = cv2.addWeighted(overlay, 0.7, frame_copy, 0.3, 0)
        
        # 텍스트
        y_pos = 40 if position == 'top' else frame.shape[0] - 20
        cv2.putText(
            frame_copy,
            text,
            (20, y_pos),
            cv2.FONT_HERSHEY_SIMPLEX,
            1.0,
            (255, 255, 255),
            2
        )
        
        return frame_copy
    
    def _create_combined_view(self, top_frame: np.ndarray, agent_frames: List[np.ndarray], frame_count: int) -> np.ndarray:
        """통합 뷰 생성 (탑뷰 + 모든 에이전트 POV)"""
        # 1920x1080 캔버스 생성
        canvas = np.zeros((1080, 1920, 3), dtype=np.uint8)
        
        # 탑뷰를 왼쪽에 배치 (1280x1080)
        top_resized = cv2.resize(top_frame, (1280, 1080))
        canvas[:, :1280] = top_resized
        
        # 에이전트 POV를 오른쪽에 그리드로 배치 (640x1080 공간)
        pov_width = 640
        pov_height = 360  # 3개까지 세로로 배치 가능
        
        for i, agent_frame in enumerate(agent_frames[:3]):  # 최대 3개
            y_start = i * pov_height
            y_end = y_start + pov_height
            
            resized = cv2.resize(agent_frame, (pov_width, pov_height))
            canvas[y_start:y_end, 1280:] = resized
        
        # 프레임 카운트 추가
        cv2.putText(
            canvas,
            f"Frame: {frame_count}",
            (1300, 50),
            cv2.FONT_HERSHEY_SIMPLEX,
            1.0,
            (255, 255, 255),
            2
        )
        
        return canvas
    
    def close(self):
        """모든 리소스 정리 (안전하게)"""
        print("\n📹 비디오 작성 완료 중...")
        
        for name, writer in self.video_writers.items():
            try:
                if writer and writer.isOpened():
                    writer.release()
                    print(f"✓ {name} 저장 완료")
            except Exception as e:
                print(f"✗ {name} 저장 중 오류: {e}")
        
        # 탑뷰 카메라 종료
        if self.top_view_controller:
            try:
                self.top_view_controller.stop()
                print("✓ 탑뷰 카메라 종료")
            except Exception as e:
                print(f"✗ 탑뷰 카메라 종료 중 오류: {e}")
        
        try:
            cv2.destroyAllWindows()
        except:
            pass


def visualize_multi_agent_execution(
    agents: Dict[str, AI2THORAgent],
    scene: str = "FloorPlan1",
    duration_seconds: int = 30,
    output_dir: str = "output_videos"
) -> str:
    """
    멀티-에이전트 실행 과정을 시각화
    
    Args:
        agents: 에이전트 딕셔너리
        scene: 씬 이름
        duration_seconds: 녹화 시간 (초)
        output_dir: 출력 디렉토리
    
    Returns:
        출력 디렉토리 경로
    """
    print("\n" + "="*80)
    print("멀티-에이전트 시각화 시작")
    print("="*80 + "\n")
    
    visualizer = MultiAgentVisualizer(output_dir)
    
    try:
        # 탑뷰 카메라 초기화
        visualizer.initialize_top_view_camera(scene, len(agents))
        
        # 비디오 작성기 설정
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        visualizer.setup_video_writers(agents, timestamp)
        
        # 프레임 캡처
        total_frames = duration_seconds * visualizer.fps
        print(f"\n📹 {duration_seconds}초간 녹화 중... (총 {total_frames} 프레임)\n")
        
        for frame_count in range(total_frames):
            visualizer.capture_frame(agents, frame_count)
            
            if frame_count % 10 == 0:
                progress = (frame_count / total_frames) * 100
                print(f"진행률: {progress:.1f}% ({frame_count}/{total_frames} 프레임)")
        
        print("\n✓ 녹화 완료!")
        
    finally:
        visualizer.close()
    
    print(f"\n📁 출력 디렉토리: {output_dir}")
    return output_dir


# 간단한 사용 예제
if __name__ == "__main__":
    from multi_agent_system import FunctionDatabase, LLMTaskPlanner, MultiAgentOrchestrator
    
    print("멀티-에이전트 시각화 테스트")
    print("="*80)
    
    # 시스템 초기화
    function_db = FunctionDatabase()
    llm_planner = LLMTaskPlanner(function_db, use_local=True)
    orchestrator = MultiAgentOrchestrator(function_db, llm_planner)
    
    # 명령어 실행
    command = "3개의 에이전트를 생성해서 각각 다른 방향으로 탐색해."
    
    try:
        # 에이전트 생성
        result = orchestrator.execute_natural_language_command(
            command=command,
            scene="FloorPlan1",
            max_agents=3
        )
        
        # 시각화
        visualize_multi_agent_execution(
            agents=orchestrator.agents,
            scene="FloorPlan1",
            duration_seconds=30
        )
        
    finally:
        orchestrator.shutdown_all_agents()
