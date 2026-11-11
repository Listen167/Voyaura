# 系统架构

## 仓库边界

```text
voyaura/                    主应用
├── web/                    Vue 3 + Vite + TypeScript PWA
├── api/                    FastAPI + SQLAlchemy + Alembic
├── worker/                 媒体与 AI 异步任务
├── infra/                  PostgreSQL、Redis、MinIO
└── docx/                   产品与工程文档

voyaura-skill/              独立 AI Skill
├── SKILL.md                任务路由与行为边界
├── scripts/                确定性 API 调用
└── references/             API 契约和工具目录
```

## 运行链路

```text
用户
  ├── Web / PWA ───────────────┐
  └── 小曦聊天 → Voyaura Skill ├→ FastAPI
                               │    ├→ PostgreSQL 18 / PostGIS 18（按需升级）
                               │    ├→ Redis 任务队列
                               │    ├→ MinIO 媒体存储
                               │    ├→ 高德地图与天气
                               │    └→ Worker → 图片模型 / ComfyUI
                               └──────────────────────────────
```

## 技术决策

- 前端采用 Vue 3，便于延续 `Emo_Agent` 的小曦资产与视觉语言。
- 桌面与手机共用响应式 PWA；需要后台轨迹时再用 Capacitor 封装。
- PostgreSQL 18 是当前业务主数据库；首版经纬度以数值字段存储。首次实现地理围栏或轨迹空间查询前，在同一 PostgreSQL 18 主版本上启用 PostGIS，避免跨主版本数据卷迁移。
- Redis 承载图片、视频和内容生成任务，不在 HTTP 请求中等待长任务。
- MinIO 提供本地 S3 兼容媒体存储，生产环境可以替换为云对象存储。
- Skill 不持有地图或图片模型密钥，只调用 Voyaura 的版本化 API。
- 当前所有业务均为链下数据，不引入区块链和智能合约。

## 图片 Provider 边界

```text
ImageProvider
├── CloudImageProvider       快速验证图像编辑体验
└── ComfyUIProvider          本地化、可控工作流与角色一致性
```

风格 Skill 只负责参考图角色、Prompt、Recipe 和质量门槛，不等同于图片模型。

