FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制 mcp_service.py 文件
COPY mcp_service.py .

COPY api_def.json .

# 暴露 mcp_service 监听的端口
EXPOSE 7816

CMD ["python", "mcp_service.py"]