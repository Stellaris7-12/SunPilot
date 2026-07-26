"""PageAgent 语义 target 配置加载器。

P1-4: 统一前后端语义 target 定义的单一事实源。
配置文件: ai-engine/data/semantic_targets.json
"""

import json
from functools import lru_cache
from pathlib import Path
from typing import Literal

PageTaskScene = Literal["call-intake", "ticket-reply", "evidence-review", "human-confirm"]


class SemanticTargetDefinition:
    """单个语义 target 定义。"""

    def __init__(self, data: dict):
        self.target: str = data["target"]
        self.label: str = data["label"]
        self.capabilities: list[str] = data["capabilities"]
        self.alias_for: str | None = data.get("aliasFor")
        self.deprecated: bool = data.get("deprecated", False)

    def to_dict(self) -> dict:
        result = {
            "target": self.target,
            "label": self.label,
            "capabilities": self.capabilities,
        }
        if self.alias_for:
            result["aliasFor"] = self.alias_for
        if self.deprecated:
            result["deprecated"] = self.deprecated
        return result


class SemanticTargetsConfig:
    """语义 target 配置。"""

    def __init__(self, data: dict):
        self._data = data
        self.version: str = data.get("version", "1.0.0")
        self.description: str = data.get("description", "")
        self._scenes: dict[str, list[SemanticTargetDefinition]] = {}

        for scene, scene_data in data.get("scenes", {}).items():
            targets = [
                SemanticTargetDefinition(target_data)
                for target_data in scene_data.get("targets", [])
            ]
            self._scenes[scene] = targets

    def get_targets(self, scene: PageTaskScene) -> list[SemanticTargetDefinition]:
        """获取指定场景的所有 target 定义。"""
        return self._scenes.get(scene, [])

    def get_target_labels(self, scene: PageTaskScene) -> dict[str, str]:
        """获取指定场景的 target -> label 映射。"""
        return {
            target.target: target.label
            for target in self.get_targets(scene)
        }

    def get_allowed_targets(self, scene: PageTaskScene, include_deprecated: bool = True) -> list[str]:
        """获取指定场景允许的所有 target 名称。"""
        targets = self.get_targets(scene)
        if not include_deprecated:
            targets = [t for t in targets if not t.deprecated]
        return [t.target for t in targets]

    def find_target(self, scene: PageTaskScene, target: str) -> SemanticTargetDefinition | None:
        """查找指定场景中的 target 定义。"""
        for t in self.get_targets(scene):
            if t.target == target:
                return t
        return None

    def is_valid_target(self, scene: PageTaskScene, target: str) -> bool:
        """检查 target 是否在指定场景中有效。"""
        return target in self.get_allowed_targets(scene)


@lru_cache(maxsize=1)
def load_semantic_targets() -> SemanticTargetsConfig:
    """加载语义 target 配置（带缓存）。"""
    config_path = Path(__file__).parent.parent / "data" / "semantic_targets.json"
    with config_path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    return SemanticTargetsConfig(data)


def get_scene_targets(scene: PageTaskScene) -> list[str]:
    """获取指定场景的所有 target 名称（便捷函数）。"""
    config = load_semantic_targets()
    return config.get_allowed_targets(scene)


def get_target_label(scene: PageTaskScene, target: str) -> str:
    """获取指定 target 的显示标签（便捷函数）。"""
    config = load_semantic_targets()
    target_def = config.find_target(scene, target)
    return target_def.label if target_def else target
