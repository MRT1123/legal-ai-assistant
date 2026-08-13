"""
法律智能助手 - FastAPI 应用入口
启动方式：uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from contextlib import asynccontextmanager
import uvicorn
import os

from app.api.routes import router, init_graph
from app.api.auth_routes import router as auth_router


# ==================== 应用生命周期 ====================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时初始化
    print("=" * 60)
    print("🚀 法律智能助手 API 启动中...")
    print("=" * 60)
    init_graph()
    print("✅ 启动完成！")
    print("📘 API 文档：http://localhost:8000/docs")
    print("=" * 60)
    
    yield  # 应用运行中
    
    # 关闭时清理（暂无需）
    print("\n👋 API 正在关闭...")


# ==================== 创建 FastAPI 应用 ====================

app = FastAPI(
    title="法律智能助手 API",
    description="基于 LangGraph 多智能体架构的法律问答系统",
    version="0.1.0",
    lifespan=lifespan
)

# 配置 CORS（允许前端跨域访问）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境应限制具体域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册 API 路由
app.include_router(router)        # 主业务路由（聊天/历史/导出等）
app.include_router(auth_router)   # 认证路由（注册/登录/验证码等）

# 挂载静态文件目录（前端资源）
static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
app.mount("/static", StaticFiles(directory=static_dir), name="static")


# ==================== 首页路由 ====================

@app.get("/")
async def index():
    """首页：返回聊天界面"""
    return FileResponse(os.path.join(static_dir, "index.html"))


# ==================== 启动入口 ====================

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True  # 开发模式：代码修改自动重启
    )
