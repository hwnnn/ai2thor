# Experiment Guide

## Execution
- .env setup:
  - Create `.env` manually with `OPENAI_API_KEY`
  - Optional: set `OPENAI_MODEL=gpt-4.1-mini`
- Single command dry-run:
  - `python3 main.py "토마토를 썰어서 냉장고에 넣고, 불을 꺼줘" --provider echo --model echo --dry-run`
- Single command with GPT:
  - `python3 main.py "토마토를 썰어서 냉장고에 넣고, 불을 꺼줘" --provider openai --profile dev`
- Multi-run variability:
  - `python3 main.py "불을 꺼줘" --provider openai --runs 5 --json`
- Benchmark unseen split:
  - `python3 main.py --benchmark --benchmark-path src/smart_llm/benchmark/tasks.json --provider openai --json`

## Metrics
- `Exe`: plan execution completeness
- `RU`: useful transitions / total transitions
- `GCR`: goal completion rate
- `TCR`: task completion rate
- `SR`: strict success rate (all tasks + all goals)

## Reproducibility
- Use `--seed` to fix randomization.
- Use `--runs N` for variability aggregation (mean/std).
- Keep benchmark file versioned and immutable during comparisons.

## macOS vs Linux Policy
- macOS: local development/debug and dry-run validation.
- Linux GPU: full experiment runs with remote model serving if needed.

## Compatibility Matrix
| Mode | macOS | Linux GPU |
| --- | --- | --- |
| Dry-run pipeline | Yes | Yes |
| AI2-THOR interactive runs | Yes (local) | Yes |
| Large-scale LLM experiments | Limited | Recommended |
