"""
数据库配置文件

通过环境变量 DB_TYPE 控制使用哪种数据库：
  - "sqlite"（默认）：本地 SQLite 文件数据库，零配置
  - "postgresql"：PostgreSQL（需要安装 psycopg2 并配置连接信息）

切换方式：只需设置环境变量，无需改任何代码
  Windows PowerShell:  $env:DB_TYPE = "postgresql"
  Linux/Mac:          export DB_TYPE="postgresql"
"""

import os

# 数据库类型：sqlite 或 postgresql（默认 sqlite）
DB_TYPE = os.getenv("DB_TYPE", "sqlite")

# PostgreSQL 连接配置（仅当 DB_TYPE=postgresql 时生效）
# 可以通过环境变量单独设置每一项，也可以直接设置 DATABASE_URL
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")
POSTGRES_DB = os.getenv("POSTGRES_DB", "legal_assistant")
POSTGRES_USER = os.getenv("POSTGRES_USER", "postgres")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "")

# 完整的 PostgreSQL 连接 URL
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
)
