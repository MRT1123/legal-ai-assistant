"""
数据库抽象基类

定义所有数据库实现必须遵守的"接口规范"。
未来如果要加 PostgreSQL，只需要新建一个 postgres_impl.py，
实现这个基类的所有方法就行，上层调用代码完全不用改。
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict


class DatabaseBase(ABC):
    """数据库操作抽象基类"""

    # ==================== 对话相关方法 ====================

    @abstractmethod
    def init_db(self):
        """
        初始化数据库表结构
        应用启动时调用，如果表已存在则跳过
        """
        pass

    @abstractmethod
    def save_message(self, session_id: str, role: str, content: str,
                     query_type: Optional[str] = None,
                     sources: Optional[str] = None):
        """
        保存一条对话记录
        
        参数：
            session_id - 会话 ID（用于关联同一个对话的多条消息）
            role       - 角色：user（用户）或 assistant（AI）
            content    - 消息内容
            query_type - 问题分类结果（仅 assistant 有）
            sources    - 引用来源 JSON 字符串（仅 assistant 有）
        """
        pass

    @abstractmethod
    def get_history(self, session_id: str, limit: int = 50) -> list:
        """
        获取某个会话的历史记录
        
        参数：
            session_id - 会话 ID
            limit      - 最多返回多少条（默认50条）
        
        返回：按时间正序排列的消息列表
        """
        pass

    @abstractmethod
    def get_all_sessions(self) -> list:
        """
        获取所有会话列表（用于侧边栏展示历史对话）
        
        返回：每个会话的 ID、第一条消息摘要、最后一条消息时间、消息数量
        """
        pass

    @abstractmethod
    def delete_session(self, session_id: str):
        """删除一个会话的所有记录"""
        pass

    @abstractmethod
    def search_sessions(self, keyword: str) -> list:
        """
        按关键词搜索对话历史
        
        参数：
            keyword - 搜索关键词（模糊匹配对话内容）
        
        返回：匹配的会话列表，每个会话包含 session_id、first_message（匹配摘要）、last_time、message_count
        """
        pass

    # ==================== 用户相关方法 ====================

    @abstractmethod
    def create_user(self, email: str, hashed_password: str) -> bool:
        """
        创建新用户
        
        参数：
            email           - 用户邮箱
            hashed_password - 加密后的密码
        
        返回：创建成功返回 True，邮箱已存在返回 False
        """
        pass

    @abstractmethod
    def get_user_by_email(self, email: str) -> Optional[Dict]:
        """
        根据邮箱获取用户信息
        
        参数：
            email - 用户邮箱
        
        返回：用户信息字典 {"id", "email", "hashed_password", "created_at"}，不存在返回 None
        """
        pass

    @abstractmethod
    def update_user_password(self, email: str, new_hashed_password: str) -> bool:
        """
        更新用户密码
        
        参数：
            email              - 用户邮箱
            new_hashed_password - 新的加密密码
        
        返回：更新成功返回 True，用户不存在返回 False
        """
        pass

    # ==================== 验证码相关方法 ====================

    @abstractmethod
    def save_verification_code(self, email: str, code: str, purpose: str) -> None:
        """
        保存验证码
        
        参数：
            email   - 接收验证码的邮箱
            code    - 验证码
            purpose - 用途：register（注册）或 reset（重置密码）
        """
        pass

    @abstractmethod
    def get_latest_code(self, email: str, purpose: str) -> Optional[Dict]:
        """
        获取指定邮箱最新的一条未使用验证码
        
        参数：
            email   - 邮箱
            purpose - 用途：register 或 reset
        
        返回：验证码信息 {"code", "expires_at"}，不存在或已过期返回 None
        """
        pass

    @abstractmethod
    def mark_code_used(self, email: str, code: str, purpose: str) -> None:
        """
        标记验证码为已使用
        
        参数：
            email   - 邮箱
            code    - 验证码
            purpose - 用途
        """
        pass
