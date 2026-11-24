# 289fd4d界面交付与上游整合

产品视觉固定为289fd4d97bbbaecae25c196d9a1e9b107581a439。上次PR #1已合并，本次从Listen167/main 567dfde建立codex/delivery-editorial-289fd4d，通过fork和新草稿PR交付，不覆盖维护者后续开发。

四图构图、档案与受控工作台沿用289fd4d。保留主分支新增正式行程模型、需求分析API、API模块和优化器整理脚本。交付提交与产品基线SHA不同，因为包含必要整合与目录整理。

## 复现修复

- JourneyPlannerView在上游合并中模板缺段：从维护者74a2547恢复完整版本，保留需求草案和路线工具。
- App中旧聊天代码引用未定义且未挂载的状态：清除不可执行片段，沿用289fd4d实际页面与导航。需求分析继续由真实存在的工作台测试覆盖，移除失效旧聊天组件断言。
- 两个0014迁移head：追加无数据操作的0015合并revision，不改历史迁移。
- langchain依赖声明未入锁：保留原约束补齐哈希锁，在独立venv安装验证。
- trips/xiaoxi路由仅导入未注册：在owner认证边界挂载，并复核正式行程username。
- 拆分API请求丢失bearer且回退另一端口：共享原client同源请求与错误类，模块默认用户取当前owner。
- Vitest5在Windows错误转换public图URL：仅测试编译关闭静态资源导入转换，生产行为不变。

这些为交付复现修复，不是新一轮界面设计。后端Provider双、空档案截图与在线结果分别记录。

## 精简与保留

289fd4d原有969个文件、约92MB，主要是多轮截图、参考图和重复报告。本次交付树移除历史大图册、旧JUnit与重复Word/PDF/PPT，保留原本地文件和既有Git历史。只带8张最新WebP、源码、测试、依赖锁、配置和必要Markdown，以及维护者已有原始资料。

令牌、真实DB/媒体、环境、node_modules、venv、dist、日志和自动报告不提交。全量自动证据在.local或CI artifact，摘要见[测试报告](delivery/TEST_REPORT.md)。

原289fd4d工作目录与5278预览不变。未合并主分支、公开部署、购买服务或上传参赛作品。在线模型/地图/影像与生产媒体栈仍需独立联调；视觉保留项见[差异说明](design/current/DIFFERENCES.md)。
