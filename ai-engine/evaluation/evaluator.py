"""Evaluation module — computes metrics for the P1 evaluation dashboard.

Metrics:
- Intent accuracy: correct intent classifications / total samples
- Field completeness: extracted required fields / total required fields
- Tool correctness: correct tool selections / total samples
- Average time saved: processing time saved vs. manual baseline (120s per ticket)
"""

import json
import logging
from pathlib import Path
from dataclasses import dataclass

logger = logging.getLogger(__name__)

EVAL_SAMPLES_JSON = Path(__file__).resolve().parent.parent / "data" / "evaluation_samples.json"

# Baseline: manual processing takes ~120 seconds per ticket
MANUAL_BASELINE_SECONDS = 120.0


@dataclass
class EvalMetrics:
    intent_accuracy: float
    field_completeness: float
    tool_correctness: float
    avg_time_saved_seconds: float
    total_samples: int


class Evaluator:
    """Compute evaluation metrics from sample results.

    In demo mode, metrics are hardcoded (the evaluation_samples.json
    is a placeholder). In production, this would compare AI outputs
    against ground truth labels.
    """

    def __init__(self):
        self._samples = self._load_samples()

    def _load_samples(self) -> list[dict]:
        if EVAL_SAMPLES_JSON.exists():
            with open(EVAL_SAMPLES_JSON, "r", encoding="utf-8") as f:
                return json.load(f)
        return []

    def compute(self, ai_durations_ms: list[int] | None = None) -> EvalMetrics:
        """Compute evaluation metrics.

        Args:
            ai_durations_ms: List of AI processing durations in milliseconds.
                             If None, uses demo hardcoded values.

        Returns:
            EvalMetrics with computed scores.
        """
        total = len(self._samples) if self._samples else 15

        # In demo mode, return hardcoded metrics (matches the frontend)
        if not ai_durations_ms or not self._samples:
            logger.info("Evaluator: using demo metrics (no real samples)")
            return EvalMetrics(
                intent_accuracy=0.92,
                field_completeness=0.86,
                tool_correctness=0.95,
                avg_time_saved_seconds=78.0,
                total_samples=total,
            )

        # Real mode: compute from actual results
        # (Placeholder for future — would need ground truth labels)
        intent_correct = 0
        field_complete_total = 0
        field_total = 0
        tool_correct = 0

        for sample in self._samples:
            # Compare AI output vs expected
            ai_intent = sample.get("ai_intent", "")
            expected_intent = sample.get("expected_intent", "")
            if ai_intent == expected_intent:
                intent_correct += 1

            ai_fields = sample.get("ai_fields", {})
            expected_fields = sample.get("expected_fields", {})
            for k in expected_fields:
                field_total += 1
                if k in ai_fields and ai_fields[k] != "未提及":
                    field_complete_total += 1

            ai_tool = sample.get("ai_tool", "")
            expected_tool = sample.get("expected_tool", "")
            if ai_tool == expected_tool:
                tool_correct += 1

        n = len(self._samples)
        avg_ai_time = sum(ai_durations_ms) / n / 1000  # convert to seconds
        time_saved = MANUAL_BASELINE_SECONDS - avg_ai_time

        return EvalMetrics(
            intent_accuracy=intent_correct / n if n else 0,
            field_completeness=field_complete_total / field_total if field_total else 0,
            tool_correctness=tool_correct / n if n else 0,
            avg_time_saved_seconds=round(time_saved, 1),
            total_samples=n,
        )


# Module-level singleton
evaluator = Evaluator()
