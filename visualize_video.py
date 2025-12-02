"""
AI2THOR iTHOR 영상 시각화
에이전트의 움직임을 영상(MP4)으로 저장합니다.
"""

from ai2thor.controller import Controller
import cv2
import numpy as np
import os
from datetime import datetime

def create_output_dir():
    """출력 디렉토리 생성"""
    output_dir = "output_videos"
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    return output_dir

def visualize_to_video():
    """네비게이션 과정을 영상으로 저장"""
    print("=== AI2THOR iTHOR 영상 시각화 ===\n")
    
    output_dir = create_output_dir()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    video_filename = os.path.join(output_dir, f"navigation_{timestamp}.mp4")
    
    # Controller 초기화
    print("Controller 초기화 중...")
    controller = Controller(
        scene="FloorPlan1",
        width=1280,
        height=720,
        fieldOfView=90
    )
    
    print(f"✓ 씬 로드됨: {controller.last_event.metadata['sceneName']}")
    print(f"✓ 해상도: 1280x720\n")
    
    # 비디오 작성기 초기화
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    fps = 30  # 초당 30프레임
    video = cv2.VideoWriter(video_filename, fourcc, fps, (1280, 720))
    
    # 초기 프레임 저장 (2초간 정지)
    event = controller.step("Pass")
    initial_frame = cv2.cvtColor(event.frame, cv2.COLOR_RGB2BGR)
    
    # 텍스트 오버레이 추가
    frame_with_text = add_text_overlay(initial_frame, "Initial Position", 0)
    for _ in range(fps * 2):  # 2초
        video.write(frame_with_text)
    
    print("영상 녹화 시작...\n")
    
    # 액션 시퀀스 (각 액션마다 1초씩 표시)
    actions = [
        ("MoveAhead", "전진", 1),
        ("RotateRight", "오른쪽 회전", 1),
        ("MoveAhead", "전진", 1),
        ("MoveAhead", "전진", 1),
        ("RotateRight", "오른쪽 회전", 1),
        ("MoveAhead", "전진", 1),
        ("RotateLeft", "왼쪽 회전", 1),
        ("MoveAhead", "전진", 1),
        ("LookUp", "위를 봄", 1),
        ("RotateRight", "360도 회전 (1/4)", 1),
        ("RotateRight", "360도 회전 (2/4)", 1),
        ("RotateRight", "360도 회전 (3/4)", 1),
        ("RotateRight", "360도 회전 (4/4)", 1),
        ("LookDown", "아래를 봄", 1),
        ("LookDown", "정면으로", 1),
    ]
    
    frame_count = 0
    
    for i, (action, description, hold_seconds) in enumerate(actions, 1):
        event = controller.step(action=action)
        
        if event.metadata['lastActionSuccess']:
            print(f"✓ {i}. {description} ({action})")
            
            # 프레임을 BGR로 변환 (OpenCV는 BGR 사용)
            frame = cv2.cvtColor(event.frame, cv2.COLOR_RGB2BGR)
            frame_with_text = add_text_overlay(frame, f"{i}. {description}", frame_count)
            
            # 지정된 시간만큼 프레임 유지
            for _ in range(fps * hold_seconds):
                video.write(frame_with_text)
                frame_count += 1
        else:
            print(f"✗ {i}. {description} ({action}) - 실패")
            print(f"   오류: {event.metadata['errorMessage']}")
            
            # 실패해도 현재 뷰를 잠시 유지
            frame = cv2.cvtColor(event.frame, cv2.COLOR_RGB2BGR)
            frame_with_text = add_text_overlay(frame, f"{i}. {description} (Failed)", frame_count)
            for _ in range(fps * 1):
                video.write(frame_with_text)
                frame_count += 1
    
    # 마지막 프레임 2초간 유지
    final_frame = add_text_overlay(frame, "Complete!", frame_count)
    for _ in range(fps * 2):
        video.write(final_frame)
    
    # 정리
    video.release()
    controller.stop()
    
    print(f"\n✓ 영상 저장 완료!")
    print(f"   파일: {video_filename}")
    print(f"   총 프레임: {frame_count}")
    print(f"   길이: ~{frame_count // fps}초")
    
    return video_filename

def add_text_overlay(frame, text, frame_number):
    """프레임에 텍스트 오버레이 추가"""
    frame_copy = frame.copy()
    
    # 반투명 배경 추가
    overlay = frame_copy.copy()
    cv2.rectangle(overlay, (10, 10), (600, 100), (0, 0, 0), -1)
    cv2.addWeighted(overlay, 0.6, frame_copy, 0.4, 0, frame_copy)
    
    # 텍스트 추가
    font = cv2.FONT_HERSHEY_SIMPLEX
    cv2.putText(frame_copy, text, (20, 50), font, 1.2, (255, 255, 255), 2, cv2.LINE_AA)
    cv2.putText(frame_copy, f"Frame: {frame_number}", (20, 85), font, 0.6, (200, 200, 200), 1, cv2.LINE_AA)
    
    return frame_copy

def interactive_video_recording():
    """대화형 영상 녹화"""
    print("=== AI2THOR iTHOR 대화형 영상 녹화 ===\n")
    
    output_dir = create_output_dir()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    video_filename = os.path.join(output_dir, f"interactive_{timestamp}.mp4")
    
    controller = Controller(
        scene="FloorPlan1",
        width=1280,
        height=720
    )
    
    print("컨트롤:")
    print("  w: 전진 (MoveAhead)")
    print("  s: 후진 (MoveBack)")
    print("  a: 왼쪽 회전 (RotateLeft)")
    print("  d: 오른쪽 회전 (RotateRight)")
    print("  i: 위를 봄 (LookUp)")
    print("  k: 아래를 봄 (LookDown)")
    print("  예: w,w,d,w,a,w (쉼표로 구분)\n")
    
    user_input = input("명령을 입력하세요: ").lower()
    
    # 비디오 작성기 초기화
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    fps = 30
    video = cv2.VideoWriter(video_filename, fourcc, fps, (1280, 720))
    
    action_map = {
        'w': ('MoveAhead', '전진'),
        's': ('MoveBack', '후진'),
        'a': ('RotateLeft', '왼쪽 회전'),
        'd': ('RotateRight', '오른쪽 회전'),
        'i': ('LookUp', '위를 봄'),
        'k': ('LookDown', '아래를 봄')
    }
    
    # 초기 프레임
    event = controller.step("Pass")
    frame = cv2.cvtColor(event.frame, cv2.COLOR_RGB2BGR)
    frame_with_text = add_text_overlay(frame, "Start", 0)
    for _ in range(fps * 1):
        video.write(frame_with_text)
    
    frame_count = 0
    print("\n녹화 시작...\n")
    
    for char in user_input.replace(',', '').replace(' ', ''):
        if char in action_map:
            action, description = action_map[char]
            event = controller.step(action=action)
            
            if event.metadata['lastActionSuccess']:
                frame_count += 1
                frame = cv2.cvtColor(event.frame, cv2.COLOR_RGB2BGR)
                frame_with_text = add_text_overlay(frame, description, frame_count)
                
                for _ in range(fps * 1):  # 각 액션마다 1초
                    video.write(frame_with_text)
                
                print(f"✓ {description} ({action})")
            else:
                print(f"✗ {description} ({action}) - 실패")
    
    video.release()
    controller.stop()
    
    print(f"\n✓ 영상 저장 완료: {video_filename}")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "interactive":
        interactive_video_recording()
    else:
        visualize_to_video()
