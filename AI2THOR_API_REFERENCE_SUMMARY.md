# AI2-THOR API Reference 정리

## 문서 범위
아래 페이지들을 기준으로 정리했다.
- https://ai2thor.allenai.org/ithor/documentation/
- https://ai2thor.allenai.org/ithor/documentation/concepts
- https://ai2thor.allenai.org/ithor/documentation/initialization
- https://ai2thor.allenai.org/ithor/documentation/environment-state
- https://ai2thor.allenai.org/ithor/documentation/scenes
- https://ai2thor.allenai.org/ithor/documentation/objects/object-types
- https://ai2thor.allenai.org/ithor/documentation/objects/set-object-states
- https://ai2thor.allenai.org/ithor/documentation/objects/domain-randomization
- https://ai2thor.allenai.org/ithor/documentation/navigation
- https://ai2thor.allenai.org/ithor/documentation/object-state-changes

---

## 1. Documentation (루트)
- AI2-THOR iTHOR 문서의 진입점.
- 설치/컨트롤러/핵심 개념/액션/환경 상태 페이지로 이어지는 허브.
- 실전에서는 `Controller` 생성 + `controller.step(action=...)` 패턴이 기본.

## 2. Concepts
- 핵심 엔티티:
  - Agent
  - Scene
  - Object
  - Action
  - Event
- 실행 모델:
  - 액션 호출 → 시뮬레이터 상태 전이 → Event 반환
  - Event에 프레임/메타데이터가 포함됨

## 3. Initialization
- `Controller(...)` 초기화 시 자주 쓰는 주요 파라미터:
  - `scene`
  - `agentCount`
  - `width`, `height`
  - `fieldOfView`
  - `visibilityDistance`
  - `gridSize`
  - `rotateStepDegrees`
  - `snapToGrid`
  - `renderImage`, `renderDepthImage`, `renderClassImage`, `renderObjectImage`, `renderInstanceSegmentation`, `renderNormalsImage`, `renderFlowImage`
  - `quality`
  - `platform`, `gpu_device`, `headless`, `x_display`
  - `host`, `port`
  - `commit_id`, `branch`, `local_executable_path`
  - `server_timeout`, `server_start_timeout`
- 초기화 후:
  - `controller.reset(scene=...)`로 씬 변경 가능
- 멀티에이전트:
  - `agentCount > 1`일 때 대부분 액션에 `agentId` 지정 필요

## 4. Environment State
- Event 기반 상태 접근:
  - 단일 에이전트: `controller.last_event`
  - 멀티 에이전트: `controller.last_event.events[i]`
- metadata에 포함되는 핵심 정보:
  - agent pose/rotation/horizon
  - objects 배열(visibility, distance, state flags, objectId 등)
  - `lastActionSuccess`, `errorMessage`, `actionReturn`
- 상태 조회/질의 액션(대표):
  - `GetReachablePositions`
  - `GetInteractablePoses`
  - `GetObjectInFrame`
  - `GetCoordinateFromRaycast`
  - `GetSpawnCoordinatesAboveReceptacle`
- Third-party camera:
  - `AddThirdPartyCamera`
  - `UpdateThirdPartyCamera`
  - `RemoveThirdPartyCamera`
- 실무 팁:
  - 행동 전후로 `lastActionSuccess` 확인 필수
  - 실패 시 `errorMessage`를 로깅해 재시도 정책으로 연결

## 5. Scenes
- iTHOR 씬은 타입별 floorplan 세트로 구성됨.
- 대표 명명 규칙:
  - `FloorPlan1~30` (kitchen)
  - `FloorPlan201~230` (living room)
  - `FloorPlan301~330` (bedroom)
  - `FloorPlan401~430` (bathroom)
- 씬 전환은 `reset` 사용.
- 프로시저럴/커스텀 씬도 문서에서 별도 설명.

