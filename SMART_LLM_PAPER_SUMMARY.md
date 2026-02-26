# SMART-LLM 논문 정리

## 1. 논문 메타데이터
- 제목: **SMART-LLM: Smart Multi-Agent Robot Task Planning using Large Language Models**
- 저자: Shyam Sundar Kannan, Vishnunandan L. N. Venkatesh, Byung-Cheol Min
- 버전: arXiv:2309.10062v2 (2024-03-23)
- 링크: https://arxiv.org/abs/2309.10062

## 2. 한 줄 요약
자연어 고수준 명령을 **(1) 태스크 분해 → (2) 연합(팀) 형성 → (3) 태스크 할당 → (4) 실행**의 4단계로 변환해, 이기종 멀티로봇이 병렬/순차 제약을 지키며 실행하도록 만드는 LLM 기반 프레임워크.

## 3. 문제 설정
- 입력: 자연어 명령 `I`
- 환경: 객체/속성/상태가 존재하는 환경 `E`
- 로봇 집합: 이기종 로봇 `R = {R1...RN}`
- 스킬 집합: 전체 스킬 `Δ`, 각 로봇 스킬 `Sn ⊆ Δ`
- 목표:
  - 명령을 실행 가능한 서브태스크로 분해
  - 각 서브태스크의 요구 스킬과 로봇 스킬을 매칭
  - 단일 로봇 불가 시 팀(연합) 구성
  - 병렬 가능한 부분은 병렬 실행

## 4. 핵심 방법론 (4-Stage)

### Stage 1: Task Decomposition
- 입력:
  - 로봇 primitive skill 목록
  - 환경 내 객체/속성 정보
  - few-shot 분해 예시
  - 사용자 명령
- 출력:
  - 시간 순서가 있는 서브태스크 집합
  - 각 서브태스크 실행 코드(파이썬 형태)

### Stage 2: Coalition Formation
- 입력:
  - Stage 1 결과(서브태스크)
  - 로봇별 스킬/제약
  - 연합 정책 예시
- 출력:
  - 서브태스크별 단일 로봇/팀 할당 정책(연합 정책)
- 포인트:
  - 스킬 부족
  - 물체 무게/제약 등 capability gap
  - 협업 필요 여부 판단

### Stage 3: Task Allocation
- 입력:
  - 서브태스크
  - Stage 2 연합 정책
  - few-shot 할당 예시
- 출력:
  - 실행 가능한 최종 코드 (threading 기반 병렬 포함)

### Stage 4: Task Execution
- 입력: Stage 3 코드
- 수행: 로봇 저수준 API 호출로 실제 실행(시뮬/실로봇)

## 5. 프롬프트 설계 포인트
- 자연어 프롬프트보다 **Pythonic prompt**를 사용
- line-by-line comment + block summary를 함께 제공
- 로봇/객체 정보를 Python dict로 제공해 토큰 절감
- few-shot 예시를 단계별로 분리(분해/연합/할당)

## 6. 벤치마크 데이터셋
- 총 36개 high-level instruction
- AI2-THOR floorplan 기반
- 태스크 카테고리:
  - Elemental: 6개
  - Simple: 8개
  - Compound: 14개
  - Complex: 8개
- 추가로 제공:
  - 최종 목표 상태(ground-truth symbolic goals)
  - robot utilization transition 정보

## 7. 실험 설정
- Backbone LLM:
  - GPT-4
  - GPT-3.5
  - Llama2-70B
  - Claude-3-Opus
- Prompt 예시 수:
  - 분해 5개
  - 연합 3개
  - 할당 4개
- Baseline:
  - 분해(ours)+랜덤 할당
  - 분해(ours)+룰 기반 할당

## 8. 평가 지표
- Exe: 실행 가능한 액션 비율
- RU: 로봇 활용 효율(transition 기반)
- GCR: 목표 상태 재현율
- TCR: 태스크 완료율 (`GCR == 1`)
- SR: 성공률 (`GCR == 1` and `RU == 1`)

## 9. 주요 결과
- 전반적으로 SMART-LLM이 baseline 대비 우수
- GPT-4/Claude-3가 특히 안정적
- 단순 태스크에서는 TCR이 높아도 RU 저하로 SR이 낮아질 수 있음(병렬화 미흡 시)
- 복합/복잡 태스크에서 rule/random 할당 한계가 큼
- Llama2-70B도 구조화 프롬프트에서 경쟁력 확인

## 10. 변동성/어블레이션/한계
- LLM 비결정성으로 결과 변동 존재 (특히 complex)
- comment/summary 제거 시 성능 저하
- coalition 단계 제거 시 성능 저하(특히 elemental에서 과도한 팀 할당)
- 미래 과제:
  - 동적(task-time) 재할당
  - 멀티에이전트 LLM 프레임워크 결합

## 11. 우리 프로젝트 관점의 직접 적용 포인트
- 현재 코드에서 가장 먼저 맞춰야 할 논문 정합 포인트:
  - Stage 2(연합 정책) 명시 구현
  - Stage 3(연합 기반 할당 코드 생성) 명시 구현
  - 액션 단위 인터리빙/병렬 실행기 도입
  - RU/GCR/TCR/SR/Exe 평가 루프 구축
  - 프롬프트 템플릿 분리 및 few-shot 자산화

## 12. 참고 링크
- 논문: https://arxiv.org/abs/2309.10062
- 프로젝트 페이지(논문 본문 기재): https://sites.google.com/view/smart-llm/

