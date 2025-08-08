# 1. 使用官方的 Python 3.11 slim 镜像作为基础
FROM python:3.12-slim

# 2. 设置容器内的工作目录
WORKDIR /app

# 3. 复制依赖文件
COPY ../requirements.txt .

# 4. 安装依赖
# --no-cache-dir 选项可以减小镜像体积
RUN pip install --no-cache-dir -r requirements.txt

# 5. 将后端所有源代码复制到工作目录
# 注意我们把根目录的文件和 tools 文件夹都复制进去
COPY ../agent.py .
COPY ../server.py .
COPY ../api_def.json .
COPY ../mcp_service.py .
COPY ../tools ./tools/

# 6. 暴露服务运行的端口
EXPOSE 8000

# 7. 容器启动时执行的命令
# 使用 0.0.0.0 作为主机，以便 Docker 容器可以从外部访问
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000"]