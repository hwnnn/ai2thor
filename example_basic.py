"""
AI2THOR iTHOR 기본 예제
간단한 에이전트 동작과 환경 상호작용 예제
"""

from ai2thor.controller import Controller

def basic_navigation_example():
    """기본 네비게이션 예제"""
    print("=== AI2THOR iTHOR 기본 예제 ===\n")
    
    # Controller 초기화
    controller = Controller(
        agentMode="default",
        visibilityDistance=1.5,
        scene="FloorPlan1",
        
        # 헤드리스 모드로 실행하려면 아래 주석을 해제하세요
        # platform=CloudRendering
    )
    
    print(f"씬 로드됨: {controller.last_event.metadata['sceneName']}")
    print(f"에이전트 위치: {controller.last_event.metadata['agent']['position']}\n")
    
    # 여러 액션 수행
    actions = [
        "MoveAhead",
        "RotateRight",
        "MoveAhead",
        "RotateLeft",
        "LookUp",
        "LookDown"
    ]
    
    print("액션 시퀀스 실행:")
    for i, action in enumerate(actions, 1):
        event = controller.step(action=action)
        success = event.metadata['lastActionSuccess']
        status = "✓" if success else "✗"
        print(f"  {i}. {action}: {status}")
        
        if not success:
            print(f"     오류 메시지: {event.metadata['errorMessage']}")
    
    # 씬의 객체 정보 가져오기
    print(f"\n씬 내 객체 수: {len(controller.last_event.metadata['objects'])}")
    print("\n일부 객체 목록:")
    for obj in controller.last_event.metadata['objects'][:5]:
        print(f"  - {obj['objectType']} (ID: {obj['objectId']})")
    
    # Controller 종료
    controller.stop()
    print("\n프로그램 종료")

if __name__ == "__main__":
    basic_navigation_example()
