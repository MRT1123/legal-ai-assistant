"""
单元测试 - 敏感信息脱敏模块

覆盖场景：
- 手机号 / 身份证 / 银行卡 / 邮箱 的脱敏替换
- 中文边界场景（脱敏正则不再使用 \b）
- 还原操作
- 敏感信息检测
"""

import sys
import os
import pytest

# 把 backend 加入 Python 路径，让测试能找到 app 模块
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from app.services.desensitize_service import Desensitizer, desensitize, restore, has_sensitive_info


@pytest.fixture
def d():
    """每次测试创建一个新的脱敏器实例"""
    return Desensitizer()


# ==================== 脱敏测试 ====================

class TestDesensitize:
    """测试脱敏功能"""

    def test_phone_basic(self, d):
        """基础手机号脱敏"""
        text, mapping = d.desensitize("我手机号13812345678被偷了")
        assert "13812345678" not in text
        assert "[PHONE_1]" in text
        assert mapping["[PHONE_1]"] == "13812345678"

    def test_phone_chinese_boundary(self, d):
        """中文边界手机号（前后是汉字，不能用 \b）"""
        text, mapping = d.desensitize("请问13900001111能打吗")
        assert "13900001111" not in text
        assert "[PHONE_1]" in text

    def test_phone_multiple(self, d):
        """多个手机号"""
        text, mapping = d.desensitize("打13800001111或13900002222都行")
        assert "[PHONE_1]" in text
        assert "[PHONE_2]" in text
        assert len([k for k in mapping if "PHONE" in k]) == 2

    def test_idcard_basic(self, d):
        """基础身份证号脱敏（18位）"""
        text, mapping = d.desensitize("身份证110101199003071234怎么补办")
        assert "110101199003071234" not in text
        assert "[IDCARD_1]" in text
        assert mapping["[IDCARD_1]"] == "110101199003071234"

    def test_idcard_with_x(self, d):
        """身份证号末尾是 X"""
        text, mapping = d.desensitize("身份证11010119900307123X怎么办")
        assert "[IDCARD_1]" in text

    def test_idcard_chinese_boundary(self, d):
        """身份证在中文边界"""
        text, mapping = d.desensitize("我的证号是320106198512150018帮我查")
        assert "320106198512150018" not in text
        assert "[IDCARD_1]" in text

    def test_bankcard(self, d):
        """银行卡号脱敏（16-19位）"""
        text, mapping = d.desensitize("卡号6222021234567890123被冻结")
        assert "6222021234567890123" not in text
        assert "[BANKCARD_1]" in text

    def test_email(self, d):
        """邮箱脱敏"""
        text, mapping = d.desensitize("发邮件到test@example.com被盗用")
        assert "test@example.com" not in text
        assert "[EMAIL_1]" in text
        assert mapping["[EMAIL_1]"] == "test@example.com"

    def test_mixed_types(self, d):
        """同一文本包含多种敏感信息"""
        text, mapping = d.desensitize(
            "手机13812345678，身份证110101199003071234，邮箱test@a.com"
        )
        assert "[PHONE_1]" in text
        assert "[IDCARD_1]" in text
        assert "[EMAIL_1]" in text
        assert len(mapping) == 3

    def test_no_sensitive_info(self, d):
        """不含敏感信息的文本"""
        text, mapping = d.desensitize("今天天气不错")
        assert text == "今天天气不错"
        assert len(mapping) == 0

    def test_short_number_not_matched(self, d):
        """短数字不应被误判为银行卡"""
        text, mapping = d.desensitize("案件编号12345")
        assert "12345" in text  # 短数字保留原样
        assert len(mapping) == 0


# ==================== 还原测试 ====================

class TestRestore:
    """测试还原功能"""

    def test_basic_restore(self, d):
        """脱敏后还原"""
        text, mapping = d.desensitize("手机13812345678被偷")
        restored = d.restore(text, mapping)
        assert "13812345678" in restored
        assert "[PHONE_1]" not in restored

    def test_restore_multiple(self, d):
        """多个占位符还原"""
        original = "手机13812345678，身份证110101199003071234"
        text, mapping = d.desensitize(original)
        restored = d.restore(text, mapping)
        assert "13812345678" in restored
        assert "110101199003071234" in restored

    def test_restore_empty_mapping(self, d):
        """空映射不改变原文"""
        result = d.restore("原文不变", {})
        assert result == "原文不变"


# ==================== 检测测试 ====================

class TestHasSensitiveInfo:
    """测试敏感信息检测"""

    def test_has_phone(self):
        assert has_sensitive_info("打13812345678") is True

    def test_has_idcard(self):
        assert has_sensitive_info("证号110101199003071234") is True

    def test_has_email(self):
        assert has_sensitive_info("联系test@a.com") is True

    def test_no_sensitive(self):
        assert has_sensitive_info("今天天气好") is False


# ==================== 快捷函数测试 ====================

class TestShortcutFunctions:
    """测试模块级快捷函数"""

    def test_desensitize_shortcut(self):
        text, mapping = desensitize("手机13812345678")
        assert "[PHONE_1]" in text

    def test_restore_shortcut(self):
        text, mapping = desensitize("手机13812345678")
        restored = restore(text, mapping)
        assert "13812345678" in restored
