# 路线与跨城交通 Provider 方案

## 推荐组合

| 场景 | 推荐 Provider | 当前状态 | 需要用户提供 |
|---|---|---|---|
| 步行、公交地铁、驾车、车站机场接驳 | 高德 Web 服务 | 接口已实现，真实查询受 `10007` 签名配置阻塞 | 修正现有高德 Web Key 的数字签名配置 |
| 高铁、动车、普通火车 | 携程/同程等正式合作接口 | 能力契约已预留，尚未授权 | 合作方账号、接口文档和测试凭证 |
| 航班开发验证 | Amadeus Flight Offers Search | 能力契约已预留，尚未接入 | Amadeus 测试应用 Client ID/Secret |
| 国内生产航班与售票 | 携程、航司或中航信类授权方 | 上线前评估 | 商务合同、生产凭证、覆盖与结算规则 |

## 铁路边界

12306 没有提供适合本项目直接使用的稳定公开售票 API。网页或 App 内部接口可能变化，并涉及服务条款、验证码、实名乘车人和支付安全。Voyaura 不抓取这些未公开接口，也不保存 12306 密码或乘车人证件。

铁路 Provider 必须返回车次、出发/到达站、日期时间、席别、价格、余票状态、数据来源和查询时间。没有授权 Provider 时，小曦只能给出换乘结构和建议查询入口，不能虚构车次、票价或余票。

## 航班边界

Amadeus Self-Service 使用标准 OAuth2，并提供 Flight Offers Search，适合开发阶段验证航班搜索、舱位和价格结构。正式面向中国用户上线前，需要评估国内航司、代码共享、行李额、退改规则和支付覆盖；覆盖不足时切换到国内授权合作方。

密钥只放在 API 环境，不能进入网页或 Skill。真正实现 Amadeus Provider 时再加入以下配置，当前不加入无效环境变量：

```text
VOYAURA_FLIGHT_PROVIDER=amadeus
VOYAURA_AMADEUS_CLIENT_ID=...
VOYAURA_AMADEUS_CLIENT_SECRET=...
VOYAURA_AMADEUS_ENVIRONMENT=test
```

## 当前接口

```text
GET  /api/v1/tools/routes/capabilities
POST /api/v1/tools/routes/plan
```

`capabilities` 返回市内和跨城 Provider 的状态、数据范围、申请入口和限制。`plan` 当前支持 `walking`、`transit` 和 `driving`，坐标使用 GCJ-02，返回高德来源与查询时间。

完整跨城行程最终组合为：

```text
出发地 → 高德接驳 → 车站/机场 → 铁路/航班 Provider → 到达站/机场 → 高德接驳 → 目的地
```

Voyaura 只负责搜索与组合。购买、实名信息提交和支付必须跳转授权平台，并由用户最终确认。

