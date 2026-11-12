# 数据库与 Navicat

## 本地连接

Docker Desktop 启动后，在项目根目录执行：

```powershell
docker compose -f infra/compose.yml up -d postgres
```

当前固定为 PostgreSQL 18.6，足以支撑账户、城市、记忆和媒体元数据。首次加入地理围栏或轨迹空间查询时，再在 PostgreSQL 18 同主版本上启用 PostGIS；当前阶段不提前引入未使用的空间扩展。

Navicat 新建 PostgreSQL 连接：

| 配置 | 默认值 |
|---|---|
| Host | `127.0.0.1` |
| Port | `5433` |
| Database | `voyaura` |
| Username | `voyaura` |
| Password | `voyaura_dev_only` |

这些值只用于本地开发。共享或部署前必须修改 `.env` 中的密码。
Voyaura 使用 `5433`，以避开本机其他项目通常占用的 PostgreSQL 默认端口 `5432`。

## 迁移和种子数据

```powershell
cd api
python -m alembic -c alembic.ini upgrade head
python -m app.seed
```

`app.seed` 是幂等的：重复执行不会重复创建用户或城市。

可以在 Navicat 中执行以下只读查询确认首位测试者：

```sql
SELECT username, display_name, role, is_test_user
FROM users
WHERE username = 'AuroraRovella';
```

## 当前表

### users

账户基础资料。初始种子包含 `AuroraRovella`，但认证功能尚未启用，所以 `password_hash` 为空。

### cities

城市字典，使用高德 `adcode` 作为外部稳定标识。初始仅放入界面与接入测试需要的少量城市。

### city_visits

用户与城市之间的真实到访关系。只有定位确认或用户主动补录后才创建。`check_in_source` 记录 `device`、`ip` 或 `manual`，不保存本次精确定位坐标。

### city_memories

用户在已点亮城市中的文字记忆。保存标题、正文、发生时间和可见范围。`client_request_id` 与用户组成唯一约束，防止网络重试产生重复记忆；创建、编辑和删除均要求先预览再最终确认。

### memory_mutations

文字记忆编辑与删除的幂等操作记录。保存目标记忆 ID、操作类型、请求指纹和响应快照；`client_request_id` 与用户组成唯一约束。重复确认返回首次操作结果，同一请求编号被用于其他记忆或不同内容时返回冲突。删除后仍保留操作记录，因此前端网络重试不会把“已经删除”误报成“找不到记忆”。

### media_assets

照片与 Vlog 的媒体元数据，包括原文件与缩略图对象键、原始文件名、MIME 类型、尺寸、视频时长、私有可见性、EXIF 状态、安全扫描状态和异步处理生命周期。数据库不保存二进制文件；浏览器使用 15 分钟有效的 MinIO 签名 PUT 地址直传，读取原文件和预览图时也只返回短时签名 GET 地址。只有 `upload_status=ready` 的记录会进入城市详情和统计。

`client_request_id` 唯一约束防止重复创建上传任务。`pending` 和 `processing` 会预留配额，过期的 `pending` 任务不再占用配额；格式、大小、内容、安全扫描或衍生图生成失败后记录为 `failed`。照片在完成接口中应用 EXIF 方向并重新编码，不保留 EXIF 和其他原始元数据。

`scan_status` 依次为 `pending`、`scanning`、`clean`，也可能进入 `infected` 或 `error`。`thumbnail_key`、`thumbnail_mime_type`、`thumbnail_width` 和 `thumbnail_height` 描述 WebP 预览；`processing_error` 保存可排查但不含密钥的错误说明，`processed_at` 记录处理完成时间。恶意文件会从 MinIO 删除并标记 `MEDIA_MALWARE_DETECTED`。

过期清理只锁定并删除 `upload_status=pending` 且 `upload_expires_at` 已过期的行，避免与上传完成接口竞争。`processing`、`ready` 和 `failed` 不会被定时清理；其中失败任务可在城市档案中由用户重试或删除。

### media_mutations

媒体删除的幂等操作记录。保存用户、城市、目标记忆、目标媒体、操作类型、请求指纹和响应快照。`user_id + client_request_id` 唯一约束保证网络重试不会重复执行删除；记录不对目标媒体建立外键，因此原文件、缩略图和 `media_assets` 行删除后仍能识别同一次确认请求。

不要直接在 Navicat 中删除 `media_assets` 行：这样会遗留 MinIO 对象并绕过二次确认和幂等记录。应通过媒体删除预览/确认接口操作。

### image_generation_jobs

照片风格生成任务。记录用户、城市、记忆、私有源照片、Provider、风格、最终 Prompt、收藏状态 `is_favorite`、任务状态和私有输出对象键。`user_id + client_request_id` 保证重复确认不会创建多项任务；状态依次为 `queued`、`running`、`succeeded` 或 `failed`。

ComfyUI 的 `prompt_id` 只保存在 `provider_job_id`，Provider 返回的非敏感输出描述保存在 `provider_metadata`。生成图片本身存放在 MinIO，并统一重新编码为 WebP，不在数据库中保存二进制内容。删除源照片或整段记忆时，业务接口会同时删除生成图与任务记录。

`0011_image_recipes` 新增 `preservation_level` 和
`recipe_snapshot`。前者记录创建任务时选择的“平衡/高保真”，后者保存当时使用的
Recipe 版本、画幅、布局、焦点、排版、颜色与纹理，避免风格目录升级后历史作品失去
可解释性。ComfyUI workflow 中可识别的 checkpoint/UNet/模型名称保存在
`provider_metadata.model_names`，不单独建立模型表。

`0012_image_captions` 新增 `caption_mode` 和 `caption_snapshot`。选择
`travel_stamp` 时，任务创建阶段会冻结记忆标题、城市名和记忆日期；worker 在
Provider 输出完成后使用 Pillow 写入这些文字。即使之后编辑城市记忆，历史生成图的
文字来源仍可追溯。默认 `none` 不进行任何文字排版。

`0013_xiaoxi_photo` 新增 `companion_snapshot`。只在用户选择小曦合照且
授权素材配置完整时写入，保存素材版本、站位、尺寸、动作、表情、合成方法和展示
声明，不保存本机素材路径。生成输出仍使用原来的 MinIO 私有对象，删除图片任务会
同时删除合照结果。

### image_job_mutations

图片任务删除的幂等记录。保存用户、已删除的任务 ID、操作类型、请求编号和响应快照。`user_id + client_request_id` 唯一约束保证网络重试不会重复执行删除。`target_job_id` 刻意不建立外键，因此任务行删除后仍能识别同一次确认请求。

不要直接在 Navicat 中删除 `image_generation_jobs`：这样可能遗留 MinIO 生成图，也会绕过运行中保护、二次确认和幂等记录。应使用图片任务删除预览与确认接口。

## 后续表计划

- `trips`、`trip_days`、`trip_members`
- `pois`、`routes`、`weather_snapshots`
- `vlogs`（若后续需要独立于 `media_assets` 的视频业务字段）
- `generation_jobs`、`generated_assets`、`style_presets`
- `publish_drafts`、`source_links`
- `xiaoxi_memories`、`conversation_threads`

每次增加表都必须通过 Alembic 迁移，不能直接在 Navicat 中修改生产结构。Navicat 用于查看、查询和辅助调试。

