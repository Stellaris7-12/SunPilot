"""Load tool definitions from JSON configuration."""

import json
from pathlib import Path
from models.tool_schemas import ToolDefinition

TOOLS_JSON = Path(__file__).resolve().parent.parent / "data" / "tools.json"


def load_tool_definitions() -> list[ToolDefinition]:
    """Load and parse all tool definitions from data/tools.json."""
    with open(TOOLS_JSON, "r", encoding="utf-8") as f:
        data = json.load(f)
    existing = {item["name"] for item in data}
    data.extend(item for item in _builtin_i3_tools() if item["name"] not in existing)
    return [ToolDefinition(**item) for item in data]


def _builtin_i3_tools() -> list[dict]:
    """Production-like mock tools added for Module I3."""
    return [
        _tool("customer.lookup", "Customer lookup", "Find customer by id, phone, name, or card tail", "customer", [
            _param("customerId", False), _param("phone", False), _param("customerName", False), _param("cardLast4", False)
        ]),
        _tool("customer.profile-query", "Customer profile query", "Read customer profile and risk segment", "customer", [
            _param("customerId")
        ]),
        _tool("card.account-status-query", "Card account status query", "Read card status by customer and card tail", "card", [
            _param("customerId"), _param("cardLast4", False)
        ]),
        _tool("ticket.history-search", "Ticket history search", "Search prior ticket and tool history", "ticket", [
            _param("customerId", False), _param("ticketId", False)
        ]),
        _tool("knowledge.policy-search", "Knowledge policy search", "Read mock policy guidance", "knowledge", [
            _param("query")
        ]),
        _tool("campaign.eligibility-check", "Campaign eligibility check", "Check campaign qualification", "benefit", [
            _param("customerId"), _param("couponType", False), _param("benefitCode", False)
        ]),
        _tool("coupon.status-query", "Coupon status query", "Check coupon delivery and idempotency status", "coupon", [
            _param("customerId"), _param("couponType")
        ]),
        _tool("benefit.entitlement-query", "Benefit entitlement query", "Read benefit entitlement by code", "benefit", [
            _param("customerId"), _param("benefitCode", False)
        ]),
        _tool("transaction.detail-query", "Transaction detail query", "Locate transaction by amount, merchant, or date", "transaction", [
            _param("customerId"), _param("transactionDate", False), _param("amount", False, "number"), _param("merchantName", False)
        ]),
        _tool("merchant.info-query", "Merchant info query", "Read merchant category and risk hint", "merchant", [
            _param("merchantName")
        ]),
        _tool("statement.bill-query", "Statement bill query", "Read statement billing status", "statement", [
            _param("customerId")
        ]),
        _tool("points.repair-request", "Points repair request", "Create a controlled points repair request", "points", [
            _param("customerId"), _param("reason")
        ], requires_confirmation=True, risk_level="medium"),
        _tool("fee.adjustment-request", "Fee adjustment request", "Create annual fee adjustment request", "fee", [
            _param("customerId"), _param("reason")
        ], requires_confirmation=True, risk_level="medium"),
        _tool("dispute.case-create", "Dispute case create", "Create a dispute collaboration case", "transaction", [
            _param("customerId"), _param("transactionId", False), _param("reason")
        ], requires_confirmation=True, risk_level="medium"),
        _tool("notification.send-draft", "Notification draft", "Prepare a notification draft without sending it", "notification", [
            _param("customerId"), _param("draft")
        ]),
        _tool("ticket.assign", "Ticket assign", "Prepare assignment suggestion for the ticket", "ticket", [
            _param("ticketId"), _param("assignee")
        ]),
        _tool("ticket.close-request", "Ticket close request", "Prepare close review request without closing ticket", "ticket", [
            _param("ticketId"), _param("finalReply")
        ], requires_confirmation=True, risk_level="high"),
    ]


def _tool(
    name: str,
    display_name: str,
    description: str,
    category: str,
    parameters: list[dict],
    *,
    requires_confirmation: bool = False,
    risk_level: str = "low",
) -> dict:
    return {
        "name": name,
        "display_name": display_name,
        "description": description,
        "category": category,
        "parameters": parameters,
        "requires_confirmation": requires_confirmation,
        "risk_level": risk_level,
        "mock_enabled": True,
        "mock_response": {},
        "mock_delay_ms": 120,
        "mcp_server_name": None,
        "mcp_tool_path": None,
    }


def _param(name: str, required: bool = True, param_type: str = "string") -> dict:
    return {
        "name": name,
        "type": param_type,
        "description": name,
        "required": required,
        "example": "",
    }
