## 🐳 Docker Compose 操作指南

### 🔧 构建服务镜像

```bash
docker-compose build
```

在初次运行或更改了 Dockerfile、依赖文件后使用此命令进行构建。

---

### ✅ 启动服务

```bash
docker-compose up -d
```

使用后台模式启动所有服务容器。

---

### 🌐 访问前端页面

浏览器打开：[http://localhost:5173](http://localhost:5173)

---

### 📊 查看运行状态

```bash
docker-compose ps
```

列出当前项目正在运行的容器及其状态。

---

### 🧾 实时查看日志（适合调试）

#### 🔄 所有服务日志

```bash
docker-compose logs -f
```

#### 🖥️ 后端服务日志

```bash
docker-compose logs -f backend
```

#### 🎨 前端服务日志

```bash
docker-compose logs -f frontend
```

#### 🪱 MCP服务日志

```bash
docker-compose logs -f mcp_service
```

> ✅ 按 `Ctrl + C` 可退出日志查看。

---

### ⛔ 停止并移除容器

```bash
docker-compose down
```

