import sys
import os
import unittest
from unittest.mock import MagicMock, patch

# 把项目根目录加到路径里
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

class TestCoreLogic(unittest.TestCase):
    def setUp(self):
        """每个测试前初始化引擎，并 Mock 掉 Controller 以免真的去读写文件或调 AI"""
        with patch('src.core.conversational_engine.LinkSellController') as MockController:
            from src.core.conversational_engine import ConversationalEngine
            self.engine = ConversationalEngine()
            # 让 engine.controller 变成我们的 mock 对象
            self.mock_ctrl = self.engine.controller

    def test_handle_get_unique(self):
        """测试 GET 逻辑：唯一命中时应该锁定 ID 并返回详情"""
        # 1. 模拟搜索返回唯一结果
        self.mock_ctrl.find_potential_matches.return_value = [{"id": "123", "name": "沈阳项目"}]
        self.mock_ctrl.get_opportunity_by_id.return_value = {
            "id": "123",
            "project_name": "沈阳项目",
            "project_opportunity": {"project_name": "沈阳项目", "opportunity_stage": "1"}
        }
        self.mock_ctrl.extract_search_term.return_value = "沈阳"
        
        # 2. 执行 handle_get
        result = self.engine.handle_get("查看沈阳项目")
        
        # 3. 验证结果
        self.assertEqual(result["type"], "detail")
        self.assertEqual(self.engine.current_opp_id, "123") # 验证 ID 锁定成功
        self.assertIn("已定位商机", result["message"])

    def test_handle_get_ambiguous(self):
        """测试 GET 逻辑：多个命中时应该返回列表，不锁定 ID"""
        # 1. 模拟搜索返回两个结果
        self.mock_ctrl.find_potential_matches.return_value = [
            {"id": "101", "name": "沈阳一期"},
            {"id": "102", "name": "沈阳二期"}
        ]
        self.mock_ctrl.extract_search_term.return_value = "沈阳"
        
        # 2. 执行 handle_get
        result = self.engine.handle_get("查看沈阳")
        
        # 3. 验证结果
        self.assertEqual(result["type"], "list")
        self.assertIsNone(self.engine.current_opp_id) # 验证 ID 没有锁定
        self.assertIn("找到多个匹配结果", result["message"])
        self.assertIn("沈阳一期", result["report_text"])
        self.assertIn("沈阳二期", result["report_text"])

    def test_handle_record(self):
        """测试笔记记录逻辑"""
        self.mock_ctrl.add_to_note_buffer.return_value = "润色后的内容"
        self.engine.controller.note_buffer = ["第一条"] # 模拟 buffer 长度
        
        result = self.engine.handle_record("这是一条笔记")
        
        self.assertEqual(result["type"], "record")
        self.assertIn("笔记已暂存", result["message"])

if __name__ == '__main__':
    unittest.main()
