# SMART-LLM Architecture (AI2THOR)

## Pipeline
1. Stage 1 Task Decomposition
- Input: natural language command + skill/env context
- Output: validated `subtasks[]`

2. Stage 2 Coalition Formation
- Input: subtasks + robot skills
- Output: minimum team candidates and coalition policy text

3. Stage 3 Task Allocation
- Input: subtasks + coalition candidates
- Output: robot/team allocation, thread groups, barriers, executable IR

4. Stage 4 Task Execution
- Input: executable IR
- Output: normalized action status and execution result logs
- Failure policy: retry -> local replan -> global replan

## Core Modules
- `src/smart_llm/schemas`: stage I/O schemas and validator
- `src/smart_llm/stages`: Stage1..Stage4 implementations
- `src/smart_llm/execution`: interleaving executor and action wrappers
- `src/smart_llm/environment`: AI2-THOR adapter with profile support
- `src/smart_llm/metrics`: Exe/RU/GCR/TCR/SR evaluators
- `src/smart_llm/benchmark`: benchmark task format + unseen split
- `src/smart_llm/knowledge`: scene/object/interaction catalog used by decomposition and coalition

## Intermediate IR
`ExecutableTask`
- `subtask_id`
- `task_type`
- `parameters`
- `assigned_robots`
- `thread_group`
- `dependencies`

This IR is generated in Stage 3 and consumed by Stage 4.
