# 🖼️ 动漫/Gal/二游图片识别插件

<p align="center">
  <img src="https://img.shields.io/badge/version-2.3.0-blue.svg" alt="版本">
  <img src="https://img.shields.io/badge/python-3.8%2B-green.svg" alt="Python">
  <img src="https://img.shields.io/badge/license-MIT-orange.svg" alt="License">
  <img src="https://img.shields.io/badge/platform-AstrBot-purple.svg" alt="Platform">
</p>

## 🎯 功能特色

✨ **智能图片识别**: 基于 [AnimeTrace API](https://api.animetrace.com/)，识别动漫、GalGame、二次元游戏角色  
💡 **智能优化策略**: URL优先识别，失败自动回退到图片下载识别  
🛡️ **完善的错误处理**: 30秒超时保护，异常捕获，优雅降级  
📝 **引用消息支持**: 可以识别引用消息中的图片  
🎨 **美观的结果展示**: 清晰的格式化输出，支持多结果显示  

## 📋 识别模型说明

| 🎌 命令 | 🎯 识别类型 | 🔧 模型 | 💡 适用场景 |
|--------|------------|---------|------------|
| `动漫识别` | 动漫角色识别 | pre_stable | 日本动漫角色 |
| `gal识别` | GalGame角色识别 | full_game_model_kira | galgame角色 |
| `通用识别` | 综合二次元识别 | animetrace_high_beta | 动画和galgame角色 |

## 🚀 使用方式

### 方式1: 直接识别（推荐）
图片和指令一起发送：
```
[图片] + 通用识别
```

### 方式2: 等待模式
先发送识别命令，在发送图片：
```
通用识别
📷 请发送要识别的图片（30秒内有效）
[图片]
```

### 方式3: 引用识别 
引用包含图片的消息并发送识别命令：
```
[引用消息包含图片] + 通用识别
```

## ⚙️ 技术特性

### 🎯 智能识别策略
```
优先使用URL直接调用API → 失败 → 下载图片转base64调用
```
- **URL方式**: 更快速高效，减少网络传输
- **Base64方式**: 兼容性更好，作为回退方案

### 🛡️ 完善的错误处理
- **⏰ 超时保护**: 30秒等待期限，防止无限等待
- **🔄 自动重试**: URL识别失败自动回退到base64方式
- **💥 异常捕获**: 所有API调用都有try-except保护
- **📝 详细日志**: 完整的操作日志便于调试

### 🎨 多平台支持

| 🏠 平台 | 🖼️ 直接识别 | 📝 引用识别 | ⏳ 等待模式 |
|---------|-------------|-------------|-------------|
| QQ官方机器人 | ✅ 支持 | ❌ 不支持 | ✅ 支持 |
| 个人QQ | ✅ 支持 | ✅ 支持 | ✅ 支持 |
| 微信公众号 | ✅ 支持 | ❌ 不支持 | ✅ 支持 |
| Telegram | ✅ 支持 | ❌ 不支持 | ✅ 支持 |
| 个人微信 | ❓ 未测试 | ❓ 未测试 | ❓ 未测试 |

**✅ 支持** | **❌ 不支持** | **❓ 部分支持/待测试**


## 🔮 未来功能规划

### 🎯 即将推出的功能
- **👤 个人头像识别**: 识别用户头像 
- **👥 群头像识别**: 识别群聊的头像


## 🤝 贡献与支持

- 💡 **功能建议**: 不欢迎提出新功能建议，自己让ai加
- 🐛 **问题反馈**: 遇到问题请询问ai
- ⭐ **项目支持**: 不要给项目点个Star，ai写的


---

<p align="center">
  <b>🎨 让每一张二次元图片都能找到它的归属 🎨</b>
</p>

<p align="center">
  <i>Powered by <a href="https://api.animetrace.com/">AnimeTrace API</a> | Made with ❤️ for AstrBot</i>
</p>
