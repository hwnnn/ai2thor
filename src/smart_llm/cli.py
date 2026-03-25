from __future__ import annotations

import argparse
import json
import os
import random
from pathlib import Path
from typing import Any, List

from smart_llm.benchmark import build_unseen_split, default_benchmark_path, load_benchmark
from smart_llm.config import RuntimeConfig
from smart_llm.env_loader import load_env_file
from smart_llm.metrics import Evaluator, MetricsResult
from smart_llm.pipeline import SMARTPipeline


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="SMART-LLM aligned multi-agent planner/executor")
    parser.add_argument("command", nargs="?", default="토마토를 썰어서 냉장고에 넣고, 불을 꺼줘")
    parser.add_argument("--provider", default="openai", choices=["openai", "ollama", "echo", "mock", "offline"])
    parser.add_argument("--model", default=None)
    parser.add_argument("--profile", default="dev", choices=["dev", "test", "eval"])
    parser.add_argument("--dry-run", action="store_true", help="AI2-THOR 없이 실행")
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--runs", type=int, default=1)
    parser.add_argument("--benchmark", action="store_true", help="내장 벤치마크를 실행")
    parser.add_argument("--benchmark-path", default=str(default_benchmark_path()))
    parser.add_argument("--unseen-ratio", type=float, default=0.25)
    parser.add_argument("--record-overhead", action="store_true", help="상단 관찰 카메라 영상을 저장")
    parser.add_argument("--record-pov", action="store_true", help="각 agent 시야 영상을 저장")
    parser.add_argument("--record-dir", default="output_videos", help="녹화 영상을 저장할 디렉토리")
    parser.add_argument("--observer-fov", type=float, default=35.0, help="fallback 상단 카메라 field of view")
    parser.add_argument("--observer-height-padding", type=float, default=0.0, help="공식 map-view orthographic size에 더할 여백")
    parser.add_argument("--json", action="store_true", help="JSON 결과만 출력")
    return parser


def _metrics_from_dict(payload: dict[str, Any]) -> MetricsResult:
    return MetricsResult(
        Exe=float(payload["Exe"]),
        RU=float(payload["RU"]),
        GCR=float(payload["GCR"]),
        TCR=float(payload["TCR"]),
        SR=float(payload["SR"]),
    )


def _print_human(result: dict[str, Any]) -> None:
    print("=" * 60)
    print("SMART-LLM Pipeline Result")
    print("=" * 60)

    print("\n[Stage 1] Decomposition")
    for sub in result["stage1"]["subtasks"]:
        print(f"- {sub['subtask_id']}: {sub['description']} (deps={sub['dependencies']})")
    if "llm" in result["stage1"]:
        llm = result["stage1"]["llm"]
        print(
            f"  LLM: provider={llm['provider']}, model={llm['model']}, "
            f"latency_ms={llm['latency_ms']}, prompt_tokens={llm['prompt_tokens']}, "
            f"completion_tokens={llm['completion_tokens']}"
        )

    print("\n[Stage 2] Coalition")
    for col in result["stage2"]["coalitions"]:
        print(
            f"- {col['subtask_id']}: min_team={col['min_team_size']}, "
            f"single={col['single_robot_possible']}, candidates={col['candidate_teams']}"
        )

    print("\n[Stage 3] Allocation")
    for alloc in result["stage3"]["allocations"]:
        print(
            f"- {alloc['subtask_id']}: robots={alloc['assigned_robots']}, "
            f"group={alloc['thread_group']}, deps={alloc['dependencies']}"
        )

    print("\n[Stage 4] Execution")
    for row in result["stage4"]["results"]:
        mark = "OK" if row["success"] else "FAIL"
        print(f"- {row['subtask_id']}: {mark}, attempts={row['attempts']}, transitions={row['transitions']}")

    print("\n[Metrics]")
    for key, value in result["metrics"].items():
        print(f"- {key}: {value:.3f}")

    artifacts = result.get("artifacts", {})
    if artifacts:
        print("\n[Artifacts]")
        for key, value in artifacts.items():
            print(f"- {key}: {value}")


def run_command(args: argparse.Namespace) -> int:
    random.seed(args.seed)

    resolved_model = args.model
    if not resolved_model:
        if args.provider == "openai":
            resolved_model = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
        elif args.provider == "ollama":
            resolved_model = os.getenv("OLLAMA_MODEL", "")
        else:
            resolved_model = args.provider

    if args.provider == "openai" and not os.getenv("OPENAI_API_KEY"):
        raise ValueError("OPENAI_API_KEY is required. Add it to .env or export it before running.")

    if args.provider == "ollama" and not resolved_model:
        raise ValueError("OLLAMA_MODEL is required. Set it in .env or pass --model.")

    config = RuntimeConfig(
        provider=args.provider,
        model=resolved_model or "",
        profile=args.profile,
        dry_run=args.dry_run,
        seed=args.seed,
        run_count=args.runs,
        record_overhead_video=args.record_overhead,
        record_agent_video=args.record_pov,
        record_dir=args.record_dir,
        observer_fov=args.observer_fov,
        observer_height_padding=args.observer_height_padding,
    )

    pipeline = SMARTPipeline(config)
    evaluator = Evaluator()

    if not args.benchmark:
        metrics_runs: List[MetricsResult] = []
        last_result: dict[str, Any] = {}

        for _ in range(max(1, args.runs)):
            current_result = pipeline.run_once(args.command).__dict__
            last_result = current_result
            metrics_runs.append(_metrics_from_dict(current_result["metrics"]))

        if args.runs > 1:
            variance = evaluator.aggregate_variance(metrics_runs)
            last_result["variance"] = {"runs": variance.runs, "mean": variance.mean, "stdev": variance.stdev}

        if args.json:
            print(json.dumps(last_result, ensure_ascii=False, indent=2))
        else:
            _print_human(last_result)
        return 0

    benchmark_path = Path(args.benchmark_path)
    tasks = load_benchmark(benchmark_path)
    split = build_unseen_split(tasks, unseen_ratio=args.unseen_ratio, seed=args.seed)

    rows: List[dict[str, Any]] = []
    for task in split.unseen:
        run = pipeline.run_once(task.command, goal_states=task.goal_states)
        rows.append({"category": task.category, "metrics": run.metrics, "task_id": task.task_id})

    category_rows = [{"category": r["category"], "metrics": _metrics_from_dict(r["metrics"])} for r in rows]
    category_report = evaluator.category_report(category_rows)

    output = {
        "unseen_task_count": len(split.unseen),
        "category_report": {k: v.__dict__ for k, v in category_report.items()},
        "tasks": rows,
    }

    if args.json:
        print(json.dumps(output, ensure_ascii=False, indent=2))
    else:
        print(json.dumps(output, ensure_ascii=False, indent=2))

    return 0


def main() -> int:
    load_env_file()
    parser = _build_parser()
    args = parser.parse_args()
    return run_command(args)


if __name__ == "__main__":
    raise SystemExit(main())
