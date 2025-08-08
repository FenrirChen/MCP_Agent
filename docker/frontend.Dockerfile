# 使用 Node.js 镜像来构建 Vue 应用
FROM node:20-alpine AS build

# 设置工作目录
WORKDIR /app

# 复制 package.json 和 package-lock.json
COPY frontend-Vue3/vue-project/package*.json ./

# 安装依赖
RUN npm install

# 复制所有前端源代码
COPY ../frontend-Vue3/vue-project .

# 执行构建命令
RUN npm run build

# 使用一个轻量的 Nginx 服务器来托管静态文件
FROM nginx:alpine

# 从构建阶段（build）将编译好的静态文件复制到 Nginx 的网站根目录
COPY --from=build /app/dist /usr/share/nginx/html

# 复制 Nginx 配置文件
COPY docker/nginx.conf /etc/nginx/conf.d/default.conf

# 暴露 Nginx 的默认端口
EXPOSE 80