# AI2THOR iTHOR 개발 환경

AI2THOR iTHOR 환경이 설정되었습니다.

## 설치된 환경

- **Python**: 3.13.2 (Virtual Environment)
- **AI2THOR**: 5.0.0
- **위치**: `/Users/jaehwan/Desktop/JaeHwan/workspace/ai2thor`

## 의존성 설치

```bash
pip install -r requirements.txt
```

## 요구사항

- OS: macOS 10.9+ 또는 Ubuntu 14.04+
- Python: 3.5+
- CPU: SSE2 instruction set 지원
- Graphics Card: DX9 (shader model 3.0) 또는 DX11 with feature level 9.3

## 파일 설명

### `test_setup.py`
설치가 올바르게 되었는지 확인하는 테스트 스크립트입니다.

실행:
```bash
/Users/jaehwan/Desktop/JaeHwan/workspace/ai2thor/.venv/bin/python test_setup.py
```

### `example_basic.py`
기본적인 에이전트 네비게이션과 환경 상호작용 예제입니다.

실행:
```bash
/Users/jaehwan/Desktop/JaeHwan/workspace/ai2thor/.venv/bin/python example_basic.py
```

### `visualize_simple.py`
에이전트의 시야를 이미지로 캡처하고 그리드로 시각화합니다.

실행:
```bash
.venv/bin/python visualize_simple.py
```

출력: `output_images/` 폴더에 개별 프레임과 통합 이미지 저장

### `visualize_video.py`
에이전트의 움직임을 MP4 영상으로 녹화합니다.

실행:
```bash
.venv/bin/python visualize_video.py
```

대화형 모드:
```bash
.venv/bin/python visualize_video.py interactive
```

출력: `output_videos/` 폴더에 MP4 영상 저장

## 주요 기능

### 1. Controller 초기화
```python
from ai2thor.controller import Controller
controller = Controller()
```

### 2. 헤드리스 모드 (서버 환경)
화면 없이 실행하려면:
```python
from ai2thor.controller import Controller
from ai2thor.platform import CloudRendering

controller = Controller(platform=CloudRendering)
```

### 3. 특정 씬 로드
```python
controller = Controller(scene="FloorPlan1")
```

### 4. 액션 실행
```python
event = controller.step("MoveAhead")
event = controller.step("RotateRight")
event = controller.step("LookUp")
```

## 첫 실행 시 주의사항

- 첫 Controller 초기화 시 약 **500MB**의 게임 환경이 `~/.ai2thor`에 다운로드됩니다.
- 다운로드는 최초 1회만 진행됩니다.

## 유용한 링크

- [공식 문서](https://ai2thor.allenai.org/ithor/documentation/)
- [API 참조](https://ai2thor.allenai.org/ithor/documentation/)
- [데모](https://ai2thor.allenai.org/demo)
- [GitHub](https://github.com/allenai/ai2thor)
- [Google Colab 버전](https://github.com/allenai/ai2thor-colab)

## 다음 단계

1. `test_setup.py`를 실행하여 설치 확인
2. `example_basic.py`로 기본 사용법 학습
3. [공식 문서](https://ai2thor.allenai.org/ithor/documentation/)에서 더 많은 기능 탐색

## 추가 설정

### 특정 커밋 버전 설치
```bash
pip install --extra-index-url https://ai2thor-pypi.allenai.org ai2thor==0+COMMIT_ID
```

### Docker 사용
[AI2-THOR Docker](https://github.com/allenai/ai2thor-docker) 참조
