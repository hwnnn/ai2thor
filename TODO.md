# TODO: SMART-LLM 논문 정합 구현 계획

## 0. 리포지토리 정리
- [ ] 현재 코드/문서 백업 전략 결정 (브랜치 분리 또는 아카이브)
- [ ] 새 아키텍처 기준 디렉토리 구조 정의
- [ ] 실행 엔트리포인트 단일화 (`main.py` 또는 `cli.py`)

## 1. 스펙 고정
- [ ] 논문 4단계(Stage 1~4) I/O 스키마 정의
- [ ] 로봇 스킬 스키마 정의 (`skills`, `constraints`, `capabilities`)
- [ ] 환경/객체 스키마 정의 (`objectType`, `state`, `position`, `affordance`)
- [ ] 태스크 플랜 JSON 스키마 정의 (decomposition, coalition, allocation)

## 2. Stage 1: Task Decomposition
- [ ] Pythonic few-shot 프롬프트 템플릿 파일 분리
- [ ] 입력: 자연어 명령 + 객체/스킬 컨텍스트
- [ ] 출력: 서브태스크 목록 + 순서/병렬 가능성 + 서브태스크 코드 초안
- [ ] 출력 검증기(JSON schema validator) 구현

## 3. Stage 2: Coalition Formation
- [ ] 서브태스크별 요구 스킬 자동 추출기 구현
- [ ] 단일 로봇 가능 여부 판정기 구현
- [ ] 불가 시 최소 팀 조합 생성기 구현
- [ ] coalition policy 텍스트 + 구조화 포맷 동시 저장

## 4. Stage 3: Task Allocation
- [ ] coalition policy 기반 로봇/팀 할당기 구현
- [ ] 병렬 가능한 서브태스크를 thread group으로 배치
- [ ] 순서 제약(의존성) 있는 태스크는 barrier/join으로 강제
- [ ] 최종 executable plan(중간 IR + 실행 코드) 생성

## 5. Stage 4: Task Execution
- [ ] 실행기(Executor) 모듈 구현
- [ ] 액션 래퍼: 성공/실패/에러메시지 표준화
- [ ] 실패 처리 정책: retry → local replan → global replan
- [ ] 멀티에이전트 인터리빙 실행 루프 구현

## 6. AI2-THOR 연동
- [ ] 초기화 파라미터 프로파일화 (dev/test/eval)
- [ ] 객체 조회/상태 조회 API 래핑
- [ ] 내비게이션 API 조합 전략 고정
- [ ] object-state-changes 액션별 precondition 체크 함수 구현

## 7. 평가 파이프라인 (논문 지표 정합)
- [ ] 지표 구현: `Exe`, `RU`, `GCR`, `TCR`, `SR`
- [ ] ground-truth goal state 포맷 정의
- [ ] transition count 계산기 구현 (RU용)
- [ ] category별(Elemental/Simple/Compound/Complex) 리포트 생성

## 8. 데이터셋/실험 관리
- [ ] 벤치마크 태스크 포맷 설계 (명령, 씬, 로봇, 제약, goal states)
- [ ] unseen split 생성 규칙 문서화
- [ ] seed 고정 및 실험 재현성 옵션 추가
- [ ] 성능 변동성(다회 실행) 자동 집계

## 9. LLM 레이어
- [ ] 모델 어댑터 계층화 (OpenAI/Ollama/기타)
- [ ] 프롬프트 버전 관리
- [ ] 출력 파싱/복구(robust parsing) 구현
- [ ] 토큰 길이/비용/지연 로깅

## 10. macOS 제약 반영
- [ ] 로컬 mac 실행 경로와 Linux GPU 실행 경로 분리
- [ ] 렌더링/실행 호환성 매트릭스 문서화
- [ ] mac에서는 개발/디버그, Linux GPU에서는 본실험 수행 정책 확정

## 11. 테스트/품질
- [ ] 단위테스트: 스키마/할당/지표 계산
- [ ] 통합테스트: end-to-end 1개 elemental + 1개 complex
- [ ] 회귀테스트: 프롬프트 변경 시 성능 비교 자동화
- [ ] 코드 품질: lint/type-check/format 파이프라인

## 12. 문서화
- [ ] 설계 문서(아키텍처, 데이터흐름, 오류처리)
- [ ] 실험 문서(실행법, 지표 계산법, 재현 절차)
- [ ] 결과 대시보드/리포트 템플릿

## 13. 즉시 실행 우선순위 (Next 5)
- [ ] Stage 1~3 출력 스키마 먼저 고정
- [ ] coalition formation 독립 모듈 구현
- [ ] 현재 코드의 순차 실행 루프를 인터리빙 실행기로 교체
- [ ] 지표 5종 계산기 추가
- [ ] 최소 벤치마크 4개(카테고리별 1개)로 첫 리그레션 구축

