from __future__ import annotations

import json
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Sequence, Tuple


@dataclass
class BenchmarkTask:
    task_id: str
    category: str
    command: str
    scene: str
    robots: List[str]
    constraints: List[str] = field(default_factory=list)
    goal_states: List[Dict] = field(default_factory=list)


@dataclass
class BenchmarkSplit:
    train: List[BenchmarkTask]
    unseen: List[BenchmarkTask]


def load_benchmark(path: Path) -> List[BenchmarkTask]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    tasks = [BenchmarkTask(**item) for item in payload.get("tasks", [])]
    return tasks


def build_unseen_split(tasks: Sequence[BenchmarkTask], unseen_ratio: float = 0.25, seed: int = 7) -> BenchmarkSplit:
    rng = random.Random(seed)
    buckets: Dict[str, List[BenchmarkTask]] = {}
    for task in tasks:
        buckets.setdefault(task.category, []).append(task)

    train: List[BenchmarkTask] = []
    unseen: List[BenchmarkTask] = []

    for category_tasks in buckets.values():
        shuffled = list(category_tasks)
        rng.shuffle(shuffled)
        unseen_size = max(1, int(len(shuffled) * unseen_ratio))
        unseen.extend(shuffled[:unseen_size])
        train.extend(shuffled[unseen_size:])

    return BenchmarkSplit(train=train, unseen=unseen)


def category_count(tasks: Sequence[BenchmarkTask]) -> Dict[str, int]:
    out: Dict[str, int] = {}
    for task in tasks:
        out[task.category] = out.get(task.category, 0) + 1
    return out


def default_benchmark_path() -> Path:
    return Path(__file__).resolve().parent / "tasks.json"
