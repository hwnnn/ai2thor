from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List

from smart_llm.config import RuntimeConfig, default_robots, default_skills
from smart_llm.environment import AI2ThorAdapter
from smart_llm.llm import build_adapter
from smart_llm.metrics import Evaluator
from smart_llm.models import Stage1Output
from smart_llm.schemas import SchemaValidator
from smart_llm.stages import CoalitionFormer, Stage1Decomposer, Stage4Executor, TaskAllocator


PROMPT_VERSION = "stage1_v3_yaml"


@dataclass
class PipelineResult:
    stage1: Dict[str, Any]
    stage2: Dict[str, Any]
    stage3: Dict[str, Any]
    stage4: Dict[str, Any]
    metrics: Dict[str, float]
    artifacts: Dict[str, Any]


class SMARTPipeline:
    def __init__(self, config: RuntimeConfig):
        self.config = config
        self.validator = SchemaValidator()
        self.skills = default_skills()
        self.adapter = build_adapter(provider=config.provider, model=config.model)

    def _build_env(self, *, enable_recording: bool) -> AI2ThorAdapter:
        return AI2ThorAdapter(
            profile=self.config.profile,
            dry_run=self.config.dry_run,
            record_overhead_video=self.config.record_overhead_video if enable_recording else False,
            record_agent_video=self.config.record_agent_video if enable_recording else False,
            output_dir=self.config.record_dir,
            observer_fov=self.config.observer_fov,
            observer_height_padding=self.config.observer_height_padding,
        )

    def _recommended_agent_count(self, stage1: Stage1Output) -> int:
        levels: Dict[str, int] = {}
        pending = {sub.subtask_id: sub for sub in stage1.subtasks}

        while pending:
            progressed = False
            for subtask_id, subtask in list(pending.items()):
                if not set(subtask.dependencies).issubset(levels):
                    continue
                levels[subtask_id] = max((levels[dep] + 1 for dep in subtask.dependencies), default=0)
                del pending[subtask_id]
                progressed = True

            if not progressed:
                for subtask_id in list(pending.keys()):
                    levels[subtask_id] = 0
                    del pending[subtask_id]

        concurrent: Dict[int, int] = {}
        for subtask in stage1.subtasks:
            if not subtask.parallelizable:
                continue
            level = levels.get(subtask.subtask_id, 0)
            concurrent[level] = concurrent.get(level, 0) + 1

        suggested = max(concurrent.values(), default=1)
        return max(1, min(self.config.max_agents, suggested))

    def run_once(self, user_command: str, goal_states: List[Dict[str, Any]] | None = None) -> PipelineResult:
        bootstrap_env = self._build_env(enable_recording=False)
        bootstrap_env.start(agent_count=1)

        try:
            objects = bootstrap_env.list_environment_objects(agent_id=0)
        finally:
            bootstrap_env.stop()

        stage1 = Stage1Decomposer(adapter=self.adapter, validator=self.validator).run(
            user_command=user_command,
            skills=self.skills,
            objects=objects,
        )
        robots = default_robots(self._recommended_agent_count(stage1))

        env = self._build_env(enable_recording=True)
        env.start(agent_count=len(robots))

        try:
            stage2 = CoalitionFormer(validator=self.validator).run(stage1_output=stage1, robots=robots)
            stage3 = TaskAllocator(validator=self.validator).run(
                stage1_output=stage1,
                stage2_output=stage2,
                robots=robots,
            )
            stage4 = Stage4Executor(env_adapter=env, robots=robots).run(stage3_output=stage3)

            evaluator = Evaluator()
            goal_state_results: List[bool] = (
                env.evaluate_goal_states(goal_states)
                if goal_states is not None
                else [r.success for r in stage4.results]
            )
            useful_transitions = sum(1 for r in stage4.results if r.success)
            metrics = evaluator.evaluate(
                stage4_output=stage4,
                goal_state_results=goal_state_results,
                useful_transitions=useful_transitions,
            )

            stage1_payload = {
                "subtasks": [s.__dict__ for s in stage1.subtasks],
                "prompt_version": PROMPT_VERSION,
            }
            llm_response = getattr(self.adapter, "last_response", None)
            if llm_response is not None:
                stage1_payload["llm"] = {
                    "provider": self.config.provider,
                    "model": getattr(self.adapter, "model_name", self.config.model),
                    "latency_ms": llm_response.latency_ms,
                    "prompt_tokens": llm_response.prompt_tokens,
                    "completion_tokens": llm_response.completion_tokens,
                    "estimated_cost_usd": llm_response.estimated_cost_usd,
                }

            artifacts = env.artifacts()
            artifacts["agent_count"] = len(robots)

            return PipelineResult(
                stage1=stage1_payload,
                stage2={
                    "coalitions": [c.__dict__ for c in stage2.coalitions],
                    "coalition_policy_text": stage2.coalition_policy_text,
                },
                stage3={
                    "allocations": [a.__dict__ for a in stage3.allocations],
                    "barriers": stage3.barriers,
                    "executable_plan": [p.__dict__ for p in stage3.executable_plan],
                },
                stage4={
                    "results": [r.__dict__ for r in stage4.results],
                    "success": stage4.success,
                    "total_transitions": stage4.total_transitions,
                    "logs": stage4.logs,
                },
                metrics=metrics.__dict__,
                artifacts=artifacts,
            )
        finally:
            env.stop()
