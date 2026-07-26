"""Typed workflow configuration contracts and accessors."""

from __future__ import annotations

from typing import Any, Mapping

from pydantic import Field

from models.ai_result import ApiModel


class WorkflowField(ApiModel):
    name: str
    label: str = ""
    field_type: str = Field(default="text", alias="type")
    options: list[str] = Field(default_factory=list)


class WorkflowScenario(ApiModel):
    workflow_name: str = ""
    label: str = ""
    order_prefix: str = ""
    sla_days: int = 0
    fields: list[WorkflowField] = Field(default_factory=list)
    specific_fields: list[WorkflowField] = Field(default_factory=list)
    required_fields: list[str] = Field(default_factory=list)
    recommended_tool: str = ""
    candidate_tools: list[str] = Field(default_factory=list)
    classifier_hint: str = ""
    requires_human_confirmation: bool = False
    notification_template: str = ""

    def to_runtime_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="python", by_alias=False)


class WorkflowConfig(ApiModel):
    default_workflow: str = "unknown_flow"
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
