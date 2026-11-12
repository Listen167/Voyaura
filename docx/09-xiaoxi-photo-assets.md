# 小曦合照素材接入

## 当前状态

Voyaura 已实现确定性透明素材合成器，但项目中没有正式小曦角色图片。未取得明确授权
前，不使用 Emo_Agent、网络图片或临时占位形象冒充小曦。

## 素材要求

- PNG、RGBA，背景必须存在真实透明区域。
- 建议完整角色高度至少 1024 像素，角色边缘保留少量透明安全区。
- 素材不包含水印、说明文字或背景阴影；worker 会按场景自行添加柔和阴影。
- 每次素材更新都提供稳定版本号，例如 `xiaoxi-v1`。
- 保留创作者、版权归属和允许在 Voyaura 中使用、修改、分发的授权记录。

## 配置

素材可以放在项目外的私有目录，避免在未确认分发授权时提交到 Git：

```dotenv
VOYAURA_XIAOXI_PHOTO_ASSET_PATH=D:\VoyauraPrivateAssets\xiaoxi-v1.png
VOYAURA_XIAOXI_PHOTO_ASSET_VERSION=xiaoxi-v1
```

修改 `api/.env` 后重启 FastAPI 和 `.\worker\run-image.ps1`。检查能力：

```powershell
Invoke-RestMethod http://127.0.0.1:8001/api/v1/image-styles |
  Select-Object -ExpandProperty companion
```

`available=true` 后，照片风格弹层会开放“和小曦一起入镜”，支持左右站位和
小/中/大尺寸。

## 数据与隐私

浏览器和 API 响应不会暴露本机素材路径，只返回素材版本和支持的选项。合照结果与
其他生成图一样保存在私有 MinIO 对象中，收藏、下载和删除沿用图片任务接口。界面会
显示“小曦角色使用经授权透明素材进行确定性合成”，不把它描述为真实同行者照片。
