# MERGE 操作 opportunity_stage 更新修复 - 修复总结

## 问题描述
用户在添加笔记"我认为该商机已进入阶段2"后，发现 `opportunity_stage` 字段没有从 1 更新到 2。

## 根本原因
1. **提示词不清晰**：sales_architect.txt 没有明确指导 LLM 如何处理 `opportunity_stage` 字段的位置和更新规则
2. **字段位置歧义**：LLM 可能返回的 `opportunity_stage` 不清楚应该在顶层还是在 `project_opportunity` 中
3. **类型转换不完善**：merge() 方法没有处理 LLM 可能返回字符串 "2" 的情况

## 实施的修复

### 1. 增强 sales_architect.txt 提示词
**文件**: `/config/prompts/sales_architect.txt`

**改进内容**:
- 明确定义 `opportunity_stage` 必须在顶层（顶层 JSON 根元素）
- 提供关键词识别表：
  - "需求确认" → 1
  - "沟通交流" / "进展沟通" / "联系客户" → 2
  - "商务谈判" / "报价" / "方案讨论" / "条款协商" → 3
  - "签订合同" / "签约" / "已决定合作" → 4
  - 明确说"已进入阶段X"时，直接使用该数字
- 添加强制更新规则：如果笔记中提到阶段变化，必须更新 `opportunity_stage`
- 提供 3 个具体示例说明如何处理阶段更新

### 2. 改进 controller.py 中的 merge() 方法
**文件**: `/src/core/controller.py`
**方法**: `merge()` 中的 `opportunity_stage` 处理部分

**改进内容**:
- ✅ 支持从两个位置提取 `opportunity_stage`：顶层或 `project_opportunity` 中
- ✅ 自动将字符串类型的阶段值转换为整数（例如："2" → 2）
- ✅ 比对新旧值，只在真正改变时才更新
- ✅ 同时更新顶层和 `project_opportunity.opportunity_stage` 以保持一致性
- ✅ 异常处理：类型转换失败时安全跳过

**代码逻辑**:
```python
# 提取阶段值（支持两个位置）
stage_val = None
if "opportunity_stage" in parsed_data:
    stage_val = parsed_data["opportunity_stage"]
elif "project_opportunity" in parsed_data and ...:
    stage_val = parsed_data["project_opportunity"]["opportunity_stage"]

# 类型转换和更新
if stage_val is not None:
    try:
        if isinstance(stage_val, str):
            stage_val = int(stage_val)
        current_stage = merged.get("opportunity_stage")
        if stage_val != current_stage:
            merged["opportunity_stage"] = stage_val
            # 同时同步到 project_opportunity
            if "project_opportunity" in merged:
                merged["project_opportunity"]["opportunity_stage"] = stage_val
    except (ValueError, TypeError):
        pass  # 转换失败则跳过
```

## 测试验证
✅ 已测试：opportunity_stage 从 1 成功更新到 2（顶层和 project_opportunity 都同步更新）

## 下一步建议
1. 运行完整的 MERGE 流程测试，验证 architect_analyze 返回正确的 `opportunity_stage`
2. 在 conversational_engine 中运行实际的 handle_merge() 流程
3. 检查 GUI/CLI 是否正确显示更新后的阶段

## 文件修改清单
- ✅ [config/prompts/sales_architect.txt](config/prompts/sales_architect.txt) - 增强提示词
- ✅ [src/core/controller.py](src/core/controller.py) - 改进 merge() 方法（lines ~376-398）
