"""
法律智能助手 - 模型服务层
统一管理 LLM 实例，支持多模型 Fallback（主备切换）

架构：
    主模型 (DeepSeek) --失败/超时--> 备用模型 (火山引擎豆包) --再失败--> 返回友好错误

配置方式：
    在 .env 文件或环境变量中设置：
    - VOLCANO_API_KEY: 火山引擎 ARK API Key
    - VOLCANO_MODEL: 火山引擎模型 Endpoint ID（如 ep-20240xxx）
    - VOLCANO_BASE_URL: 火山引擎 API 地址（默认 https://ark.cn-beijing.volces.com/api/v3）
"""

import os
from dotenv import load_dotenv

# 加载 .env 环境变量（火山引擎配置）
load_dotenv()
import time
from langchain_openai import ChatOpenAI

# ==================== 模型配置 ====================

# 主模型：DeepSeek
PRIMARY_MODEL_CONFIG = {
    "model": "deepseek-chat",
    "base_url": "https://api.deepseek.com",
    "api_key": os.getenv("DEEPSEEK_API_KEY", ""),
    "temperature": 0,
    "timeout": 30,  # 超时秒数
}

# 备用模型：火山引擎（豆包）
# API Key 通过环境变量配置，未配置时备用模型不可用
FALLBACK_MODEL_CONFIG = {
    "model": os.getenv("VOLCANO_MODEL", "ep-20250813120000-xxxxx"),  # 替换为你的 Endpoint ID
    "base_url": os.getenv("VOLCANO_BASE_URL", "https://ark.cn-beijing.volces.com/api/v3"),
    "api_key": os.getenv("VOLCANO_API_KEY", ""),  # 用户充值后填入
    "temperature": 0,
    "timeout": 30,
}

# ==================== 模型实例管理 ====================

# 全局 LLM 实例（懒加载）
_primary_llm = None
_fallback_llm = None


def get_primary_llm() -> ChatOpenAI:
    """获取主模型 LLM 实例"""
    global _primary_llm
    if _primary_llm is None:
        _primary_llm = ChatOpenAI(
            model=PRIMARY_MODEL_CONFIG["model"],
            base_url=PRIMARY_MODEL_CONFIG["base_url"],
            api_key=PRIMARY_MODEL_CONFIG["api_key"],
            temperature=PRIMARY_MODEL_CONFIG["temperature"],
            timeout=PRIMARY_MODEL_CONFIG["timeout"],
        )
    return _primary_llm


def get_fallback_llm() -> ChatOpenAI:
    """获取备用模型 LLM 实例（如果已配置）"""
    global _fallback_llm
    if _fallback_llm is None:
        api_key = FALLBACK_MODEL_CONFIG["api_key"]
        if not api_key:
            return None  # 未配置 API Key，备用模型不可用
        _fallback_llm = ChatOpenAI(
            model=FALLBACK_MODEL_CONFIG["model"],
            base_url=FALLBACK_MODEL_CONFIG["base_url"],
            api_key=api_key,
            temperature=FALLBACK_MODEL_CONFIG["temperature"],
            timeout=FALLBACK_MODEL_CONFIG["timeout"],
        )
    return _fallback_llm


def get_llm() -> ChatOpenAI:
    """获取当前可用的 LLM 实例（优先主模型）
    
    简化版接口：直接返回主模型，如果主模型不可用则返回备用模型。
    适用于不需要重试逻辑的场景。
    """
    try:
        return get_primary_llm()
    except Exception:
        fallback = get_fallback_llm()
        if fallback:
            print("[模型服务] 主模型不可用，切换到备用模型")
            return fallback
        raise RuntimeError("所有模型均不可用")


def invoke_with_fallback(prompt: str, **kwargs) -> str:
    """带 Fallback 的 LLM 调用
    
    先尝试主模型，失败则自动切换到备用模型。
    
    参数：
        prompt: 提示词字符串
        **kwargs: 传递给 LLM 的额外参数
    
    返回：
        LLM 生成的文本内容
    
    异常：
        RuntimeError: 所有模型都调用失败
    """
    # 尝试主模型
    try:
        primary = get_primary_llm()
        response = primary.invoke(prompt, **kwargs)
        return response.content
    except Exception as e:
        print(f"[模型服务] 主模型调用失败: {e}")
    
    # 尝试备用模型
    fallback = get_fallback_llm()
    if fallback:
        try:
            print("[模型服务] 切换到备用模型（火山引擎）...")
            response = fallback.invoke(prompt, **kwargs)
            print("[模型服务] 备用模型调用成功")
            return response.content
        except Exception as e2:
            print(f"[模型服务] 备用模型也失败: {e2}")
    
    raise RuntimeError("所有模型均不可用，请稍后重试")


async def astream_with_fallback(prompt: str, **kwargs):
    """带 Fallback 的流式 LLM 调用（异步生成器）
    
    先尝试主模型流式输出，失败则自动切换到备用模型流式输出。
    
    用于 routes.py 中的 SSE 流式回答。
    """
    # 尝试主模型
    try:
        primary = get_primary_llm()
        chunk_count = 0
        async for token in primary.astream(prompt, **kwargs):
            if token.content:
                chunk_count += 1
                yield token
        if chunk_count > 0:
            return  # 主模型成功，直接返回
        raise RuntimeError("主模型返回空内容")
    except Exception as e:
        print(f"[模型服务] 主模型流式调用失败: {e}")
    
    # 尝试备用模型
    fallback = get_fallback_llm()
    if fallback:
        try:
            print("[模型服务] 流式输出切换到备用模型...")
            async for token in fallback.astream(prompt, **kwargs):
                if token.content:
                    yield token
            return
        except Exception as e2:
            print(f"[模型服务] 备用模型流式也失败: {e2}")
    
    raise RuntimeError("所有模型均不可用，请稍后重试")


def get_model_status() -> dict:
    """获取模型服务状态（用于健康检查）
    
    返回：
        {
            "primary": {"name": "DeepSeek", "available": True},
            "fallback": {"name": "火山引擎", "available": False, "reason": "未配置 API Key"}
        }
    """
    status = {
        "primary": {
            "name": "DeepSeek",
            "model": PRIMARY_MODEL_CONFIG["model"],
            "available": True,  # 主模型始终可用（有 Key）
        },
        "fallback": {
            "name": "火山引擎（豆包）",
            "model": FALLBACK_MODEL_CONFIG["model"],
            "available": bool(FALLBACK_MODEL_CONFIG["api_key"]),
        }
    }
    if not status["fallback"]["available"]:
        status["fallback"]["reason"] = "未配置 VOLCANO_API_KEY 环境变量"
    return status
