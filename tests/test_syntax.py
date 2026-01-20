import sys
import os
import unittest

# 把项目根目录加到路径里，不然找不到 src
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

class TestSyntax(unittest.TestCase):
    def test_import_engine(self):
        """测试 ConversationalEngine 能否正常导入 (检查 SyntaxError/IndentationError)"""
        try:
            from src.core.conversational_engine import ConversationalEngine
            print("\n✅ ConversationalEngine 导入成功，语法没毛病！")
        except Exception as e:
            self.fail(f"❌ 导入失败: {e}")

if __name__ == '__main__':
    unittest.main()

