"""
数据库服务 —— 统一入口

根据环境变量 DB_TYPE 自动选择数据库实现：
  - sqlite（默认）→ 使用本地 SQLite 文件
  - postgresql    → 使用 PostgreSQL（未来扩展）

对外暴露 5 个函数，routes.py 的 import 语句无需任何修改：
  from app.services.database import (
      init_db, save_message, get_history,
      get_all_sessions, delete_session
  )
"""

from .config import DB_TYPE

# ========================================
# 根据配置选择数据库实现
# ========================================

_db_instance = None

if DB_TYPE == "sqlite":
    from .sqlite_impl import SQLiteDatabase
    _db_instance = SQLiteDatabase()
elif DB_TYPE == "postgresql":
    # 未来扩展：取消下面的注释，创建 postgres_impl.py
    # from .postgres_impl import PostgreSQLDatabase
    # _db_instance = PostgreSQLDatabase()
    raise ImportError(
        "PostgreSQL 实现尚未创建。"
        "请先将 DB_TYPE 设置为 sqlite，或创建 postgres_impl.py 实现 DatabaseBase 接口。"
    )
else:
    raise ValueError(f"不支持的数据库类型：{DB_TYPE}，目前仅支持 sqlite")


# ========================================
# 对外暴露的函数（和原来一模一样）
# ========================================

def init_db():
    """初始化数据库表结构"""
    _db_instance.init_db()


def save_message(session_id: str, role: str, content: str,
                 query_type: str = None, sources: str = None):
    """保存一条对话记录"""
    _db_instance.save_message(session_id, role, content, query_type, sources)


def get_history(session_id: str, limit: int = 50) -> list:
    """获取某个会话的历史记录"""
    return _db_instance.get_history(session_id, limit)


def get_all_sessions() -> list:
    """获取所有会话列表"""
    return _db_instance.get_all_sessions()


def delete_session(session_id: str):
    """删除一个会话的所有记录"""
    _db_instance.delete_session(session_id)


def search_sessions(keyword: str) -> list:
    """按关键词搜索对话历史"""
    return _db_instance.search_sessions(keyword)


def get_db_instance():
    """获取数据库实例（供需要直接访问 db 对象的模块使用）"""
    return _db_instance
