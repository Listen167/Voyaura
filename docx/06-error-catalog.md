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
| `AMAP_POI_NOT_FOUND` | - | 地点 ID 已失效或高德没有返回详情，重新搜索该地点 |
| `AMAP_POI_INVALID` | - | 高德地点缺少 ID、名称或合法坐标；记录请求编号并稍后重试 |
| `AMAP_ROUTE_NOT_FOUND` | - | 高德没有返回对应方式的路线；检查端点、城市和交通方式 |
| `ROUTE_TRANSIT_ADCODE_REQUIRED` | - | 公交地铁查询缺少起终点城市代码；同时提交两个 `adcode` |
| `INTERCITY_PROVIDER_NOT_CONFIGURED` | - | 铁路或航班 Provider 尚未授权配置；查看 `10-route-provider-strategy.md` |

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
| `MEDIA_UPLOAD_CANCELLED` | 用户取消了正在进行的 MinIO PUT | 返回上传预览页；需要时可使用原上传任务重新上传 |
| `MEDIA_QUEUE_UNAVAILABLE` | API 或 worker 无法连接 Redis 媒体队列 | 检查 `6379` 端口、Redis 容器和 `VOYAURA_REDIS_URL`；该错误可重试 |
| `MEDIA_SCANNER_UNAVAILABLE` | Defender/ClamAV 不可用、超时或返回未知结果 | 检查 Defender 状态或 ClamAV 地址；修复后可在上传窗口重试 |
| `MEDIA_SCANNER_CONFIG_ERROR` | 扫描 Provider 名称无效 | 修正 `VOYAURA_MEDIA_SCANNER_PROVIDER` 为 `windows_defender` 或 `clamav` |
| `MEDIA_MALWARE_DETECTED` | 文件未通过安全扫描 | 原文件已从 MinIO 删除；不要重试该对象，重新检查来源文件 |
| `MEDIA_THUMBNAIL_FAILED` | 已上传图片无法生成 WebP 缩略图 | 重新导出静态图片后上传 |
| `MEDIA_VIDEO_PROCESSING_FAILED` | ffprobe 无法读取视频或 FFmpeg 无法生成封面 | 使用受支持编码重新导出视频，并检查 FFmpeg 日志 |
| `MEDIA_PROCESSING_ERROR` | worker 发生未识别处理错误 | 查看 worker 日志；状态接口会标记为可重试 |
| `MEDIA_PROCESSING_TIMEOUT` | 前端等待处理超过约 2 分钟 | 确认 worker 正在运行后点击重试，不需要重新 PUT 已上传文件 |
| `MEDIA_UPLOAD_CONTEXT_LOST` | 前端丢失当前上传任务信息 | 关闭上传窗口并重新选择文件 |
| `MEDIA_ASSET_NOT_FOUND` | 媒体记录不存在、已删除或不属于当前记忆 | 刷新城市档案和任务列表，不要为未知媒体重复创建删除请求 |
| `MEDIA_UPLOAD_FAILED_STATE` | 失败原因不可恢复，不能复用原任务 | 删除失败任务并重新选择原文件创建上传任务 |
| `MEDIA_UPLOAD_ALREADY_COMPLETE` | 上传任务已经处理完成 | 刷新城市档案，无需再次调用完成接口 |
| `MEDIA_DELETE_PROCESSING_CONFLICT` | 媒体正由 worker 处理，暂不能删除 | 等待任务进入 `ready` 或 `failed` 后重试删除 |
| `MEDIA_MUTATION_IDEMPOTENCY_CONFLICT` | 删除请求编号被用于另一媒体或操作 | 为新的删除操作生成新的 `client_request_id` |

失败任务列表只把 `MEDIA_QUEUE_UNAVAILABLE`、`MEDIA_SCANNER_UNAVAILABLE`、`MEDIA_STORAGE_UNAVAILABLE` 和 `MEDIA_PROCESSING_ERROR` 标记为可重试。重试会复用已经上传的私有对象并重新进入 Redis 队列，不会要求浏览器再次上传文件。恶意文件、格式错误和衍生图生成失败不自动重试。

## 媒体清理

