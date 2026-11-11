# 错误代码与排查

## API 错误格式

所有业务错误统一返回：

```json
{
  "error": {
    "code": "AMAP_INVALID_SIGNATURE",
    "message": "高德 Web 服务开启了数字签名，但本次请求未通过签名验证。",
    "details": { "provider_infocode": "10007" },
    "retryable": false,
    "request_id": "d88b4a93917a"
  }
}
```

响应头同时包含 `X-Request-ID`。排查后端日志时优先使用这个编号，不记录或输出高德 Key。

## 地图与定位

| 错误代码 | 含义 | 处理方式 |
|---|---|---|
| `AMAP_CONFIG_MISSING` | 前端缺少 JS Key 或 `securityJsCode` | 检查 `web/.env.local` 并重启 Vite |
| `AMAP_JS_LOAD_FAILED` | 高德 JS API 加载失败 | 检查 Key 类型、域名白名单、安全密钥和网络 |
| `LOCA_LAYER_FAILED` | Loca 点图层加载失败 | 地图仍可使用；检查 Loca 2.0 权限并刷新 |
| `LOCATION_NOT_SUPPORTED` | 浏览器不支持定位 | 更换现代浏览器或使用后续的手工补录 |
| `LOCATION_PERMISSION_DENIED` | 用户拒绝位置权限 | 在浏览器站点权限中允许定位 |
| `LOCATION_UNAVAILABLE` | 系统无法取得位置 | 开启系统定位服务后重试 |
| `LOCATION_TIMEOUT` | 高精度和普通精度两次定位均超时 | 使用网络城市建议或手动选城，并检查系统定位服务 |
| `AMAP_IP_CITY_FAILED` | 高德 JS 无法根据网络判断城市 | 改用手动选城并检查 JS API 权限 |
| `AMAP_IP_CITY_INVALID` | 网络城市结果缺少 `adcode` 或中心点 | 改用手动选城并记录高德返回状态 |
| `AMAP_CITY_SEARCH_FAILED` | 高德 JS 行政区搜索失败 | 检查 JS Key、安全密钥、网络和调用额度 |
| `CITY_SEARCH_EMPTY` | 没有匹配到手动输入的城市 | 输入完整城市名，例如“广州市” |

## 高德 Web 服务

| 错误代码 | 高德码 | 处理方式 |
|---|---:|---|
| `AMAP_KEY_MISSING` | - | 在 `api/.env` 配置 `VOYAURA_AMAP_WEB_KEY` |
| `AMAP_INVALID_KEY` | `10001` | Key 错误或已过期，重新创建 Web 服务 Key |
| `AMAP_SERVICE_UNAVAILABLE` | `10002` | Key 没有相应接口权限，检查绑定服务 |
| `AMAP_DAILY_LIMIT` | `10003` | 今日额度耗尽，等待恢复或调整配额 |
| `AMAP_RATE_LIMIT` | `10004` | 调用过快，稍后重试并增加缓存/限流 |
| `AMAP_IP_NOT_ALLOWED` | `10005` | 将服务器出口 IP 加入白名单 |
| `AMAP_DOMAIN_NOT_ALLOWED` | `10006` | 修正高德控制台域名白名单 |
| `AMAP_INVALID_SIGNATURE` | `10007` | 关闭数字签名，或配置 `VOYAURA_AMAP_WEB_PRIVATE_KEY` |
| `AMAP_PLATFORM_MISMATCH` | `10009` | 不要使用 JS API Key 调用 Web 服务 |
| `AMAP_INSUFFICIENT_PRIVILEGES` | `10012` | 为 Key 开通目标服务权限 |
| `AMAP_SERVER_BUSY` | `10016` | 高德繁忙，稍后重试 |
| `AMAP_OUTSIDE_CHINA` | `20011` | 坐标超出高德境内服务范围 |
| `AMAP_PROXY_CONFIG_ERROR` | - | 安装 `httpx[socks]` 或修正系统代理配置 |
| `AMAP_NETWORK_ERROR` | - | 检查代理、DNS、证书与网络连接 |

## 通用错误

| 错误代码 | 含义 | 处理方式 |
|---|---|---|
| `API_NETWORK_ERROR` | 浏览器无法连接 FastAPI | 确认 API 已启动、端口为 `8001`、CORS 配置正确 |
| `VALIDATION_ERROR` | 请求参数不合法 | 查看 `details.fields` 中的字段与原因 |
| `USER_NOT_FOUND` | 用户不存在 | 检查用户名或重新执行种子脚本 |
| `CITY_NOT_FOUND` | `adcode` 对应城市不存在 | 检查城市编码和城市种子数据 |
| `CITY_NOT_VISITED` | 当前用户尚未点亮该城市 | 先完成定位预览和确认点亮，不得伪造到访记录 |
| `MEMORY_CONTEXT_LOST` | 前端记忆编辑上下文已失效 | 重新打开城市档案并填写记忆 |
| `MEMORY_IDEMPOTENCY_CONFLICT` | 同一请求编号被用于其他城市 | 生成新的请求编号，不要自动覆盖原记忆 |
| `MEMORY_TITLE_EMPTY` | 标题去除空格后为空 | 填写至少一个可见字符后重新预览 |
| `MEMORY_NOT_FOUND` | 目标记忆不存在、已删除或不属于当前用户/城市 | 刷新城市档案；不要对未知记忆重复生成新的删除请求 |
| `MEMORY_MUTATION_IDEMPOTENCY_CONFLICT` | 编辑/删除请求编号被用于其他目标、操作或内容 | 保留原请求用于原操作，为新的变更生成新的请求编号 |
| `INTERNAL_SERVER_ERROR` | 未捕获异常 | 使用 `request_id` 检索后端日志 |

