"""
AI2THOR iTHOR 설정 테스트 스크립트
이 스크립트는 AI2THOR가 올바르게 설치되었는지 확인합니다.
"""

from ai2thor.controller import Controller

def test_basic_setup():
    """기본 설정 테스트"""
    print("AI2THOR Controller 초기화 중...")
    print("첫 실행 시 약 500MB의 게임 환경이 ~/.ai2thor 에 다운로드됩니다.")
    
    # Controller 초기화
    controller = Controller()
    
    print("✓ Controller 초기화 완료!")
    
    # 간단한 액션 실행
    print("\n액션 실행 테스트: MoveAhead")
    event = controller.step("MoveAhead")
    
    print(f"✓ 액션 실행 성공!")
    print(f"  - 이벤트 메타데이터 수신: {event.metadata is not None}")
    print(f"  - 현재 씬: {event.metadata.get('sceneName', 'N/A')}")
    
    # Controller 종료
    controller.stop()
    print("\n✓ 모든 테스트 완료!")
    print("\n설정이 성공적으로 완료되었습니다!")

if __name__ == "__main__":
    test_basic_setup()
