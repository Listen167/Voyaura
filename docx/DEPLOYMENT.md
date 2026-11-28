# Voyaura 公网部署指南

下面以 Linux 服务器、Docker Engine、Compose v2 和宿主机 Nginx 为例。网页、FastAPI 和 PostgreSQL 由 Compose 运行。宿主机 Nginx 负责公网域名与 HTTPS。已有 Docker 的服务器可直接用部署包构建，Python 和 Node.js 随镜像提供。

## 1. 上传代码

- 首次部署可以上传 Voyaura 的源码部署包，在服务器解压后进入项目目录。包内包含构建文件、迁移和配置模板。
- 有固定更新节奏时，可以从 GitHub 拉取通过检查的提交或标签，然后用同样的 Compose 命令重新构建。GitHub 托管源码，服务器上的 Compose 运行应用。
- 将 `.env.prod` 留在服务器。数据库和媒体文件存放在独立的 Docker 卷里。更新时可保留原有目录、配置和 Compose 项目名 `voyaura-prod`。

## 2. 配置并启动基础版

在项目根目录执行。首次执行时自动生成两个独立的随机值，分别用于数据库密码和档案访问令牌。

```bash
umask 077
if [ ! -f .env.prod ]; then
  cp .env.prod.example .env.prod
  sed -i "s/^POSTGRES_PASSWORD=$/POSTGRES_PASSWORD=$(openssl rand -hex 32)/" .env.prod
  sed -i "s/^VOYAURA_AUTH_TOKEN=$/VOYAURA_AUTH_TOKEN=$(openssl rand -hex 32)/" .env.prod
fi
chmod 600 .env.prod
```

编辑 `.env.prod`。有域名时把 `VOYAURA_PUBLIC_ORIGIN` 填成实际 HTTPS 地址，例如 `https://travel.example.com`，省略末尾斜杠。数据库密码沿用上述十六进制格式，可直接用于数据库连接串。访问令牌至少 32 个字符，对应初始档案 `AuroraRovella`。

| 场景 | 设置 |
| --- | --- |
| 网页和离线行程演练 | 数据库密码、档案访问令牌。网页入口默认绑定服务器 `127.0.0.1:8080`。 |
| 高德地图底图 | `VITE_AMAP_KEY`、`VITE_AMAP_SECURITY_CODE`。在高德控制台限制访问域名。这两项使用现有前端接入，随网页构建交付给浏览器。 |
| 高德地点与路线 | `VOYAURA_AMAP_WEB_KEY`。已开启服务端签名时填写对应的 `VOYAURA_AMAP_WEB_PRIVATE_KEY`。 |
| 小曦在线对话 | `VOYAURA_DEEPSEEK_API_KEY` 用于规划对话。Agent 模型能力另由 `VOYAURA_AGENT_LLM_ENABLED`、`VOYAURA_AGENT_LLM_API_KEY` 控制。在线模型调用仍走界面授权。 |

```bash
docker compose --env-file .env.prod -f infra/compose.prod.yml config --quiet
docker compose --env-file .env.prod -f infra/compose.prod.yml up -d --build --wait
docker compose --env-file .env.prod -f infra/compose.prod.yml ps -a
curl -fsS http://127.0.0.1:8080/health
```

`migrate` 等待 PostgreSQL 就绪，执行升级与初始数据写入，成功后会显示 `Exited (0)`。随后启动 API 和网页。手机或电脑都可访问公网入口。首次临时验证也可以在自己的电脑上执行 `ssh -L 8080:127.0.0.1:8080 用户名@服务器IP`，然后打开本机 `http://127.0.0.1:8080`。若本机 8080 被占用，可以将 SSH 命令的第一个端口改为 18080。

## 3. 配置公网 HTTPS

将域名解析至服务器，开放 TCP 80 和 443。在宿主机 Nginx 的站点配置中设置域名和证书路径。以下示例的证书可由现有云证书或 ACME 客户端提供。

```nginx
server {
    listen 80;
    server_name travel.example.com;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl;
    server_name travel.example.com;
    ssl_certificate /etc/letsencrypt/live/travel.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/travel.example.com/privkey.pem;

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $http_host;
        proxy_read_timeout 180s;
    }
}
```

执行 `sudo nginx -t` 验证配置，再执行 `sudo systemctl reload nginx`。打开首页和 `/plan` 后直接刷新，查看 `/health` 与 `/docs`。在「我的档案」使用服务端令牌连接 `AuroraRovella`，再从计划页体验离线演练。Apifox 可导入 `/openapi.json`，需要授权的接口填写 Bearer Token。网页、API 和定位通过同一个 HTTPS 入口使用。只有公网 IP 时，可继续用 SSH 转发验收，再按实际入口配置受信任的证书。

