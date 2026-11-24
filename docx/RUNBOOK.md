# 运行、部署与验证

## 本地启动

推荐Python3.12、Node24 LTS、Chrome。首次安装和启动命令见[根README](../README.md)。默认Web5188/API8018；初始化参数--api-port、--web-port可调整，已有profile不覆盖。Linux使用api/.venv/bin/python代替Windows路径。

profile、随机访问令牌和空SQLite在.local。seed只初始化用户和城市字典。API从当前目录.env或进程环境读取，根.env供Compose使用。不要提交令牌、云Key或复制个人库做验收。

## 验证

api目录：

~~~powershell
.venv/Scripts/python.exe -m pytest -q
.venv/Scripts/python.exe -m ruff check app tests
~~~

web目录：

~~~powershell
npm run test
npm run build
npm audit --omit=dev
~~~

根目录：

~~~powershell
api/.venv/Scripts/python.exe scripts/verify_e2e.py
~~~

没有Chrome时在web运行npx playwright install chromium，根目录设置VOYAURA_E2E_CHANNEL=chromium后运行。使用全新独立库、随机端口与令牌，只停止自身服务。输出.local/e2e-evidence，CI保留artifact，不进入Git。

正常产品不显示演练；只有独立开发测试显式启用夹具。图片、模型与地图替身不代表在线结果。

## 迁移与配置

0014_agent_workflows和0014_itinerary_contracts来自不同分支，0015_merge_agent_itinerary把二者合为一个head。空库、两种已有head升级和历史数据保留均由测试覆盖。私人或生产库先备份并在副本验证，本次未操作。

原受控Agent关键词模型使用VOYAURA_AGENT_LLM_*；主分支结构化需求分析使用VOYAURA_DEEPSEEK_API_KEY，两者职责不同。高德、扫描器、MinIO、FFmpeg、Redis和ComfyUI分别配置，见[接入文档](02-data-integrations.md)、[影像说明](07-comfyui-integration.md)和[DeepSeek清单](12-deepseek-planning-checklist.md)。

## 生产边界

npm run build输出web/dist。反向代理把/api/v1转发Uvicorn，其他页面使用SPA回退。TLS、秘密管理、备份、角色/会话、限流、多人账户和媒体可靠性需独立验收。本机没有Docker，本轮未公开部署。

单机owner令牌不是多租户登录。保存计划不自动点亮城市；故事只读取授权窗口已有记录，删除来源不自动删除已确认快照。在线Provider和生产并发需另行验证。

Linux运行中文旅行印章需安装CJK字体，例如Ubuntu的fonts-noto-cjk；也可用VOYAURA_IMAGE_CAPTION_FONT_PATH指定已授权本地字体。CI已显式安装字体，字体缺失时原服务仍明确失败，不伪造中文渲染成功。
