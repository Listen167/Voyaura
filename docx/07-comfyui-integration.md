# ComfyUI 图片风格接入

## 当前边界

Voyaura 已实现 ComfyUI Provider、异步任务 API、Redis 图片队列和独立 worker。默认配置为 `disabled`，因此未准备好 workflow 时只能预览任务，不能误创建“成功”结果。原图和输出图都保持私有，浏览器不会获得 ComfyUI 地址或 workflow JSON。

## 1. 准备 ComfyUI workflow

1. 在 ComfyUI 中完成一个可用的 img2img workflow。
2. workflow 至少包含一个 `LoadImage`、正向 `CLIPTextEncode` 和图片输出节点。
3. 如需负向提示词，保留对应的负向 `CLIPTextEncode`。
4. 使用 **Save (API Format)** 导出 JSON，而不是普通界面 workflow JSON。
5. 记下上述节点在 JSON 顶层的 ID，例如 `10`、`6`、`7`、`9`。

Voyaura 会修改 `LoadImage.inputs.image` 和 Prompt 节点的 `inputs.text`，其余模型、采样器、ControlNet、IP-Adapter 或 LoRA 参数由你的 workflow 自己控制。

## 2. 配置 `api/.env`

```dotenv
VOYAURA_IMAGE_PROVIDER=comfyui
VOYAURA_IMAGE_QUEUE_KEY=voyaura:image:jobs
VOYAURA_COMFYUI_BASE_URL=http://127.0.0.1:8188
VOYAURA_COMFYUI_WORKFLOW_PATH=D:\ComfyUI\workflows\voyaura-api.json
VOYAURA_COMFYUI_INPUT_NODE_ID=10
VOYAURA_COMFYUI_POSITIVE_PROMPT_NODE_ID=6
VOYAURA_COMFYUI_NEGATIVE_PROMPT_NODE_ID=7
VOYAURA_COMFYUI_OUTPUT_NODE_ID=9
VOYAURA_COMFYUI_TIMEOUT_SECONDS=300
VOYAURA_COMFYUI_POLL_INTERVAL_SECONDS=1.5
```

负向 Prompt 和输出节点 ID 可以留空；输出节点留空时 Provider 会搜索 workflow history 中的首张图片。workflow 路径可放在项目外，避免提交本地模型名称或私有路径。
修改 `api/.env` 后必须重启 FastAPI 和图片 worker，Provider 配置不会在常驻进程中自动刷新。

## 3. 启动与检查

```powershell
cd D:\PragramFile\VScode\26.11\Travel\voyaura\api
.\.venv\Scripts\python.exe -m alembic -c alembic.ini upgrade head

cd ..
.\worker\run-image.ps1
```

另一个终端保持 `.\worker\run.ps1` 运行。检查 Provider 能力：

```powershell
Invoke-RestMethod http://127.0.0.1:8001/api/v1/image-styles
```

返回 `available: true` 后，从地图打开已点亮城市，切换到“影像”，点击照片上的魔棒按钮。Vlog 当前不能作为风格源图。

## 4. API 契约

- `GET /api/v1/image-styles`：Provider 可用性与稳定风格 ID。
- `POST /api/v1/image-jobs/preview`：只读验证源照片、风格和最终 Prompt。
- `POST /api/v1/image-jobs`：带 `client_request_id` 的幂等任务创建。
- `GET /api/v1/image-jobs?favorite_only=false`：生成历史；可只返回收藏记录。
- `GET /api/v1/image-jobs/{job_id}`：查询 `queued/running/succeeded/failed` 和私有输出 URL。
- `POST /api/v1/image-jobs/{job_id}/favorite`：收藏或取消收藏。
- `POST /api/v1/image-jobs/{job_id}/delete-preview`：只读删除预览。
- `POST /api/v1/image-jobs/{job_id}/delete-confirm`：幂等删除生成图和任务，保留源照片。

ComfyUI 标准调用顺序为 `/upload/image`、`/prompt`、`/history/{prompt_id}`、`/view`。输出会再次解码并转为 WebP，以移除 Provider 可能写入的元数据。

## 5. 安全与数据清理

- 不要把 ComfyUI 暴露到公网；Voyaura 后端直接访问本机或受信网络地址。
- 不要在 workflow JSON、Prompt 或日志中写 API Key 和个人身份信息。
- 删除源照片或整段城市记忆时，对应生成图和任务会同步删除。
- 当前没有公开发布接口，生成图默认仅自己可见。
- 成功任务返回短期预览 URL 和带建议文件名的短期下载 URL；地址过期后重新查询任务即可。
- 运行中的任务不能删除，避免 worker 写回已不存在的任务；等待状态进入 `succeeded` 或 `failed` 后操作。

## 6. Recipe、模型与原图保真

创建图片任务时必须选择 `balanced` 或 `high` 原图保真级别。API 会把实际
保真级别和风格 Recipe 保存为任务快照；之后更新风格目录不会改写历史任务。
ComfyUI Provider 会从 API-format workflow 的 `ckpt_name`、`unet_name` 或
`model_name` 输入中提取去重后的模型名，并在任务成功后返回给视觉工作台。

`minimal_zine_poster` 预设基于 MIT 授权的 GC Minimal Zine Poster v0.3.1
风格系统，默认使用高保真，重点是 3:5 纸感画幅、大面积留白、一个旅行照片焦点和
单一高彩色。项目保留上游名称、版本、仓库和许可证信息，完整声明见
`THIRD_PARTY_NOTICES.md`。上游示例图片没有复制到 Voyaura。

## 7. 中文旅行印记

风格预览可以选择 `none` 或 `travel_stamp`。后者在任务创建时冻结城市记忆
标题、城市名称和发生日期；ComfyUI 只负责生成画面，图片 worker 随后使用 Pillow
写入可读文字并再次导出无元数据 WebP。

Windows 默认依次查找微软雅黑和黑体，Linux 查找 Noto Sans CJK，macOS 查找
PingFang。部署环境没有这些字体时，在 `api/.env` 明确配置：

```dotenv
VOYAURA_IMAGE_CAPTION_FONT_PATH=D:\Fonts\NotoSansCJKsc-Regular.otf
```

字体路径只由 worker 读取，不返回浏览器。配置不存在时任务会以
`IMAGE_CAPTION_FONT_UNAVAILABLE` 失败，不会回退到无法显示中文的字体。

## 8. 小曦确定性合照

小曦角色不交给 ComfyUI 重绘。Provider 完成背景图片后，worker 读取经授权透明
PNG，根据用户选择的左右站位和小/中/大尺寸进行缩放，加入柔和阴影和轻微亮度匹配，
最后再执行旅行印记排版。这样即使没有 IP-Adapter 或 LoRA，也能保留角色原始外观。

素材未配置时，风格目录返回 `companion.available=false`，前端禁用合照开关；
直接请求创建任务会返回 `XIAOXI_ASSET_NOT_CONFIGURED`。详细素材要求见
`09-xiaoxi-photo-assets.md`。
