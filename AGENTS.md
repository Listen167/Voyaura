# Voyaura 工程规则

- 交付视觉基线289fd4d，整合基线Listen167/main 567dfde。用户已授权通过fork/PR上传；不得自行合并主分支、公开部署或上传比赛。原工作目录与私人数据不修改。
- 保留Vue3/FastAPI/SQLAlchemy/Alembic/PostgreSQL/Redis/MinIO。SQLite用于本地与隔离测试。0015合并两条0014迁移，不重写历史迁移，不直接操作私人库。
- 默认外部服务关闭；模型文本、装饰、测试夹具与在线事实分开。未知保持未知，不补造旅行、作品、Provider或CodeArts成功。
- 私人API通过get_actor，username复核actor。API拆分模块共享认证请求；令牌只在本地忽略文件和浏览器会话，不写URL。
- 保存绑定用户、版本、内容摘要与期限。权限、费用、删除、公开发布保留必要确认。测试替身不代替真实认证边界验证。
- 品牌令牌在web/src/styles/design-tokens.css；复用UiButton/UiStatus。正文输入16px、辅助14px、标签≥12px、触控44px，保留键盘焦点和状态文字。
- 当前截图仅放docs/design/current。生成JUnit、长图、历史对照、依赖、缓存、DB、密钥和重复Office导出不进Git。目录规则见docs/REPOSITORY_GUIDE.md。
- api运行pytest与ruff，web运行npm ci/test/build/audit；根目录通过api/.venv/Scripts/python.exe scripts/verify_e2e.py运行隔离浏览器流程。输出.local/e2e-evidence，CI上传artifact。
- 只停止自己启动的子进程，不覆盖维护者并行修改。记录已测事实与未验证范围。运行手册docx/RUNBOOK.md，测试摘要docs/delivery/TEST_REPORT.md。
