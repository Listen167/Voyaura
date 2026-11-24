# 目录与内容

~~~text
Voyaura/
├─ README.md / AGENTS.md          项目入口与工程规则
├─ .env.example                  Compose示例，不含真实凭证
├─ .github/workflows/ci.yml       API/Web/浏览器/Postgres迁移检查
├─ api/
│  ├─ app/agent/                 受控任务、工具、规划、验证与确认
│  ├─ app/integrations/          地图、模型、存储和队列
│  ├─ app/routers/               API、正式行程与需求分析
│  ├─ app/auth.py                owner身份边界
│  ├─ alembic/versions/          历史迁移与0015双分支合并
│  ├─ tests/                     API、鉴权、迁移与Provider替身
│  └─ pyproject.toml / *.lock    依赖声明及哈希锁
├─ web/
│  ├─ src/views/                 发现、规划、故事、地图、记忆、创作、档案
│  ├─ src/components/            导航、地图、媒体和共享UI
│  ├─ src/api/                   API模块、统一认证请求与会话
│  ├─ src/styles/                品牌令牌与职责样式
│  ├─ public/discover/           开放许可摄影与credits
│  ├─ public/art/                本地手帐、护照、等高线与邮戳
│  ├─ e2e/                      隔离浏览器流程
│  └─ package-lock.json          前端锁
├─ scripts/                      初始化、启动、隔离验收和只读截图
├─ worker/ / infra/              媒体/影像后台与本地服务组合
├─ docx/                         产品、接入、DB、正式行程和运行文档
└─ docs/
   ├─ HANDOFF.md                 本次范围与上游整合修复
   ├─ agent_contract.md          受控Agent契约
   ├─ design/current/            8张最终截图与视觉差异说明
   └─ delivery/                  架构、测试摘要和参赛Markdown初稿
~~~

只提交源代码、测试、迁移、配置示例、依赖锁、许可、当前截图与必要说明。docx中的维护者原始材料保留，该目录并非只放Word。

不提交.env、令牌、私人DB/媒体、.local、node_modules、.venv、dist、日志、历史图册与重复Office导出。全量历史保留在原本地工作目录。

测试在.local/e2e-随机编号建库，在.local/e2e-evidence生成报告和截图；CI以artifact提供，不反复写入版本树。

本分支继承最新main历史，不重写维护者历史；不推送本地包含多轮大图册的开发分支历史。交付包和新提交只包含最终净改动。
