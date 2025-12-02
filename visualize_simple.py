"""
AI2THOR iTHOR 실시간 시각화 예제 (간단 버전)
에이전트가 움직이는 동안 화면을 저장하고 확인합니다.
"""

from ai2thor.controller import Controller
import matplotlib.pyplot as plt
from PIL import Image
import os

def create_output_dir():
    """출력 디렉토리 생성"""
    output_dir = "output_images"
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    return output_dir

def simple_visualization():
    """간단한 시각화 예제"""
    print("=== AI2THOR iTHOR 시각화 예제 ===\n")
    
    output_dir = create_output_dir()
    
    # Controller 초기화
    print("Controller 초기화 중...")
    controller = Controller(
        scene="FloorPlan1",
        width=800,
        height=600,
        renderDepthImage=False,
        renderInstanceSegmentation=False
    )
    
    # 첫 이벤트 가져오기
    event = controller.step("Pass")  # 아무것도 하지 않는 액션
    
    print(f"✓ 씬 로드됨: {event.metadata['sceneName']}")
    print(f"✓ 이미지 크기: {event.frame.shape}\n")
    
    # 초기 프레임 저장
    img = Image.fromarray(event.frame)
    img.save(os.path.join(output_dir, "frame_00_initial.png"))
    print("저장됨: frame_00_initial.png")
    
    # 액션 실행
    actions = [
        ("MoveAhead", "전진"),
        ("MoveAhead", "전진"),
        ("RotateRight", "오른쪽 90도 회전"),
        ("MoveAhead", "전진"),
        ("RotateRight", "오른쪽 90도 회전"),
        ("MoveAhead", "전진"),
        ("LookUp", "위를 봄"),
        ("LookDown", "정면으로"),
    ]
    
    print("\n액션 실행 중...\n")
    saved_images = []
    
    for i, (action, description) in enumerate(actions, 1):
        event = controller.step(action=action)
        
        if event.metadata['lastActionSuccess']:
            # 프레임 저장
            filename = f"frame_{i:02d}_{action.lower()}.png"
            filepath = os.path.join(output_dir, filename)
            img = Image.fromarray(event.frame)
            img.save(filepath)
            
            saved_images.append((filepath, f"{i}. {description}"))
            print(f"✓ {i}. {description} ({action})")
            print(f"   → {filename}")
        else:
            print(f"✗ {i}. {description} ({action}) - 실패")
            print(f"   오류: {event.metadata['errorMessage']}")
    
    # 통합 이미지 생성
    print(f"\n총 {len(saved_images) + 1}개의 프레임 저장 완료!")
    print("\n통합 시각화 생성 중...")
    
    # 모든 이미지를 그리드로 표시
    n_images = len(saved_images) + 1
    cols = 3
    rows = (n_images + cols - 1) // cols
    
    fig, axes = plt.subplots(rows, cols, figsize=(15, 5*rows))
    fig.suptitle('AI2THOR iTHOR - 에이전트 시야 변화', fontsize=16, fontweight='bold')
    
    # axes를 1차원 배열로 변환
    if rows == 1:
        axes = axes.reshape(-1) if cols > 1 else [axes]
    else:
        axes = axes.flatten()
    
    # 초기 이미지
    img = Image.open(os.path.join(output_dir, "frame_00_initial.png"))
    axes[0].imshow(img)
    axes[0].set_title("0. 초기 위치", fontsize=10)
    axes[0].axis('off')
    
    # 나머지 이미지들
    for idx, (img_path, title) in enumerate(saved_images, 1):
        img = Image.open(img_path)
        axes[idx].imshow(img)
        axes[idx].set_title(title, fontsize=10)
        axes[idx].axis('off')
    
    # 빈 subplot 숨기기
    for idx in range(n_images, len(axes)):
        axes[idx].axis('off')
    
    plt.tight_layout()
    
    # 저장
    grid_path = os.path.join(output_dir, "visualization_grid.png")
    plt.savefig(grid_path, dpi=150, bbox_inches='tight')
    print(f"✓ 통합 이미지 저장: {grid_path}")
    
    # 화면에 표시
    print("\n이미지 창이 열립니다...")
    plt.show()
    
    controller.stop()
    print(f"\n완료! 모든 이미지는 '{output_dir}/' 폴더에 있습니다.")

if __name__ == "__main__":
    simple_visualization()
