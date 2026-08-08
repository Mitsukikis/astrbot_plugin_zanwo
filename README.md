</div>

<div align="center">



# astrbot_plugin_zanwo

_✨ [astrbot](https://github.com/AstrBotDevs/AstrBot) 赞我插件 ✨_

[![Python 3.8+](https://img.shields.io/badge/Python-3.8%2B-blue.svg)](https://www.python.org/)
[![GitHub](https://img.shields.io/badge/作者-Futureppo-blue)](https://github.com/Futureppo)
[![GitHub](https://img.shields.io/badge/作者-Zhalslar-blue)](https://github.com/Zhalslar)

</div>

## 📦 插件简介

【仅QQ】QQ名片赞，同时用户可以订阅点赞，订阅后bot每天自动为用户点赞。可在 控制面板>插件配置 开启白名单群聊, 开启后只有在白名单群聊中才能使用插件。

## 🛠️ 本维护版改进

- 每天北京时间 00:00，由每个在线 OneBot QQ 机器人分别为全部订阅用户点赞。
- AstrBot 在零点离线或重启时，当天会自动补跑；平台暂时不可用时每 5 分钟重试。
- 按 QQ 机器人分别保存每日执行状态，避免多机器人漏跑或同一天重复执行。
- 修复原版只有收到“赞我”消息后才顺带检查订阅、失败前提前写入完成日期的问题。

## ⌨️ 命令

|     命令      |      说明        |
|:-------------:|:------------------------------------:|
|     赞我       | 给用户点赞（可不带前缀）  |
|     赞@XXX       | 给用户点赞，可以同时@多个人  |
| /订阅点赞      | 订阅后bot每天自动为用户点赞    |
| /取消订阅点赞   | 取消订阅后bot每天不再自动为用户点赞 |
| /订阅点赞列表   | 查看当前订阅点赞的用户ID列表 |
| /谁赞了bot      | 查看谁赞了bot |

## 📌 注意事项

- 点赞限制：非好友每天只能点50人，每人50个赞

## ❓ 常见问题

### Q: 为什么点赞失败？

- 可能是因为用对方隐私设置未开启陌生人点赞权限，
- 或者已达到QQ点赞次数限制
- 或者是你没加bot好友，而bot今日给陌生人点赞量也已到达上限

---

## 🐔 联系作者

- **反馈**：欢迎在 [GitHub Issues](https://github.com/Futureppo/astrbot_plugin_zanwo/issues) 提交问题或建议

---

## 🌟 支持

- Star 这个项目！

## 📜 开源协议

本项目采用 [MIT License](LICENSE)
