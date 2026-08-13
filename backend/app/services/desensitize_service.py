"""
法律智能助手 - 敏感信息脱敏服务

功能：在用户输入传给 LLM 之前，自动将敏感信息替换为占位符，
      LLM 回答后再还原为原始信息。

支持的敏感信息类型：
- 手机号（11位）
- 身份证号（18位/15位）
- 银行卡号（16-19位）
- 邮箱地址

设计思路：
- 用正则匹配敏感信息
- 替换为 [PHONE_1]、[IDCARD_1] 等占位符
- 保存映射关系，回答后还原
"""

import re
from typing import Dict, Tuple


class Desensitizer:
    """敏感信息脱敏器"""
    
    def __init__(self):
        # 敏感信息类型及其正则表达式
        self.patterns = [
            # 身份证号（18位，最后可能是X）- 用前后断言替代 \b
            ("IDCARD", r'(?<!\d)[1-9]\d{5}(?:19|20)\d{2}(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])\d{3}[\dXx](?!\d)'),
            # 手机号（11位，1开头）
            ("PHONE", r'(?<!\d)1[3-9]\d{9}(?!\d)'),
            # 银行卡号（16-19位数字）
            ("BANKCARD", r'(?<!\d)\d{16,19}(?!\d)'),
            # 邮箱
            ("EMAIL", r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}'),
        ]
        
        # 占位符的中文标签（显示给用户看更友好）
        self.labels = {
            "IDCARD": "身份证号",
            "PHONE": "手机号",
            "BANKCARD": "银行卡号",
            "EMAIL": "邮箱",
        }
    
    def desensitize(self, text: str) -> Tuple[str, Dict[str, str]]:
        """脱敏处理
        
        参数：
            text: 原始文本
        
        返回：
            (脱敏后的文本, 占位符到原始值的映射字典)
        """
        mapping = {}  # 占位符 -> 原始值
        counter = {}  # 每种类型的计数器
        
        for info_type, pattern in self.patterns:
            counter[info_type] = 0
            
            def replace_func(match):
                original = match.group(0)
                counter[info_type] += 1
                placeholder = f"[{info_type}_{counter[info_type]}]"
                mapping[placeholder] = original
                return placeholder
            
            text = re.sub(pattern, replace_func, text)
        
        return text, mapping
    
    def restore(self, text: str, mapping: Dict[str, str]) -> str:
        """还原脱敏信息
        
        参数：
            text: 包含占位符的文本
            mapping: 占位符到原始值的映射
        
        返回：
            还原后的文本
        """
        for placeholder, original in mapping.items():
            text = text.replace(placeholder, original)
        return text
    
    def has_sensitive_info(self, text: str) -> bool:
        """检查文本是否包含敏感信息"""
        for info_type, pattern in self.patterns:
            if re.search(pattern, text):
                return True
        return False
    
    def get_summary(self, mapping: Dict[str, str]) -> str:
        """获取脱敏摘要（用于日志）"""
        if not mapping:
            return "无敏感信息"
        types = set()
        for placeholder in mapping:
            # 从 [PHONE_1] 提取 PHONE
            info_type = placeholder.strip("[]").rsplit("_", 1)[0]
            types.add(self.labels.get(info_type, info_type))
        return f"已脱敏: {', '.join(types)}"


# 全局单例
_desensitizer = Desensitizer()


def desensitize(text: str) -> Tuple[str, Dict[str, str]]:
    """脱敏处理（快捷函数）"""
    return _desensitizer.desensitize(text)


def restore(text: str, mapping: Dict[str, str]) -> str:
    """还原脱敏（快捷函数）"""
    return _desensitizer.restore(text, mapping)


def has_sensitive_info(text: str) -> bool:
    """检查是否有敏感信息"""
    return _desensitizer.has_sensitive_info(text)
