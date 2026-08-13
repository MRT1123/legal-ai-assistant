"""
单元测试 - 多模型 Fallback 服务

覆盖场景：
- 模型配置读取（从环境变量）
- 模型状态查询
- 未配置备用模型时的降级行为
"""

import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

# 在导入 model_service 之前设置测试环境变量
os.environ.setdefault("DEEPSEEK_API_KEY", "sk-test-key-for-testing")
os.environ.setdefault("VOLCANO_API_KEY", "")  # 不配置备用模型

from app.services.model_service import (
    PRIMARY_MODEL_CONFIG,
    FALLBACK_MODEL_CONFIG,
    get_model_status,
)


class TestModelConfig:
    """模型配置测试"""

    def test_primary_model_is_deepseek(self):
        """主模型应该是 DeepSeek"""
        assert PRIMARY_MODEL_CONFIG["model"] == "deepseek-chat"
        assert "deepseek.com" in PRIMARY_MODEL_CONFIG["base_url"]

    def test_primary_api_key_from_env(self):
        """主模型 API Key 应从环境变量读取"""
        assert PRIMARY_MODEL_CONFIG["api_key"] == "sk-test-key-for-testing"

    def test_fallback_config_structure(self):
        """备用模型配置应包含必要字段"""
        assert "model" in FALLBACK_MODEL_CONFIG
        assert "base_url" in FALLBACK_MODEL_CONFIG
        assert "api_key" in FALLBACK_MODEL_CONFIG


class TestModelStatus:
    """模型状态查询测试"""

    def test_status_has_primary_and_fallback(self):
        """状态应包含主模型和备用模型"""
        status = get_model_status()
        assert "primary" in status
        assert "fallback" in status

    def test_primary_always_available(self):
        """主模型始终可用"""
        status = get_model_status()
        assert status["primary"]["available"] is True

    def test_fallback_unavailable_without_key(self):
        """未配置 API Key 时备用模型不可用"""
        status = get_model_status()
        # 测试环境没配 VOLCANO_API_KEY
        assert status["fallback"]["available"] is False

    def test_fallback_has_reason_when_unavailable(self):
        """不可用时应说明原因"""
        status = get_model_status()
        if not status["fallback"]["available"]:
            assert "reason" in status["fallback"]


class TestFallbackConfig:
    """Fallback 配置测试"""

    def test_fallback_base_url_default(self):
        """备用模型默认使用火山引擎地址"""
        # 如果没配 VOLCANO_BASE_URL，应该用默认值
        default_url = "https://ark.cn-beijing.volces.com/api/v3"
        # 配置中应该有合理的 URL
        assert "volces.com" in FALLBACK_MODEL_CONFIG["base_url"] or \
               FALLBACK_MODEL_CONFIG["base_url"] == default_url

    def test_primary_timeout_set(self):
        """主模型应设置超时"""
        assert PRIMARY_MODEL_CONFIG["timeout"] > 0
