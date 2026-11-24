# 本次交付验证

产品界面基线289fd4d，整合基线Listen167/main 567dfde；以下为交付工作目录实际重跑结果，不把上一版成绩当成本次结果。

| 检查 | 实际结果 |
|---|---|
| 前端组件 | 21文件、86项通过 |
| 后端 | 116项通过，含两种已有迁移head升级、历史数据与新增路由鉴权 |
| 浏览器 | 桌面/手机22项通过，独立HTTP/SQLite/Chrome，约1.5分钟 |
| 类型/构建 | vue-tsc、Vite生产构建、PWA生成通过 |
| 设计 | 七页五屏宽、200%文字、44px交互区、焦点与实色取样对比通过 |
| Python静态检查 | ruff通过 |
| 依赖 | 哈希锁安装和uv pip check通过；npm生产审计0已知漏洞 |

新增认证测试覆盖trips和需求分析路由，无凭证拒绝、跨用户username拒绝。需求分析Provider单元测试明确使用actor和模型替身；真实bearer边界另用无覆盖测试。两条0014迁移经0015合为单head，空库与两种分支继续升级均通过。

主分支旧聊天壳未挂载、模板合并缺段、模块API未带bearer、依赖锁缺项等先失败后修复；说明见[HANDOFF](../HANDOFF.md)。恢复维护者完整路线/需求工作台，保留289fd4d界面和真实确认流程。上游旧聊天组件断言已由实际工作台用例覆盖，未伪造不存在的聊天界面。

本次原始JUnit位于忽略的.local/verification，浏览器JUnit与截图在.local/e2e-evidence；可通过[运行手册](../../docx/RUNBOOK.md)复现。CI会上传浏览器artifact，不能在远程完成前声称GitHub检查已通过。当前8张展示图来自原289fd4d空档案并做WebP压缩，保留其来源说明。

未在本轮验证在线地图/模型/影像Provider、PostgreSQL/Redis/MinIO完整媒体组合、原生移动端、读屏或完整WCAG；测试替身与隔离库不证明这些环节完成。未使用、删除或导出个人DB/媒体。

远程首次CI：Web与PostgreSQL迁移通过；API的4项中文印章测试因Ubuntu缺少CJK字体失败，其余112项通过。CI的API任务已补充安装fonts-noto-cjk，保留原测试，不跳过、不降低断言；最终结果以PR最新检查为准。