## 6. Object Types
- 각 오브젝트는 타입별 속성과 상호작용 가능 플래그를 가짐.
- 문서에서 강조하는 상호작용 속성(예시):
  - `Breakable`
  - `CanBeUsedUp`
  - `Cookable`
  - `Dirtyable`
  - `Fillable`
  - `Moveable`
  - `Openable`
  - `Pickupable`
  - `Receptacle`
  - `Sliceable`
  - `Toggleable`
- 메타데이터 해석에 중요한 개념:
  - `objectId` (씬 내 유니크)
  - bounding box (axis-aligned / object-oriented)
  - position / rotation
  - temperature / material 등 상태 정보
- 실무 팁:
  - 행동 전에 반드시 `pickupable/openable/toggleable/...` 플래그 확인
  - 동일 타입 다수 개체는 `objectId` 단위로 추적

## 7. Set Object States
- 환경 상태를 강제로 세팅하는 유틸성 액션군:
  - `SetObjectPoses`
  - `SetObjectToggles`
  - `SetStateOfAllObjects`
- 주 사용 목적:
  - 실험 초기조건 통제
  - 재현 가능한 데이터셋 생성
  - 상태 기반 evaluation 준비
- 실무 팁:
  - 상태 강제 변경 후 즉시 metadata를 다시 읽어 반영 여부 검증

## 8. Domain Randomization
- 시각적 일반화 강화를 위한 랜덤화 기능:
  - `RandomizeMaterials`
  - `RandomizeColors`
  - 제외 대상 제어(`excludeObjectIds` 계열 옵션)
  - reset으로 원복
- 사용 목적:
  - overfitting 완화
  - texture/color 변화에 대한 정책 강건성 점검

## 9. Navigation
- 이동:
  - `MoveAhead`, `MoveBack`, `MoveLeft`, `MoveRight`
- 회전:
  - `RotateLeft`, `RotateRight`
- 시선:
  - `LookUp`, `LookDown`
- 자세/기타:
  - `Stand`, `Crouch`
  - `JumpAhead`
  - `Teleport`, `TeleportFull`
  - `Done`
- 멀티에이전트:
  - 액션에 `agentId`를 명시해 개별 에이전트 제어
- 실무 팁:
  - 내비게이션은 `GetReachablePositions` + `GetInteractablePoses` + 경로계산 API 조합이 안정적

## 10. Object State Changes
- 객체 상태 전이 액션(핵심):
  - `OpenObject` / `CloseObject`
  - `ToggleObjectOn` / `ToggleObjectOff`
  - `SliceObject`
  - `BreakObject`
  - `CookObject`
  - `DirtyObject` / `CleanObject`
  - `FillObjectWithLiquid` / `EmptyLiquidFromObject`
  - `UseUpObject`
- 공통 주의점:
  - object type이 해당 액션을 지원해야 함
  - 가시성/거리/충돌/현재 상태에 따라 실패 가능
  - 성공 여부는 `lastActionSuccess`로 최종 판단

---

## SMART-LLM 구현 관점 체크리스트
- Stage 1(분해) 전:
  - 씬 객체 목록/속성 확보
  - 로봇별 스킬 스키마 정의
- Stage 2(연합):
  - 서브태스크 요구 스킬 추출
  - 단일 로봇 가능 여부 검사
  - 불가 시 팀 조합 탐색
- Stage 3(할당):
  - 병렬 가능한 서브태스크는 thread/group으로 배치
  - 순서 제약은 dependency로 명시
- Stage 4(실행):
  - 액션 실패 핸들링(retry/replan/fallback)
  - 목표상태 검증(GCR 계산용)

---

## 참고
- 위 문서는 제공된 레퍼런스 URL 범위를 기준으로 실무 구현 관점에서 재구성한 요약본이다.
- 원문 세부 파라미터/예제 코드는 각 공식 페이지의 최신 내용을 함께 확인하는 것을 권장.

