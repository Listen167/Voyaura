# 第三方组件与素材说明

项目直接依赖的锁定版本见 [前端依赖锁](../web/package-lock.json) 和 [后端依赖锁](../api/requirements-dev.lock)。下表列出关键组件在本项目中的用途。版本升级或重新分发镜像时，以对应上游版本附带的许可证为准。

| 组件 | 在 Voyaura 中的用途 | 许可证或条款 |
| --- | --- | --- |
| [Vue](https://github.com/vuejs/core)、[Vue Router](https://github.com/vuejs/router)、[Vite](https://github.com/vitejs/vite) | 响应式界面、页面路由与前端构建 | MIT |
| [TypeScript](https://github.com/microsoft/TypeScript)、[Playwright](https://github.com/microsoft/playwright) | 类型检查与浏览器验收 | Apache-2.0 |
| [Lucide](https://github.com/lucide-icons/lucide) | 导航、地图和创作页图标 | ISC，继承的 Feather 图标含 MIT 授权 |
| [FastAPI](https://github.com/fastapi/fastapi)、[SQLAlchemy](https://github.com/sqlalchemy/sqlalchemy)、[Alembic](https://github.com/sqlalchemy/alembic) | Web API、数据模型与迁移 | MIT |
| [LangChain](https://github.com/langchain-ai/langchain)、[Pillow](https://github.com/python-pillow/Pillow) | 结构化需求提取、图像缩略图和旅行印记 | LangChain 为 MIT，Pillow 为 HPND |
| [PostgreSQL](https://www.postgresql.org/about/licence/)、SQLite | 正式数据库和单机体验数据库 | PostgreSQL License、SQLite 公有领域 |
| [Redis](https://redis.io/legal/licenses/)、[MinIO](https://github.com/minio/minio) | 可选任务队列与 S3 兼容对象存储 | Redis 7.4 适用 RSALv2 或 SSPLv1，MinIO 上游为 AGPL-3.0 |
| [FFmpeg](https://ffmpeg.org/legal.html)、[ClamAV](https://github.com/Cisco-Talos/clamav)、[ComfyUI](https://github.com/Comfy-Org/ComfyUI) | 可选视频处理、病毒扫描、风格生成工作流 | FFmpeg 随构建选项适用 LGPL 或 GPL，ClamAV 为 GPL-2.0，ComfyUI 为 GPL-3.0 |

高德 SDK 与 Web 服务依照 [高德开放平台条款](https://lbs.amap.com/) 使用。DeepSeek 在线推理由其 [API 服务](https://api-docs.deepseek.com/zh-cn/) 提供。发现页中的 Wikimedia Commons 摄影按单张图片保留署名及授权说明。见 [摄影素材来源](../web/public/discover/credits.html)。

## GC Minimal Zine Poster

Voyaura 的 `minimal_zine_poster` 预设借鉴了 GC Minimal Zine Poster 0.3.1 的部分提示词设计。预设分发范围为改编提示词，MIT 授权声明见下方。[上游项目](https://github.com/LiamGvchi/gc-minimal-zine-poster)

MIT License

Copyright (c) 2026 LiamGvchi

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