| 错误代码/现象 | 含义 | 处理方式 |
|---|---|---|
| `MEDIA_CLEANUP_LIMIT_INVALID` | 手动清理命令的 `--limit` 小于等于 0 | 改用正整数，例如 `--limit 100` |
| 清理结果包含 `failures` | 删除 MinIO 对象时发生可识别错误 | 根据其中的 `asset_id`、`code` 和 `message` 排查存储服务，再次运行清理 |

只清理签名地址已经过期且状态仍为 `pending` 的任务。`processing`、`ready`、`failed` 和真实旅行记忆不会被自动删除。手动执行：

```powershell
cd api
.\.venv\Scripts\python.exe -m app.media_cleanup --limit 100
```

## 图片风格生成与 ComfyUI

| 错误代码 | 含义 | 处理方式 |
|---|---|---|
| `IMAGE_PROVIDER_NOT_CONFIGURED` | 图片 Provider 被禁用或 ComfyUI 配置不完整 | 按 `07-comfyui-integration.md` 配置 Provider、workflow 路径和节点 ID |
| `IMAGE_PROVIDER_UNSUPPORTED` | `VOYAURA_IMAGE_PROVIDER` 不是受支持值 | 当前使用 `disabled` 或 `comfyui` |
| `IMAGE_STYLE_NOT_FOUND` | 请求了不存在的风格 ID | 重新读取 `GET /api/v1/image-styles` |
| `IMAGE_SOURCE_NOT_FOUND` | 源照片不存在或不属于当前用户 | 刷新城市影像页并重新选择照片 |
| `IMAGE_SOURCE_NOT_READY` | 源文件不是已完成安全处理的照片 | 等待媒体任务完成；Vlog 暂不进入图片风格生成 |
| `IMAGE_JOB_IDEMPOTENCY_CONFLICT` | 同一请求编号用于不同照片、风格或 Prompt | 为新的创作生成新的 `client_request_id` |
| `IMAGE_JOB_NOT_FOUND` | 生成任务不存在、已删除或不属于当前用户 | 刷新视觉工作台，不要继续使用过期任务 ID |
| `IMAGE_JOB_DELETE_RUNNING_CONFLICT` | 任务正在由图片 worker 生成，暂不能删除 | 等待任务成功或失败后再删除；工作台会自动刷新状态 |
| `IMAGE_JOB_MUTATION_IDEMPOTENCY_CONFLICT` | 删除请求编号已用于另一任务或操作 | 为新的删除操作生成新的 `client_request_id` |
| `IMAGE_QUEUE_UNAVAILABLE` | 无法连接图片 Redis 队列 | 检查 Redis 和 `VOYAURA_IMAGE_QUEUE_KEY` |
| `COMFYUI_WORKFLOW_INVALID` | workflow JSON 无法读取或不是 API format | 在 ComfyUI 使用 Save (API Format) 重新导出 |
| `COMFYUI_WORKFLOW_NODE_MISSING` | 配置的节点 ID 不存在或没有目标输入 | 检查 LoadImage、正/负 Prompt 和输出节点 ID |
| `COMFYUI_UNAVAILABLE` | ComfyUI 网络、上传、提交或下载失败 | 确认 `8188` 可访问并查看 ComfyUI 控制台 |
| `COMFYUI_GENERATION_FAILED` | workflow 节点执行失败 | 在 ComfyUI 中使用相同 workflow 检查模型和节点错误 |
| `COMFYUI_TIMEOUT` | 等待 `/history/{prompt_id}` 超时 | 调大超时或检查显存、队列和模型加载状态 |
| `COMFYUI_OUTPUT_MISSING` | workflow 完成但没有图片输出 | 配置 SaveImage/PreviewImage 输出节点 |
| `IMAGE_PROVIDER_OUTPUT_INVALID` | Provider 返回的内容不是可解码图片 | 检查输出节点和自定义节点返回格式 |
| `IMAGE_CAPTION_INVALID` | 旅行印记缺少标题、地点或日期 | 刷新城市记忆后重新创建任务，不要手工拼接缺失字段 |
| `IMAGE_CAPTION_STYLE_INVALID` | 旅行印记使用了不支持的版式、颜色或字体组合 | 重新读取前端选项；可用版式为档案横带、明信片角标和竖排印章 |
| `IMAGE_CAPTION_FONT_UNAVAILABLE` | worker 找不到中文字体或配置路径不存在 | 在 `api/.env` 配置 `VOYAURA_IMAGE_CAPTION_FONT_PATH` 并重启图片 worker |
| `IMAGE_CAPTION_RENDER_FAILED` | Pillow 无法把旅行印记写入生成图 | 检查字体文件、Provider 输出图片和图片 worker 日志 |
| `XIAOXI_ASSET_NOT_CONFIGURED` | 未配置授权素材、文件不存在或版本号缺失 | 按 `09-xiaoxi-photo-assets.md` 配置透明 PNG 和素材版本 |
| `XIAOXI_ASSET_ALPHA_REQUIRED` | 小曦素材没有实际透明区域 | 导出带透明背景的 RGBA PNG，不要使用白底图片 |
| `XIAOXI_COMPOSITION_INVALID` | 站位或尺寸不在支持范围 | 重新读取风格能力并选择左右站位和小/中/大尺寸 |
| `XIAOXI_COMPOSITION_FAILED` | worker 无法读取素材或完成合成 | 检查 PNG 完整性、路径权限和图片 worker 日志 |
| `IMAGE_GENERATION_ERROR` | 图片 worker 出现未识别异常 | 使用任务 ID 检索图片 worker 日志 |