## 媒体上传

| 错误代码 | 含义 | 处理方式 |
|---|---|---|
| `MEDIA_FILENAME_INVALID` | 文件名为空、过长或含控制字符 | 重新命名文件后选择 |
| `MEDIA_TYPE_UNSUPPORTED` | MIME 类型不在允许列表 | 使用 JPEG、PNG、WebP、MP4、MOV 或 WebM |
| `MEDIA_FILENAME_MISMATCH` | 扩展名与 MIME 类型不一致 | 不要只修改后缀，导出为正确格式 |
| `MEDIA_FILE_TOO_LARGE` | 照片超过 20 MB 或 Vlog 超过 500 MB | 压缩文件后重新创建上传任务 |
| `MEDIA_QUOTA_EXCEEDED` | 用户 2 GB 私有媒体配额不足 | 删除不需要的媒体或提高配额 |
| `MEDIA_UPLOAD_IDEMPOTENCY_CONFLICT` | 上传请求编号被用于其他文件 | 为新文件生成新的请求编号 |
| `MEDIA_UPLOAD_INTENT_EXPIRED` | 15 分钟签名地址已过期 | 重新选择文件并创建上传任务 |
| `MEDIA_STORAGE_UNAVAILABLE` | API 无法连接 MinIO | 检查 `9000` 端口、容器状态和 API MinIO 配置 |
| `MEDIA_OBJECT_NOT_FOUND` | PUT 尚未完成或对象不存在 | 确认浏览器直传成功后重试完成接口 |
| `MEDIA_UPLOAD_SIZE_MISMATCH` | MinIO 实际大小与声明不一致 | 文件会被拒绝并清理，重新选择原文件 |
| `MEDIA_CONTENT_MISMATCH` | 实际内容或 MinIO Content-Type 与声明不一致 | 使用原始文件重新上传，不要伪造 MIME 类型 |
| `MEDIA_IMAGE_INVALID` | 图片损坏、像素异常或无法解码 | 重新导出静态图片 |
| `MEDIA_IMAGE_ANIMATED_UNSUPPORTED` | 当前版本不支持动态图片 | 转为静态 WebP、JPEG 或 PNG |
| `MEDIA_VIDEO_INVALID` | 视频文件头不符合 MP4/MOV/WebM | 使用受支持编码重新导出 |
| `MEDIA_DIRECT_UPLOAD_NETWORK_ERROR` | 浏览器无法访问签名 MinIO 地址 | 检查 MinIO、CORS 和签名 URL 的主机地址 |
| `MEDIA_DIRECT_UPLOAD_FAILED` | MinIO 拒绝 PUT | 查看 HTTP 状态并确认签名未过期 |

## 本地基础设施

| 现象 | 原因 | 处理方式 |
|---|---|---|
| `couldn't find env file: voyaura/.env` | 项目根目录缺少 Docker Compose 环境文件 | 在 `voyaura/` 执行 `Copy-Item .env.example .env` |
| 拉取镜像返回 `EOF`，地址包含 `docker.mirrors.ustc.edu.cn` | Docker Hub 全局镜像站不可用，并非 Compose 或 `.env` 参数错误 | 使用项目 `.env` 中的 `REDIS_IMAGE` 与 `MINIO_IMAGE`；无需修改全局 Docker 设置 |
| Redis 显示 `Interrupted` | Compose 中另一个镜像拉取失败后，Redis 拉取被连带中断 | 修正失败镜像后重新执行 `docker compose --env-file .env -f infra/compose.yml up -d` |
| 容器启动但状态不是 `healthy` | 服务仍在初始化或持久化卷/端口存在问题 | 运行 `docker compose --env-file .env -f infra/compose.yml ps`，再用 `logs SERVICE` 查看对应日志 |

基础设施验收命令：

```powershell
docker compose --env-file .env -f infra/compose.yml ps
docker compose --env-file .env -f infra/compose.yml exec redis redis-cli ping
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:9000/minio/health/live
```

## 当前已知阻塞

截至 2026-11-11，本机高德 JS API、行政区图层和 Loca 2.0 已加载成功；Web 服务 Key 返回 `10007 / INVALID_USER_SIGNATURE`。在高德控制台关闭该 Key 的“数字签名”，或把对应私钥写入 `api/.env` 后，重启 API 再验证点亮流程。该错误当前会携带 CORS、`X-Request-ID`、高德 `infocode` 和可重试标记，方便前后端联合排查。
