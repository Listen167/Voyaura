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

照片与 Vlog 的媒体元数据，包括对象存储键、原始文件名、MIME 类型、尺寸、视频时长、私有可见性、EXIF 处理状态和上传生命周期。数据库不保存二进制文件；浏览器使用 15 分钟有效的 MinIO 签名 PUT 地址直传。只有 `upload_status=ready` 的记录会进入城市详情和统计。

`client_request_id` 唯一约束防止重复创建上传任务。`pending` 会预留配额，过期任务不再占用配额；格式、大小或内容校验失败后记录为 `failed`。照片在完成接口中应用 EXIF 方向并重新编码，不保留 EXIF 和其他原始元数据。

## 后续表计划

- `trips`、`trip_days`、`trip_members`
- `pois`、`routes`、`weather_snapshots`
- `vlogs`（若后续需要独立于 `media_assets` 的视频业务字段）
- `generation_jobs`、`generated_assets`、`style_presets`
- `publish_drafts`、`source_links`
- `xiaoxi_memories`、`conversation_threads`

每次增加表都必须通过 Alembic 迁移，不能直接在 Navicat 中修改生产结构。Navicat 用于查看、查询和辅助调试。

