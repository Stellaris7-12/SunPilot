"""Typed workflow configuration contracts and accessors."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from pydantic import Field, field_validator, ConfigDict

from ticket_agent.models.schemas.ai_result import ApiModel


def _load_registered_tools() -> set[str]:
    """加载 tools.json 中注册的工具名称集合，用于交叉校验。"""
    tools_path = Path(__file__).parent.parent / "data" / "tools.json"
    if not tools_path.exists():
        return set()
    try:
        with open(tools_path, "r", encoding="utf-8") as f:
            tools_data = json.load(f)
            return {tool["name"] for tool in tools_data if isinstance(tool, dict) and "name" in tool}
    except Exception:
        return set()


class WorkflowField(ApiModel):
    # P2-11: 启用 extra="forbid"，防止运营写错键名导致配置静默失效
    model_config = ConfigDict(extra="forbid")

    name: str
    label: str = ""
    field_type: str = Field(default="text", alias="type")
    options: list[str] = Field(default_factory=list)
    extract_rule: dict[str, Any] | None = Field(default=None, alias="extractRule")
    default: str = ""


class WorkflowScenario(ApiModel):
    # P2-11: 启用 extra="forbid"，防止键名错误导致配置静默失效
    model_config = ConfigDict(extra="forbid")

    workflow_name: str = ""
    label: str = ""
    order_prefix: str = Field(default="", alias="orderPrefix")
    sla_days: int = Field(default=0, alias="slaDays")
    fields: list[WorkflowField] = Field(default_factory=list)
    specific_fields: list[WorkflowField] = Field(default_factory=list, alias="specificFields")
    required_fields: list[str] = Field(default_factory=list, alias="required_fields")
    recommended_tool: str = Field(default="", alias="recommended_tool")
    candidate_tools: list[str] = Field(default_factory=list, alias="candidateTools")
    classifier_hint: str = Field(default="", alias="classifierHint")
    requires_human_confirmation: bool = Field(default=False, alias="requires_human_confirmation")
    notification_template: str = Field(default="", alias="notification_template")
    detection: dict[str, Any] | None = None

    # P1-1: 交叉校验 - required_fields 必须是 fields 的子集
    @field_validator("required_fields")
    @classmethod
    def validate_required_fields_subset(cls, v: list[str], info) -> list[str]:
        # 在 Pydantic v2 中，info.data 包含已验证的字段
        fields = info.data.get("fields", [])
        field_names = {f.name for f in fields}
        invalid = [rf for rf in v if rf not in field_names]
        if invalid:
            raise ValueError(
                f"required_fields 包含未定义的字段: {invalid}。"
                f"所有 required_fields 必须在 fields 中声明。"
            )
        return v

    # P1-1: orderPrefix 非空校验（除 UNKNOWN 场景外）
    @field_validator("order_prefix")
    @classmethod
    def validate_order_prefix_not_empty(cls, v: str, info) -> str:
        workflow_name = info.data.get("workflow_name", "")
        # UNKNOWN 场景允许空 orderPrefix
        if workflow_name != "unknown_flow" and not v:
            raise ValueError(
                f"orderPrefix 不能为空。场景 '{workflow_name}' 必须配置有效的工单前缀。"
            )
        return v

    # P1-1: 交叉校验 - recommended_tool 必须在 tools.json 中注册
    @field_validator("recommended_tool")
    @classmethod
    def validate_recommended_tool_registered(cls, v: str) -> str:
        if not v:  # 空字符串允许（例如 UNKNOWN 场景）
            return v
        registered_tools = _load_registered_tools()
        if registered_tools and v not in registered_tools:
            raise ValueError(
                f"recommended_tool '{v}' 未在 tools.json 中注册。"
                f"可用工具: {sorted(registered_tools)}"
            )
        return v

    # P1-1: 交叉校验 - candidate_tools 中的工具必须在 tools.json 中注册
    @field_validator("candidate_tools")
    @classmethod
    def validate_candidate_tools_registered(cls, v: list[str]) -> list[str]:
        if not v:
            return v
        registered_tools = _load_registered_tools()
        if registered_tools:
            invalid = [tool for tool in v if tool not in registered_tools]
            if invalid:
                raise ValueError(
                    f"candidateTools 包含未注册的工具: {invalid}。"
                    f"所有工具必须在 tools.json 中注册。可用工具: {sorted(registered_tools)}"
                )
        return v

    def to_runtime_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="python", by_alias=False)


class WorkflowConfig(ApiModel):
    # P1-1: 启用 extra="forbid"，防止顶层配置键名错误
    model_config = ConfigDict(extra="forbid")

    default_workflow: str = "unknown_flow"
    common_fields: list[WorkflowField] = Field(default_factory=list, alias="commonFields")
    scenarios: dict[str, WorkflowScenario] = Field(default_factory=dict)

    def scenario(self, intent_type: str) -> WorkflowScenario:
        scenario = self.scenarios.get(intent_type) or self.scenarios.get("UNKNOWN")
        if scenario is not None:
            return scenario
        return WorkflowScenario(
            workflow_name=self.default_workflow,
            label="未知场景",
        )

    def to_runtime_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="python", by_alias=False)


def workflow_spec(config: WorkflowConfig | Mapping[str, Any] | None) -> WorkflowConfig:
    return config if isinstance(config, WorkflowConfig) else WorkflowConfig.model_validate(config or {})


def workflow_scenario(
    config: WorkflowConfig | Mapping[str, Any] | None,
    intent_type: str,
) -> WorkflowScenario:
    return workflow_spec(config).scenario(intent_type)


def workflow_scenario_names(config: WorkflowConfig | Mapping[str, Any] | None) -> set[str]:
    return set(workflow_spec(config).scenarios.keys())


def workflow_default_name(config: WorkflowConfig | Mapping[str, Any] | None) -> str:
    return workflow_spec(config).default_workflow
