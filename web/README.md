# Voyaura Web

Vue3/TypeScript/Vite PWA，视觉基线289fd4d。启动见[根README](../README.md)和[运行手册](../docx/RUNBOOK.md)。

~~~powershell
npm ci
npm run test
npm run build
~~~

默认API为同源/api/v1，开发代理默认8018，可用VOYAURA_DEV_API_URL调整。推荐使用根启动脚本匹配profile。API模块共享认证请求和当前owner；令牌不进入URL。

地图Key只在本地.env.local配置。正常开发/生产不提供演练入口。浏览器测试必须从根scripts/verify_e2e.py启动，输出.local/e2e-evidence，不向个人库填夹具。Node24 LTS为团队与CI推荐。
