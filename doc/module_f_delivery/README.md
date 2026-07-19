# 模块 F/F+ 交付物索引

本目录用于归档模块 F「Agent 测评与效果指标」和模块 F+「真实 LLM 全量测评与指标收口」的交付材料，不放入 `doc/planning/`，便于后续汇报、答辩和演示引用。

## 交付物

- [模块 F/F+ Agent 测评报告](module_f_fplus_evaluation_report.md)

## 关联实现与原始产物

- 测评框架：`ai-engine/evaluation/evaluator.py`
- 真实 LLM 测评入口：`ai-engine/evaluation/run_module_f.py`
- 模块 F 冒烟回归：`ai-engine/evaluation/smoke_module_f.py`
- 初始 40 条真实 LLM 测评结果：`ai-engine/evaluation/module_f_full_20260719.json`
- 最终 40 条真实 LLM 测评结果：`ai-engine/evaluation/module_f_full_final3_20260719.json`

说明：JSON 运行产物属于评测过程输出，保留在 `ai-engine/evaluation/` 下；本目录只沉淀可读报告和交付说明。
