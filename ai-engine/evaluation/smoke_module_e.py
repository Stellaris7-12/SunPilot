"""Module E smoke tests for labeled evaluation samples."""

import asyncio
import importlib
import json
import re
import sys
from pathlib import Path


ENGINE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ENGINE_DIR))

DATA_DIR = ENGINE_DIR / "data"
SAMPLES_JSON = DATA_DIR / "evaluation_samples.json"
DEMO_TICKETS_JSON = DATA_DIR / "tickets.json"

MIN_SAMPLE_COUNT = 40
REQUIRED_SAMPLE_KEYS = {"id", "source", "category", "ticket", "expected"}
REQUIRED_TICKET_KEYS = {"title", "content", "riskLevel", "customerId", "phone", "cardLast4"}
REQUIRED_EXPECTED_KEYS = {
    "intentType",
    "ticketType",
    "workflowName",
    "requiredFields",
    "expectedFields",
    "expectedTool",
    "expectedStatus",
    "expectedResult",
    "replyPoints",
    "requiresHuman",
}
CORE_TOOLS = {
    "coupon.reissue",
    "customer.update-address",
    "transaction.query",
    "benefit.query",
    "application.progress-query",
}
REQUIRED_STATUSES = {
    "pending_human_review",
    "pending_info",
    "pending_human_confirm",
    "escalated",
}


def _load_json(path: Path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _assert_sample_shape(samples: list[dict]):
    assert len(samples) >= MIN_SAMPLE_COUNT, len(samples)
    ids = [sample.get("id") for sample in samples]
    assert len(ids) == len(set(ids)), "sample ids must be unique"

    for sample in samples:
        missing_sample_keys = REQUIRED_SAMPLE_KEYS - sample.keys()
        assert not missing_sample_keys, (sample.get("id"), missing_sample_keys)

        ticket = sample["ticket"]
        expected = sample["expected"]
        missing_ticket_keys = REQUIRED_TICKET_KEYS - ticket.keys()
        missing_expected_keys = REQUIRED_EXPECTED_KEYS - expected.keys()
        assert not missing_ticket_keys, (sample["id"], missing_ticket_keys)
        assert not missing_expected_keys, (sample["id"], missing_expected_keys)

        assert ticket["title"].strip(), sample["id"]
        assert ticket["content"].strip(), sample["id"]
        assert re.fullmatch(r"C\d{5}", ticket["customerId"]), (sample["id"], ticket["customerId"])
        assert re.fullmatch(r"1\d{2}\*{4}\d{4}", ticket["phone"]), (sample["id"], ticket["phone"])
        assert re.fullmatch(r"\d{4}", ticket["cardLast4"]), (sample["id"], ticket["cardLast4"])

        assert isinstance(expected["requiredFields"], list), sample["id"]
        assert isinstance(expected["expectedFields"], dict), sample["id"]
        assert isinstance(expected["replyPoints"], list) and expected["replyPoints"], sample["id"]
        assert isinstance(expected["requiresHuman"], bool), sample["id"]
        for field_name in expected["requiredFields"]:
            assert field_name in expected["expectedFields"], (sample["id"], field_name)


def _assert_coverage(samples: list[dict]):
    tools = {sample["expected"]["expectedTool"] for sample in samples}
    statuses = {sample["expected"]["expectedStatus"] for sample in samples}
    categories = {sample["category"] for sample in samples}
    intent_types = {sample["expected"]["intentType"] for sample in samples}

    assert CORE_TOOLS <= tools, tools
    assert REQUIRED_STATUSES <= statuses, statuses
    assert len(categories) >= 12, categories
    assert {
        "COUPON_REISSUE",
        "CUSTOMER_ADDRESS_UPDATE",
        "TRANSACTION_DISPUTE",
        "BENEFIT_QUERY",
        "APPLICATION_PROGRESS_QUERY",
        "UNKNOWN",
    } <= intent_types, intent_types

    first_twenty = samples[:20]
    assert all(sample["expected"]["expectedTool"] for sample in first_twenty), (
        "first 20 samples should cover standard tool-backed scenarios"
    )


def _assert_demo_data_is_separate(samples: list[dict]):
    demo_tickets = _load_json(DEMO_TICKETS_JSON)
    demo_ids = {ticket["id"] for ticket in demo_tickets}
    demo_contents = {ticket["content"] for ticket in demo_tickets}
    sample_ids = {sample["id"] for sample in samples}
    sample_contents = {sample["ticket"]["content"] for sample in samples}

    assert not (sample_ids & demo_ids), sample_ids & demo_ids
    assert not (sample_contents & demo_contents), "evaluation samples must not duplicate demo tickets"


async def _assert_evaluator_and_api(samples: list[dict]):
    evaluator_module = importlib.import_module("evaluation.evaluator")
    evaluator_module.evaluator.reload()
    metrics = evaluator_module.evaluator.compute()
    assert metrics.total_samples == len(samples), metrics

    main_module = importlib.import_module("main")
    response = await main_module.get_evaluation_metrics()
    assert response["totalSamples"] == len(samples), response


async def main():
    samples = _load_json(SAMPLES_JSON)
    assert isinstance(samples, list), type(samples)
    _assert_sample_shape(samples)
    _assert_coverage(samples)
    _assert_demo_data_is_separate(samples)
    await _assert_evaluator_and_api(samples)
    print("module E smoke passed")


if __name__ == "__main__":
    asyncio.run(main())
