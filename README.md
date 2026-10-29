# hanserLIVE 动态邮件提醒

定时监控 [2550505.com 上 hanserLIVE（UID=1）的动态](https://2550505.com/space/1)。
每半小时检查一次，新动态邮件包含标题、发布时间、完整文字正文、正文图片链接和原帖链接。
基于 Python 标准库与 GitHub Actions，不调用大模型，不需要 X API，也无需安装第三方 Python 包。

## 配置邮件

打开仓库 **Settings → Secrets and variables → Actions → New repository secret**，添加三个 Secrets：

| 名称 | 内容 |
| --- | --- |
| `SMTP_USERNAME` | 完整 QQ 发信邮箱地址 |
| `SMTP_PASSWORD` | QQ 邮箱 SMTP 授权码（不是 QQ 登录密码） |
| `MAIL_TO` | 收件邮箱地址 |

QQ 邮箱网页版 → 设置 → 账户 → 开启 IMAP/SMTP 服务 → 生成授权码。工作流默认使用 `smtp.qq.com:465`，TLS 证书验证保持开启。
邮箱地址和授权码只放入 Secrets；本仓库及状态文件不存储这些信息。

## 运行与验证

Actions → **hanserLIVE 动态监控** → **Run workflow**：

- `check`：实际读取网站动态列表与最新帖子正文，不发邮件、不更改状态。
- `test-email`：仅发送测试邮件。SMTP 接受不等于邮件进入收件箱，请检查收件箱或垃圾邮件。
- `monitor`：按状态检查新动态，有新增才发信。

定时任务在每小时第 9、39 分钟运行 monitor；GitHub 可能延迟或跳过任务，不能保证实时或严格每半小时执行。
缺少 Secrets 时会明确失败，补齐后手动执行 test-email 与 monitor。

部署时的 `state.json` 是基线，其中的帖子视为已知，不重复通知。
若没有状态文件，第一次成功运行仅建立基线，不补发旧消息。
只在成功读取、必要的邮件被 SMTP 接受之后保存状态；失败不会当作没有新动态。
检查作者 UID 和昵称，按帖子 ID 去重；点赞、评论、阅读数变化、旧动态编辑和删除不会触发通知。
读取正文区域及 pictures 字段的图片，不抓取头像和评论表情。图片以链接提供，不下载附件。

邮件发送与 Git 提交无法原子完成：发信后进程中断或推送失败可能导致下次重复发送，请查看 Actions 失败通知。
不要删除或手改 state.json；这会影响去重和时间基线。请在 GitHub 通知设置中启用 Actions 失败提醒。

## 成本与维护

当前使用网站自身公开页面的数据接口，无需登录、API Key 或付费 API。接口并非稳定性承诺，站点改版后可能需要维护。
若遇到登录、验证码或访问限制，任务会失败，不尝试绕过。
公开仓库使用 GitHub 标准运行器通常免费；私有仓库会消耗账户的 Actions 额度。不要将授权码提交到代码。
公开仓库长期无活动可能被 GitHub 停用定时任务，应定期检查 Actions。

本项目不会自动停用原有 GPT Task；确认新任务已读取成功、测试邮件已实际收到后，再停用旧任务。

## 本地运行

Python 3.12 或更新版本：

```sh
python -m unittest discover -s tests -v
python monitor.py --mode check
python monitor.py --mode initialize
python monitor.py --mode monitor
```

monitor/test-email 模式从环境变量读取上述三项邮件配置。check/initialize 不需要发信配置。
