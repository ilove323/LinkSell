"""
LinkSell 核心逻辑单元测试 (Unit Tests)

职责：
- 验证 ConversationalEngine 的核心状态机逻辑
- 测试意图分发 (GET/LIST/RECORD) 的正确性
- 确保上下文锁定 (Context Lock) 机制按预期工作

特点：
- **Mocking**: 全面 Mock 底层 Controller，不依赖真实文件系统或 API
- **Scenario Based**: 模拟用户真实场景 (唯一匹配、多结果歧义、笔记暂存)
"""

import sys
import os
import unittest
from unittest.mock import MagicMock, patch

# [环境配置] 确保可以导入 src 模块
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

class TestCoreLogic(unittest.TestCase):
    def setUp(self):
        """
        [初始化] 每个测试用例执行前运行
        功能：初始化 Engine，并用 Mock 对象替换掉真实的 Controller，
             防止测试过程中产生文件读写或 API 调用消耗。
        """
        with patch('src.core.conversational_engine.LinkSellController') as MockController:
            from src.core.conversational_engine import ConversationalEngine
            self.engine = ConversationalEngine()
            # 替换 Controller 为 Mock 对象
            self.mock_ctrl = self.engine.controller
            # 初始化笔记缓存长度
            self.mock_ctrl.note_buffer = []

    def test_handle_get_unique(self):
        """
        [测试场景] GET 查询 - 唯一命中
        预期：
        1. 返回 type="detail"
        2. current_opp_id 被正确锁定
        3. message 包含确认信息
        """
        # 1. 模拟 Controller 行为
        self.mock_ctrl.find_potential_matches.return_value = [{"id": "123", "name": "沈阳项目"}]
        self.mock_ctrl.get_opportunity_by_id.return_value = {
            "id": "123",
            "project_name": "沈阳项目",
            "project_opportunity": {"project_name": "沈阳项目", "opportunity_stage": "1"}
        }
        self.mock_ctrl.extract_search_term.return_value = "沈阳"
        self.mock_ctrl.stage_map = {"1": "初步接触"} # Mock 阶段映射
        
        # 2. 执行 Action
        result = self.engine.handle_get("查看沈阳项目")
        
        # 3. 验证 Assertion
        self.assertEqual(result["type"], "detail")
        self.assertEqual(self.engine.current_opp_id, "123") # 核心：验证锁定状态
        self.assertIn("已定位商机", result["message"])

    def test_handle_get_ambiguous(self):
        """
        [测试场景] GET 查询 - 歧义 (多个结果)
        预期：
        1. 返回 type="list"
        2. current_opp_id 保持为 None (不锁定)
        3. report_text 包含所有候选项
        """
        # 1. 模拟 Controller 返回多个结果
        self.mock_ctrl.find_potential_matches.return_value = [
            {"id": "101", "name": "沈阳一期", "project_opportunity": {"project_name": "沈阳一期"}},
            {"id": "102", "name": "沈阳二期", "project_opportunity": {"project_name": "沈阳二期"}}
        ]
        self.mock_ctrl.extract_search_term.return_value = "沈阳"
        self.mock_ctrl.stage_map = {}
        
        # 2. 执行 Action
        result = self.engine.handle_get("查看沈阳")
        
        # 3. 验证 Assertion
        self.assertEqual(result["type"], "list")
        self.assertIsNone(self.engine.current_opp_id) # 核心：验证未锁定
        self.assertIn("找到多个匹配结果", result["message"])
        self.assertIn("沈阳一期", result["report_text"])
        self.assertIn("沈阳二期", result["report_text"])

    def test_handle_record(self):
        """
        [测试场景] RECORD 笔记暂存
        预期：
        1. 返回 type="record"
        2. 消息中反馈当前暂存数量
        """
        # 1. 模拟 Controller 行为
        self.mock_ctrl.add_to_note_buffer.return_value = "润色后的内容"
        self.mock_ctrl.note_buffer = ["第一条"] # 模拟当前 buffer 已有一条
        
        # 2. 执行 Action
        result = self.engine.handle_record("这是一条笔记")
        
        # 3. 验证 Assertion
        self.assertEqual(result["type"], "record")
        self.assertIn("笔记已暂存", result["message"])

if __name__ == '__main__':
    unittest.main()