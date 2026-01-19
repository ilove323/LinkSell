# MERGE opportunity_stage 更新修复 - 测试计划

## 修复概述
已实施了三层修复：
1. **提示词层面**：增强 sales_architect.txt，明确指导 LLM 如何处理 `opportunity_stage`
2. **代码逻辑层面**：改进 controller.py 中 merge() 方法的字段处理
3. **同步层面**：确保 `opportunity_stage` 在顶层和 `project_opportunity` 中保持一致

## 测试场景

### 场景 1：笔记明确指示阶段变化
**步骤**:
1. 打开商机"中国投资咨询AI项目"（当前 stage=1）
2. 添加笔记："我认为该商机已进入阶段2"
3. 保存笔记（MERGE 或 SAVE）

**预期结果**:
- ✅ `opportunity_stage` 从 1 更新到 2
- ✅ 更新同步到 `project_opportunity.opportunity_stage`
- ✅ GUI 显示"沟通交流"阶段

### 场景 2：笔记包含沟通交流关键词
**步骤**:
1. 创建新商机，初始 stage=1
2. 添加笔记："与客户进展沟通，确认需求"
3. 保存笔记

**预期结果**:
- ✅ `opportunity_stage` 自动升级到 2（沟通交流）
- ✅ `current_log_entry` 包含笔记精华提炼

### 场景 3：笔记包含商务谈判关键词
**步骤**:
1. 创建新商机，初始 stage=1
2. 添加笔记："与客户进行报价和条款协商"
3. 保存笔记

**预期结果**:
- ✅ `opportunity_stage` 自动升级到 3（商务谈判）

### 场景 4：笔记无相关关键词
**步骤**:
1. 创建新商机，初始 stage=2
2. 添加笔记："与客户讨论实施方案"（无明确阶段指示）
3. 保存笔记

**预期结果**:
- ✅ `opportunity_stage` 保持为 2（因为 LLM 应识别"讨论方案"为商务谈判，更新到 3）
  或
- ✅ `opportunity_stage` 保持不变（如果 LLM 判断无明确变化）

### 场景 5：字段同步验证
**步骤**:
1. 执行场景 1 的 MERGE 后
2. 导出 JSON 文件
3. 检查数据结构

**预期结果**:
```json
{
  "opportunity_stage": 2,  // 顶层有值
  "project_opportunity": {
    "opportunity_stage": 2,  // 嵌套层也有相同值
    ...
  }
}
```

## 验证方法

### 1. JSON 文件检查
```bash
cat data/opportunities/中国投资咨询AI项目.json | grep -A1 -B1 "opportunity_stage"
```
应显示两处都是 2。

### 2. GUI 界面检查
- 打开商机详情
- 观察"阶段"字段是否正确显示"沟通交流"（对应值 2）

### 3. CLI 输出检查
运行 CLI，执行 MERGE 操作后，检查返回的商机信息中的 `opportunity_stage` 是否正确。

## 可能的残留问题

### 问题 A：LLM 没有返回 opportunity_stage
**症状**：即使笔记中有阶段指示，`opportunity_stage` 也不更新
**诊断**：检查 LLM 实际返回的 JSON（添加日志输出）
**修复**：可能需要进一步调整 sales_architect.txt，或检查 LLM 模型是否正确理解中文关键词

### 问题 B：字符串/数字类型混淆
**症状**：`opportunity_stage` 值为 "2" 而不是 2
**诊断**：已在代码中处理（自动转换字符串到整数）
**验证**：运行 test_merge_stage.py 已通过此测试

### 问题 C：project_opportunity 中不存在 opportunity_stage 字段
**症状**：MERGE 后只有顶层更新，嵌套层没有
**诊断**：原始数据中可能不存在该字段
**修复**：代码已处理，会自动新增字段

## 修改文件清单
1. `/config/prompts/sales_architect.txt` - 增强版本（+25 行）
2. `/src/core/controller.py` - merge() 方法 opportunity_stage 处理（改进约 30 行）

## 下一步
- [ ] 执行场景 1 完整测试流程
- [ ] 验证 JSON 文件中的字段同步
- [ ] 检查 GUI 显示是否正确
- [ ] 如有问题，检查 LLM 实际返回内容（添加调试日志）
