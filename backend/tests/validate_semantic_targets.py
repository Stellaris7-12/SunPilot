#!/usr/bin/env python3
"""验证前后端语义 target 配置一致性。

P1-4: 确保 semantic_targets.json 与前端 semanticAdapter.ts 保持同步。

运行方式：
    python ai-engine/evaluation/validate_semantic_targets.py
"""

import json
import sys
import io
from pathlib import Path

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

ENGINE_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(ENGINE_DIR))

from ticket_agent.orchestrator.semantic_targets import load_semantic_targets


def load_frontend_config() -> dict:
    """从前端 semanticAdapter.ts 中提取配置（简化版本）。"""
    frontend_file = ENGINE_DIR.parent / "frontend" / "src" / "sunpilot" / "semanticAdapter.ts"
    if not frontend_file.exists():
        print(f"警告: 前端文件不存在: {frontend_file}")
        return {}

    # 简化解析：只验证 target 名称存在性
    content = frontend_file.read_text(encoding="utf-8")
    targets = set()
    for line in content.split("\n"):
        if "target:" in line and "label:" in line:
            # 提取 { target: 'xxx', ... } 中的 target
            if "'" in line:
                parts = line.split("'")
                for i, part in enumerate(parts):
                    if i > 0 and i % 2 == 1 and "-" in part:
                        targets.add(part)
    return {"targets": list(targets)}


def validate_consistency():
    """验证前后端配置一致性。"""
    backend_config = load_semantic_targets()
    frontend_config = load_frontend_config()

    print("=" * 60)
    print("前后端语义 Target 配置一致性验证")
    print("=" * 60)

    # 收集所有后端 targets
    backend_targets = set()
    for scene in ["call-intake", "ticket-reply", "evidence-review", "human-confirm"]:
        targets = backend_config.get_allowed_targets(scene)
        backend_targets.update(targets)

    frontend_targets = set(frontend_config.get("targets", []))

    print(f"\n后端 targets 数量: {len(backend_targets)}")
    print(f"前端 targets 数量: {len(frontend_targets)}")

    # 检查差异
    only_backend = backend_targets - frontend_targets
    only_frontend = frontend_targets - backend_targets

    if only_backend:
        print(f"\n警告: 仅在后端存在的 targets ({len(only_backend)}):")
        for target in sorted(only_backend):
            print(f"  - {target}")

    if only_frontend:
        print(f"\n警告: 仅在前端存在的 targets ({len(only_frontend)}):")
        for target in sorted(only_frontend):
            print(f"  - {target}")

    common = backend_targets & frontend_targets
    print(f"\n共同 targets: {len(common)}")

    # 检查 deprecated 标记
    deprecated_targets = []
    for scene in ["call-intake", "ticket-reply", "evidence-review", "human-confirm"]:
        for target_def in backend_config.get_targets(scene):
            if target_def.deprecated:
                deprecated_targets.append(target_def.target)

    if deprecated_targets:
        print(f"\n已废弃的 targets ({len(deprecated_targets)}):")
        for target in deprecated_targets:
            print(f"  - {target}")

    # 验证结果
    if not only_backend and not only_frontend:
        print("\n[PASS] 验证通过: 前后端配置完全一致！")
        return 0
    else:
        print("\n[FAIL] 验证失败: 前后端配置存在差异")
        return 1


if __name__ == "__main__":
    sys.exit(validate_consistency())
