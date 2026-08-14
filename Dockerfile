# 法律智能助手 - Docker 镜像
# 构建: docker build -t legal-ai-assistant .
# 运行: docker run -p 8000:8000 --env-file .env legal-ai-assistant

FROM python:3.12-slim

# 设置工作目录
WORKDIR /app

# 使用阿里云镜像加速 apt 和 pip（国内环境）
RUN sed -i 's|deb.debian.org|mirrors.aliyun.com|g' /etc/apt/sources.list.d/debian.sources && \
    apt-get update && apt-get install -y --no-install-recommends gcc && \
    rm -rf /var/lib/apt/lists/*

# 使用清华镜像加速 pip
RUN pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple

# 复制依赖文件并安装
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制项目代码
COPY backend/ .

# 创建数据目录（ChromaDB 向量库 + SQLite）
RUN mkdir -p app/data/chroma_db app/data/exports

# 使用 HuggingFace 国内镜像（sentence-transformers 下载模型）
ENV HF_ENDPOINT=https://hf-mirror.com

# 暴露端口
EXPOSE 8000

# 启动命令
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
