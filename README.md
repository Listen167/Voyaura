# Voyaura · 旅途与故事

Voyaura 是一款面向自由行的旅行规划与记录应用。出发前可以与旅行伙伴小曦讨论目的地和行程，途中可以在中国地图上点亮城市，回来后把照片、Vlog 和文字整理成私人旅行档案。网页支持电脑和手机布局。

## 功能介绍

| 模块 | 当前功能与使用方式 |
| --- | --- |
| 发现与中国地图 | 浏览旅行灵感和城市索引。配置高德 JS API 后显示地图，连接私人档案后按到访城市查看足迹。 |
| 城市点亮 | 支持设备定位预览和手动选城。用户确认后记录到访，可以区分手动记录和设备定位。浏览器定位需要设备授权，并依赖 HTTPS 或 localhost。 |
| 小曦旅行伙伴 | 支持旅行问答、心情交流、景点介绍和地点澄清。可以先询问中山大学的校区，再把选中的校区带进行程。开启界面授权后可调用 DeepSeek 参与对话。 |
| 智能行程 | 根据天数、兴趣、同行者、每日时段及交通偏好检索候选，筛掉停车场、售票处等附属点。按位置分组并结合建议停留和市内路程排每日时间线，支持锁定必去点、继续对话调整及人工确认保存。 |
| 攻略时长与路线证据 | 可以贴入带明确时长的攻略摘录和原文链接。时长会参与重排，页面保留参考区间和出处。可用的步行、公交／地铁和驾车时间来自高德，缺失路段标为待核实。 |
| 城市记忆 | 每个到访城市拥有独立档案，可以记录日期和文字、浏览旅行记忆。配置对象存储、队列、扫描器和 Worker 后支持照片与 Vlog 的上传处理。 |
| 故事和影像创作 | 授权后用已有文字记忆整理故事草稿。影像工作台可浏览风格、作品历史和生成状态。真实风格生成依赖配置好的 ComfyUI，小曦同框还需要授权的透明素材。 |

行程生成采用结构化需求、高德候选、按天分组、日内排序和独立约束检查。开放时间、票价或交通证据不足时，草案会标出待核实项。阶段清单见 [功能实现清单](docx/05-feature-checklist.md)。

## 环境依赖与一键安装

| 环境 | 推荐配置 |
| --- | --- |
| 本地演示 | Windows 或 Linux，Python 3.12（脚本接受 3.11–3.13），Node.js 24 LTS（含 npm），可使用 uv 加速 Python 安装 |
| 公网部署 | Linux 主机、Nginx、Docker Engine 与 Compose v2，使用 PostgreSQL 保存正式数据 |
| 媒体处理 | Redis、兼容 S3 的对象存储、FFmpeg／FFprobe，以及 Windows Defender 或 ClamAV |
| 可选在线能力 | 高德 JS API 与 Web 服务凭证、DeepSeek API Key、ComfyUI 工作流 |

在项目根目录运行。脚本创建 Python 虚拟环境，按锁文件安装前后端依赖，然后初始化独立 SQLite 档案与访问令牌。

```bash
python scripts/install.py
```

默认 Demo 用本地规则和虚拟演练地点即可体验规划流程。服务器仅安装依赖时可执行 `python scripts/install.py --dependencies-only`。已有的 `.local/api.env` 和访问令牌会继续沿用。

## 部署运行步骤

安装完成后，打开两个终端，从项目根目录分别启动 API 和网页。

```powershell
# Windows · 终端 1
.\api\.venv\Scripts\python.exe scripts/local_serve.py api
# Windows · 终端 2
.\api\.venv\Scripts\python.exe scripts/local_serve.py web
```

```bash
# Linux · 终端 1
api/.venv/bin/python scripts/local_serve.py api
# Linux · 终端 2
api/.venv/bin/python scripts/local_serve.py web
```

- 网页演示在 [127.0.0.1:5188](http://127.0.0.1:5188/)。打开计划页可选择「填入离线演练条件」并主动生成草案。
- API 文档在 [127.0.0.1:8018/docs](http://127.0.0.1:8018/docs)。`/health` 提供进程存活检查。
- 在「我的档案」连接测试档案 `AuroraRovella`。令牌在本机 `.local/access-token.txt`，提交材料仅包含配置示例。

公网部署可用 Docker Compose 启动网页、FastAPI、PostgreSQL 和数据库迁移。宿主机 Nginx 提供公网 HTTPS。照片与 Vlog 可按需添加 MinIO、Redis、ClamAV 和媒体 Worker。公开演示地址待补充。 [公网部署与复现指南](docx/DEPLOYMENT.md)

## 项目目录

```text
web/       Vue 3 响应式界面与前端测试
api/       FastAPI、数据库迁移、规划引擎与 API 测试
worker/    媒体处理和图片生成入口及工作流说明
infra/     PostgreSQL、Redis、MinIO 的 Compose 配置
scripts/   一键安装、开发启动与独立验收
docx/      产品、架构、部署、接入及实现清单
```

## 开源组件与第三方服务

前端采用 Vue 3、Vue Router、Vite、TypeScript 和 Lucide。后端采用 FastAPI、SQLAlchemy、Alembic、LangChain 和 Pillow。PostgreSQL 用于持久化，Redis 用于任务队列，MinIO 提供对象存储。影像流程可接入 FFmpeg、ClamAV 和 ComfyUI。工程依赖版本以 `web/package-lock.json` 和 `api/requirements-dev.lock` 为准。

高德地图与 DeepSeek 是独立服务，使用各自的服务凭证与条款。GC Minimal Zine Poster 的提示词改编和配图署名见 [第三方组件与素材说明](docx/THIRD_PARTY_NOTICES.md)。

## 码道在项目开发中的应用

团队在 VS Code 中安装华为码道插件。提交的《码道使用情况.docx》按环境搭建、代码检查、服务器购买与设计方案四类场景保留了使用截图。同一份附件作为过程材料提交。各场景的用途见 [码道应用总结](docx/码道应用总结.md)。

## 后续完善规划

1. **规划效果**。引入更多真实城市样本，比较不同分区与重排策略的总时长、交通时间与必去完成率，补齐多日跨区修复。
2. **出行数据**。接入有授权的天气、城际班次与票务信息，覆盖如何到达、如何返程、营业及预约时效。逐步补齐午餐、晚餐和预算建议。
3. **小曦和知识库**。扩充带来源和更新时间的城市指南，支持用户分享攻略及语音交流，并完善对话授权和记忆管理。
4. **影像与移动端**。完善 Vlog 队列恢复、弱网上传、ComfyUI 模板和小曦同框素材，开展 iOS Safari 与 Android Chrome 真机验收。
5. **公开运行能力**。建设多人账户、会话撤销、服务配额、运行监控和备份恢复。当前 Demo 使用单人私有访问令牌。

## 验证与排查

接口测试和静态检查在 `api/` 启动，网页测试在 `web/` 启动。命令与故障处理见 [运行手册](docx/RUNBOOK.md) 和 [错误排查目录](docx/06-error-catalog.md)。
