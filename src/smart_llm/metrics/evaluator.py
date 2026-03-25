from __future__ import annotations

from dataclasses import dataclass
from statistics import mean, pstdev
from typing import Dict, Iterable, List, Sequence

from smart_llm.models import Stage4Output


@dataclass
class MetricsResult:
    Exe: float
    RU: float
    GCR: float
    TCR: float
    SR: float


@dataclass
class VarianceReport:
    runs: int
    mean: Dict[str, float]
    stdev: Dict[str, float]


def compute_exe(executed_tasks: int, total_tasks: int) -> float:
    if total_tasks == 0:
        return 0.0
    return executed_tasks / total_tasks


def compute_ru(useful_transitions: int, total_transitions: int) -> float:
    if total_transitions == 0:
        return 0.0
    return useful_transitions / total_transitions


def compute_gcr(achieved_goals: int, total_goals: int) -> float:
    if total_goals == 0:
        return 0.0
    return achieved_goals / total_goals


def compute_tcr(completed_tasks: int, total_tasks: int) -> float:
    if total_tasks == 0:
        return 0.0
    return completed_tasks / total_tasks


def compute_sr(all_tasks_success: bool, all_goals_success: bool) -> float:
    return 1.0 if all_tasks_success and all_goals_success else 0.0


def transition_count(stage4_output: Stage4Output) -> int:
    return sum(result.transitions for result in stage4_output.results)


class Evaluator:
    def evaluate(
        self,
        stage4_output: Stage4Output,
        goal_state_results: Sequence[bool],
        useful_transitions: int,
    ) -> MetricsResult:
        total_tasks = len(stage4_output.results)
        completed_tasks = sum(1 for r in stage4_output.results if r.success)

        total_goals = len(goal_state_results)
        achieved_goals = sum(1 for achieved in goal_state_results if achieved)

        exe = compute_exe(executed_tasks=total_tasks, total_tasks=total_tasks)
        ru = compute_ru(useful_transitions=useful_transitions, total_transitions=max(transition_count(stage4_output), 1))
        gcr = compute_gcr(achieved_goals=achieved_goals, total_goals=total_goals)
        tcr = compute_tcr(completed_tasks=completed_tasks, total_tasks=total_tasks)
        sr = compute_sr(all_tasks_success=completed_tasks == total_tasks, all_goals_success=achieved_goals == total_goals)

        return MetricsResult(Exe=exe, RU=ru, GCR=gcr, TCR=tcr, SR=sr)

    def category_report(self, rows: Iterable[Dict]) -> Dict[str, MetricsResult]:
        report: Dict[str, MetricsResult] = {}
        grouped: Dict[str, List[MetricsResult]] = {}

        for row in rows:
            category = row["category"]
            grouped.setdefault(category, []).append(row["metrics"])

        for category, metrics_list in grouped.items():
            report[category] = MetricsResult(
                Exe=mean(m.Exe for m in metrics_list),
                RU=mean(m.RU for m in metrics_list),
                GCR=mean(m.GCR for m in metrics_list),
                TCR=mean(m.TCR for m in metrics_list),
                SR=mean(m.SR for m in metrics_list),
            )

        return report

    def aggregate_variance(self, metrics_runs: Sequence[MetricsResult]) -> VarianceReport:
        if not metrics_runs:
            empty = {"Exe": 0.0, "RU": 0.0, "GCR": 0.0, "TCR": 0.0, "SR": 0.0}
            return VarianceReport(runs=0, mean=empty, stdev=empty)

        keys = ["Exe", "RU", "GCR", "TCR", "SR"]
        means = {k: mean(getattr(m, k) for m in metrics_runs) for k in keys}
        stdevs = {
            k: (pstdev(getattr(m, k) for m in metrics_runs) if len(metrics_runs) > 1 else 0.0)
            for k in keys
        }
        return VarianceReport(runs=len(metrics_runs), mean=means, stdev=stdevs)