生成记录删除分为只读预览与确认两步。确认会删除私有生成图和任务行，但保留原始旅行照片；相同 `client_request_id` 重试返回 `existing`，不会重复删除。下载地址是短期 MinIO 签名 URL，过期后刷新视觉工作台即可获取新地址。

## 本地基础设施

| 现象 | 原因 | 处理方式 |
|---|---|---|
| VS Code 在 `media_cleanup.py`、`media_jobs.py` 或 `tests/test_api.py` 标红 `app.*`、SQLAlchemy、pytest 等导入 | 工作区选中了 Conda，而项目依赖安装在 `api/.venv` | 重新加载 VS Code 窗口；确认解释器为 `voyaura/api/.venv/Scripts/python.exe` |
| `couldn't find env file: voyaura/.env` | 项目根目录缺少 Docker Compose 环境文件 | 在 `voyaura/` 执行 `Copy-Item .env.example .env` |
| 拉取镜像返回 `EOF`，地址包含 `docker.mirrors.ustc.edu.cn` | Docker Hub 全局镜像站不可用，并非 Compose 或 `.env` 参数错误 | 使用项目 `.env` 中的 `REDIS_IMAGE` 与 `MINIO_IMAGE`；无需修改全局 Docker 设置 |
| Redis 显示 `Interrupted` | Compose 中另一个镜像拉取失败后，Redis 拉取被连带中断 | 修正失败镜像后重新执行 `docker compose --env-file .env -f infra/compose.yml up -d` |
| 容器启动但状态不是 `healthy` | 服务仍在初始化或持久化卷/端口存在问题 | 运行 `docker compose --env-file .env -f infra/compose.yml ps`，再用 `logs SERVICE` 查看对应日志 |

基础设施验收命令：

```powershell
docker compose --env-file .env -f infra/compose.yml ps
docker compose --env-file .env -f infra/compose.yml exec redis redis-cli ping
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:9000/minio/health/live
cd api
.\.venv\Scripts\python.exe scripts\media_pipeline_smoke.py
```

媒体功能需要单独运行 worker：在项目根目录执行 `.\worker\run.ps1`。诊断单个队列任务可执行 `.\worker\run.ps1 --once`；若输出 `worker_idle no_job=true`，表示正式队列当前为空，不是错误。

## 当前已知阻塞

截至 2026-11-12，本机高德 JS API、行政区图层和 Loca 2.0 已加载成功；点亮、POI 与路线 Web 服务请求仍返回 `10007 / INVALID_USER_SIGNATURE`。在高德控制台关闭该 Key 的“数字签名”，或把对应私钥写入 `api/.env` 后，重启 API 再验证点亮、地点搜索与路线规划。该错误当前会携带 CORS、`X-Request-ID`、高德 `infocode` 和可重试标记，前端会显示对应请求编号。
