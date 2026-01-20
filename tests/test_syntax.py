"""
LinkSell 基础语法测试 (Syntax Test)

职责：
- 系统的冒烟测试 (Smoke Test)
- 验证核心模块是否可以被 Python 解释器正常加载
- 检查是否存在低级的 SyntaxError 或 IndentationError

特点：
- **Fast Fail**: 作为 CI/CD 流水线的第一道关卡
- **Zero Config**: 不依赖任何外部环境或 Mock 对象
"""

import sys
import os
import unittest

# [环境配置] 确保可以导入 src 模块
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

class TestSyntax(unittest.TestCase):
    def test_import_engine(self):
        """
        [测试场景] 导入 ConversationalEngine
        预期：无异常抛出
        """
        try:
            from src.core.conversational_engine import ConversationalEngine
            print("\n✅ ConversationalEngine 导入成功，语法没毛病！")
        except Exception as e:
            self.fail(f"❌ 导入失败: {e}")

    def test_import_controller(self):
        """
        [测试场景] 导入 LinkSellController
        预期：无异常抛出
        """
        try:
            from src.core.controller import LinkSellController
            print("\n✅ LinkSellController 导入成功，语法没毛病！")
        except Exception as e:
            self.fail(f"❌ 导入失败: {e}")

if __name__ == '__main__':
    unittest.main()