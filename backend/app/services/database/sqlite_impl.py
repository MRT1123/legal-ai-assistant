"""
数据库实现 —— SQLite

使用 SQLite 本地文件数据库，零配置、免费、单文件，
适合本地开发和 GitHub 演示部署。
"""

import sqlite3
import os
from datetime import datetime, timedelta
from typing import Optional, Dict
from .base import DatabaseBase

# 数据库文件路径：存放在 app/data 目录下
# __file__ 是 app/services/database/sqlite_impl.py，需要往上2层到 app/，再进 data/
DB_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "legal_assistant.db")


class SQLiteDatabase(DatabaseBase):
    """SQLite 数据库实现"""

    def __init__(self):
        """初始化，数据库路径可通过参数覆盖（方便测试）"""
        self.db_path = DB_PATH

    def get_connection(self):
        """
        获取数据库连接
        SQLite 每次操作都新建连接（轻量级，无性能问题）
        check_same_thread=False 允许跨线程使用（FastAPI 异步场景需要）
        """
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row  # 让查询结果可以通过列名访问
        return conn

    # ==================== 初始化 ====================

    def init_db(self):
        """
        初始化数据库表结构
        包含：对话历史表、用户表、验证码表
        """
        # 确保 data 目录存在
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

        conn = self.get_connection()
        cursor = conn.cursor()

        # ===== 对话历史表 =====
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                query_type TEXT,
                sources TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_session_id 
            ON conversations(session_id)
        ''')

        # ===== 用户表 =====
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL UNIQUE,
                hashed_password TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # ===== 验证码表 =====
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS verification_codes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL,
                code TEXT NOT NULL,
                purpose TEXT NOT NULL,
                expires_at TIMESTAMP NOT NULL,
                used INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_verification_lookup 
            ON verification_codes(email, purpose, used)
        ''')

        conn.commit()
        conn.close()
        print(f"✅ 数据库初始化完成：{self.db_path}")

    # ==================== 对话相关方法 ====================

    def save_message(self, session_id: str, role: str, content: str,
                     query_type: str = None, sources: str = None):
        """保存一条对话记录"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO conversations (session_id, role, content, query_type, sources)
            VALUES (?, ?, ?, ?, ?)
        ''', (session_id, role, content, query_type, sources))

        conn.commit()
        conn.close()

    def get_history(self, session_id: str, limit: int = 50) -> list:
        """
        获取某个会话的历史记录
        返回：按时间正序排列的消息列表
        """
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT id, session_id, role, content, query_type, sources, created_at
            FROM conversations
            WHERE session_id = ?
            ORDER BY created_at ASC
            LIMIT ?
        ''', (session_id, limit))

        rows = cursor.fetchall()
        conn.close()

        return [dict(row) for row in rows]

    def get_all_sessions(self) -> list:
        """
        获取所有会话列表（用于侧边栏展示历史对话）
        """
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT 
                session_id,
                MIN(content) as first_message,
                MAX(created_at) as last_time,
                COUNT(*) as message_count
            FROM conversations
            GROUP BY session_id
            ORDER BY last_time DESC
        ''')

        rows = cursor.fetchall()
        conn.close()

        return [dict(row) for row in rows]

    def delete_session(self, session_id: str):
        """删除一个会话的所有记录"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute('DELETE FROM conversations WHERE session_id = ?', (session_id,))

        conn.commit()
        conn.close()

    def search_sessions(self, keyword: str) -> list:
        """
        按关键词模糊搜索对话历史
        
        搜索逻辑：
        1. 在 conversations 表中模糊匹配 content 字段
        2. 按 session_id 分组，取匹配到的第一条消息作为摘要
        3. 返回匹配的会话列表（含会话ID、匹配摘要、最后更新时间、消息数量）
        """
        conn = self.get_connection()
        cursor = conn.cursor()

        # 搜索包含关键词的对话，取每个会话中第一条匹配的消息作为摘要
        cursor.execute('''
            SELECT 
                session_id,
                content as first_message,
                MAX(created_at) as last_time,
                COUNT(*) as match_count
            FROM conversations
            WHERE content LIKE ?
            GROUP BY session_id
            ORDER BY last_time DESC
        ''', (f'%{keyword}%',))

        rows = cursor.fetchall()
        conn.close()

        # 截取摘要（最多显示前50个字符）
        results = []
        for row in rows:
            item = dict(row)
            # 高亮显示匹配关键词附近的文本
            msg = item['first_message']
            if len(msg) > 50:
                # 尝试找到关键词位置，截取关键词附近的文本
                idx = msg.lower().find(keyword.lower())
                if idx >= 0:
                    start = max(0, idx - 15)
                    end = min(len(msg), idx + len(keyword) + 35)
                    item['first_message'] = ('...' if start > 0 else '') + msg[start:end] + ('...' if end < len(msg) else '')
                else:
                    item['first_message'] = msg[:50] + '...'
            results.append(item)

        return results

    # ==================== 用户相关方法 ====================

    def create_user(self, email: str, hashed_password: str) -> bool:
        """
        创建新用户
        返回：创建成功返回 True，邮箱已存在返回 False
        """
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute('''
                INSERT INTO users (email, hashed_password)
                VALUES (?, ?)
            ''', (email, hashed_password))
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            # 邮箱已存在（UNIQUE 约束触发）
            return False
        finally:
            conn.close()

    def get_user_by_email(self, email: str) -> Optional[Dict]:
        """
        根据邮箱获取用户信息
        返回：用户信息字典，不存在返回 None
        """
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT id, email, hashed_password, created_at
            FROM users
            WHERE email = ?
        ''', (email,))

        row = cursor.fetchone()
        conn.close()

        return dict(row) if row else None

    def update_user_password(self, email: str, new_hashed_password: str) -> bool:
        """
        更新用户密码
        返回：更新成功返回 True，用户不存在返回 False
        """
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            UPDATE users SET hashed_password = ? WHERE email = ?
        ''', (new_hashed_password, email))

        success = cursor.rowcount > 0
        conn.commit()
        conn.close()

        return success

    # ==================== 验证码相关方法 ====================

    def save_verification_code(self, email: str, code: str, purpose: str) -> None:
        """
        保存验证码（有效期 5 分钟）
        """
        conn = self.get_connection()
        cursor = conn.cursor()

        # 验证码 5 分钟后过期
        expires_at = (datetime.now() + timedelta(minutes=5)).strftime('%Y-%m-%d %H:%M:%S')

        cursor.execute('''
            INSERT INTO verification_codes (email, code, purpose, expires_at)
            VALUES (?, ?, ?, ?)
        ''', (email, code, purpose, expires_at))

        conn.commit()
        conn.close()

    def get_latest_code(self, email: str, purpose: str) -> Optional[Dict]:
        """
        获取指定邮箱最新的一条未使用验证码
        返回：验证码信息 {"code", "expires_at"}，不存在或已过期返回 None
        """
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT code, expires_at
            FROM verification_codes
            WHERE email = ? AND purpose = ? AND used = 0
            ORDER BY created_at DESC
            LIMIT 1
        ''', (email, purpose))

        row = cursor.fetchone()
        conn.close()

        if not row:
            return None

        result = dict(row)

        # 检查是否已过期
        expires_at = datetime.strptime(result['expires_at'], '%Y-%m-%d %H:%M:%S')
        if datetime.now() > expires_at:
            return None

        return result

    def mark_code_used(self, email: str, code: str, purpose: str) -> None:
        """标记验证码为已使用"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            UPDATE verification_codes SET used = 1
            WHERE email = ? AND code = ? AND purpose = ?
        ''', (email, code, purpose))

        conn.commit()
        conn.close()
