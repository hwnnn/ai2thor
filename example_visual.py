"""
AI2THOR iTHOR 시각화 예제
에이전트의 시야를 이미지로 저장하고 시각화합니다.
"""

from ai2thor.controller import Controller
import matplotlib.pyplot as plt
from PIL import Image
import numpy as np
import os

def create_output_dir():
    """출력 디렉토리 생성"""
    output_dir = "output_images"
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    return output_dir

def save_frame(frame, filename, output_dir):
    """프레임을 이미지로 저장"""
    img = Image.fromarray(frame)
    filepath = os.path.join(output_dir, filename)
    img.save(filepath)
    print(f"  저장됨: {filepath}")
    return filepath

def visualize_navigation():
    """네비게이션 과정을 시각화"""
    print("=== AI2THOR iTHOR 시각화 예제 ===\n")
    
    output_dir = create_output_dir()
    
    # Controller 초기화 (더 높은 해상도로)
    controller = Controller(
        agentMode="default",
        visibilityDistance=1.5,
        scene="FloorPlan1",
        width=800,
        height=600,
        fieldOfView=90
    )
    
    print(f"씬 로드됨: {controller.last_event.metadata['sceneName']}")
    print(f"이미지 크기: {controller.last_event.frame.shape}\n")
    
    # 초기 프레임 저장
    save_frame(controller.last_event.frame, "frame_00_initial.png", output_dir)
    
    # 액션 시퀀스 정의
    actions = [
        ("MoveAhead", "전진"),
        ("RotateRight", "오른쪽 회전"),
        ("MoveAhead", "전진"),
        ("RotateRight", "오른쪽 회전"),
        ("MoveAhead", "전진"),
        ("LookUp", "위를 봄"),
        ("LookDown", "아래를 봄"),
    ]
    
    print("액션 실행 및 프레임 저장:")
    saved_images = []
    
    for i, (action, description) in enumerate(actions, 1):
        event = controller.step(action=action)
        success = event.metadata['lastActionSuccess']
        status = "✓" if success else "✗"
        
        print(f"{i}. {description} ({action}): {status}")
        
        if success:
            filename = f"frame_{i:02d}_{action.lower()}.png"
            filepath = save_frame(event.frame, filename, output_dir)
            saved_images.append((filepath, f"{i}. {description}"))
        else:
            print(f"   오류: {event.metadata['errorMessage']}")
    
    # 모든 이미지를 한 화면에 표시
    print(f"\n총 {len(saved_images)} 개의 프레임 저장 완료")
    print("\n통합 시각화 생성 중...")
    
    create_image_grid(saved_images, output_dir)
    
    controller.stop()
    print(f"\n✓ 완료! 이미지는 '{output_dir}/' 폴더에 저장되었습니다.")

def create_image_grid(image_paths, output_dir):
    """여러 이미지를 그리드로 표시"""
    n_images = len(image_paths)
    cols = 3
    rows = (n_images + cols - 1) // cols
    
    fig, axes = plt.subplots(rows, cols, figsize=(15, 5*rows))
    fig.suptitle('AI2THOR iTHOR - 에이전트 시야 변화', fontsize=16, fontweight='bold')
    
    # axes를 1차원 배열로 변환
    if rows == 1:
        axes = [axes] if cols == 1 else axes
    else:
        axes = axes.flatten()
    
    for idx, (img_path, title) in enumerate(image_paths):
        img = Image.open(img_path)
        axes[idx].imshow(img)
        axes[idx].set_title(title, fontsize=10)
        axes[idx].axis('off')
    
    # 빈 subplot 숨기기
    for idx in range(n_images, len(axes)):
        axes[idx].axis('off')
    
    plt.tight_layout()
    
    # 통합 이미지 저장
    grid_path = os.path.join(output_dir, "visualization_grid.png")
    plt.savefig(grid_path, dpi=150, bbox_inches='tight')
    print(f"  통합 이미지 저장: {grid_path}")
    
    # 화면에 표시
    plt.show()

def interactive_exploration():
    """대화형 탐험 모드"""
    print("=== AI2THOR iTHOR 대화형 탐험 ===\n")
    
    output_dir = create_output_dir()
    
    controller = Controller(
        scene="FloorPlan1",
        width=800,
        height=600
    )
    
    print("컨트롤:")
    print("  w: 전진 (MoveAhead)")
    print("  s: 후진 (MoveBack)")
    print("  a: 왼쪽 회전 (RotateLeft)")
    print("  d: 오른쪽 회전 (RotateRight)")
    print("  i: 위를 봄 (LookUp)")
    print("  k: 아래를 봄 (LookDown)")
    print("  q: 종료\n")
    
    frame_count = 0
    save_frame(controller.last_event.frame, f"interactive_{frame_count:03d}.png", output_dir)
    
    action_map = {
        'w': 'MoveAhead',
        's': 'MoveBack',
        'a': 'RotateLeft',
        'd': 'RotateRight',
        'i': 'LookUp',
        'k': 'LookDown'
    }
    
    print("명령을 입력하세요 (예: w,w,d,w,q):")
    user_input = input("> ").lower()
    
    for char in user_input.replace(',', '').replace(' ', ''):
        if char == 'q':
            break
        
        if char in action_map:
            action = action_map[char]
            event = controller.step(action=action)
            
            if event.metadata['lastActionSuccess']:
                frame_count += 1
                save_frame(event.frame, f"interactive_{frame_count:03d}.png", output_dir)
                print(f"✓ {action} 실행됨 (프레임 {frame_count})")
            else:
                print(f"✗ {action} 실패: {event.metadata['errorMessage']}")
    
    controller.stop()
    print(f"\n✓ {frame_count + 1}개의 프레임이 '{output_dir}/'에 저장되었습니다.")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "interactive":
        interactive_exploration()
    else:
        visualize_navigation()