使用 Navicat 时，推荐通过 SSH 连接服务器。若需要数据库端口，给 `postgres` 加一个仅回环监听的 Compose 覆盖配置 `127.0.0.1:5433:5432`，再用 SSH 转发访问。

## 4. 可选的照片与 Vlog

基础版适合行程和文字档案演示。照片和 Vlog 另需 MinIO、Redis、ClamAV 和包含 FFmpeg 的 Worker。开启前需为 MinIO 准备独立 HTTPS 域名，例如 `media.travel.example.com`。API 和浏览器需要都能解析并访问该域名，MinIO 生成的预签名 URL 会使用它。

在 `.env.prod` 填写 `VOYAURA_MINIO_ENDPOINT=media.travel.example.com`、`VOYAURA_MINIO_ACCESS_KEY` 及用 `openssl rand -hex 32` 生成的 `VOYAURA_MINIO_SECRET_KEY`。`VOYAURA_PUBLIC_ORIGIN` 应与网页的 HTTPS 来源完全一致，Compose 会据此配置 MinIO 的 CORS。

参照上节为 `media.travel.example.com` 添加 HTTPS 站点，用以下配置替换其 `location`。将该站点的域名和证书路径一起更新。

```nginx
location / {
    proxy_pass http://127.0.0.1:19000;
    proxy_set_header Host $http_host;
    proxy_http_version 1.1;
    proxy_request_buffering off;
    proxy_buffering off;
    client_max_body_size 500m;
    proxy_read_timeout 180s;
}
```

预签名 URL 的请求路径、查询参数和 `Host` 原样转发给 MinIO。ClamAV 初次同步扫描库需要等待。后续启动、查看日志和更新媒体部署时都带上两份 Compose 文件。扫描器与反向代理均按当前 Vlog 上限 500 MiB 配置。

```bash
docker compose --env-file .env.prod -f infra/compose.prod.yml -f infra/compose.media.yml up -d --build --wait --wait-timeout 360
docker compose --env-file .env.prod -f infra/compose.prod.yml -f infra/compose.media.yml exec media-worker python -m scripts.media_pipeline_smoke
```

影像风格生成还需要可访问的 ComfyUI、工作流和独立图片 Worker。媒体部署先跑通后，再参照现有的节点映射与 Worker 说明接入。 [ComfyUI 接入](07-comfyui-integration.md) · [Worker 说明](../worker/README.md)

## 5. 更新与错误排查

升级已有实例前，先备份 PostgreSQL 与已启用的媒体存储。使用新源码后重新执行相应的 `up -d --build --wait`，再检查健康端点、迁移日志和登录。更新构建参数中的高德 JS 配置也执行同一条命令。

```bash
umask 077
docker compose --env-file .env.prod -f infra/compose.prod.yml exec -T postgres pg_dump -U voyaura -d voyaura -Fc > "voyaura-$(date +%F).dump"
docker compose --env-file .env.prod -f infra/compose.prod.yml logs --tail=100 migrate api web
```

| 现象 | 排查方法 |
| --- | --- |
| `Set POSTGRES_PASSWORD` 或 `Set VOYAURA_AUTH_TOKEN` | 从源码根目录执行命令，检查服务器 `.env.prod` 已填值。 |
| `migrate` 退出码非 0 | 查 `migrate` 和 `postgres` 日志，核对数据库密码和迁移版本。已有数据库的密码变更需要同步更新 PostgreSQL 角色。 |
| `EOF` 或镜像拉取超时 | 核对服务器能访问所用镜像仓库。基础镜像默认使用 AWS Public ECR 的 Docker Official Images 镜像源。可在 `.env.prod` 指定 `PYTHON_IMAGE`、`NODE_IMAGE`、`NGINX_IMAGE` 或 `POSTGRES_IMAGE`。 |
| 网页能开但接口 `502` | 先请求服务器本机的 `/health`，再核对宿主机 Nginx 的 `proxy_pass` 与 `VOYAURA_WEB_PORT` 一致。 |
| `AUTH_REQUIRED` 或 `AUTH_NOT_CONFIGURED` | 分别核对客户端提交的令牌和服务器配置。重启后使用服务器对应的令牌登录。 |
| 媒体 `403`、上传失败或长时间处理中 | 检查媒体域名证书、Nginx 是否保留 `Host`、MinIO CORS 来源，以及 Worker、Redis、ClamAV 的日志和状态。 |
