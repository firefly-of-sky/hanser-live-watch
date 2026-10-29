# hanserLIVE 动态邮件提醒

[![离线测试](https://github.com/firefly-of-sky/hanser-live-watch/actions/workflows/test.yml/badge.svg)](https://github.com/firefly-of-sky/hanser-live-watch/actions/workflows/test.yml)

关注 [2550505.com 上 hanserLIVE（UID=1）的动态](https://2550505.com/space/1)，有新动态时自动发邮件。默认每半小时检查一次，无新动态时不发邮件。

只需一个 GitHub 账号、一个支持 SMTP 的发信邮箱和一个收件邮箱。不需要服务器、电脑常开、网站登录账号或大模型 API。

## 可以收到什么

- 动态标题、完整文字正文、北京时间和原帖链接。
- 正文图片的链接；不下载附件，不包含头像或评论表情。
- 一轮发现多条新动态时，合并为一封邮件。

脚本核实作者身份，并按帖子 ID 保存去重记录。点赞、回复数、阅读数变化及旧帖编辑、删除不会触发提醒。第一次运行仅建立基线，不补发历史动态。

## 快速部署：Fork 后即可配置

下面以 **QQ 邮箱发信**为例，收件邮箱可以是 QQ、iCloud、Gmail 等，也可以与发信邮箱相同。全部操作都能在 GitHub 网页完成。

### 1. Fork 到自己的账号

点击本仓库右上角 **Fork → Create fork**。

后续所有设置和运行操作都在 **你自己的 Fork** 中完成。Secrets 不会从原仓库复制过来，每位使用者需要自行配置。

当前工作流使用公开仓库的标准 Ubuntu 运行器，运行计算免费且不扣减账户的免费计算额度。若自行复制到私有仓库，计算用量会计入账户额度；以 [GitHub 官方计费说明](https://docs.github.com/en/billing/concepts/product-billing/github-actions)为准。

### 2. 首次部署，重建自己的去重基线

Fork 会复制原仓库的 `state.json`，其中保存了原部署的已知帖子和监控起始时间。

**仅首次部署时，在你自己的 Fork 中删除根目录的 `state.json`，并提交到默认分支。** 可在文件页面右上角的菜单中选择删除文件，然后提交更改。如果文件本来就不存在，跳过此步。

之后首次运行 `monitor` 会自动生成自己的状态文件，把当时已有的动态视为旧动态，从此开始监控。

**已经正常运行的部署不要删除状态文件。** 删除会重新建立基线，尚未通知的现有动态也会被当作旧动态跳过。不要向原仓库提交你自己的状态文件更改。

### 3. 开启 QQ 邮箱 SMTP 并添加 Secrets

先在 [QQ 邮箱网页版](https://mail.qq.com/)进入 **设置 → 账户**，找到 **IMAP/SMTP 服务**或 **POP3/SMTP 服务**，按提示开启并生成授权码。

授权码用于脚本发信，**不是 QQ 登录密码**。

在你自己的 GitHub 仓库进入：

**Settings → Secrets and variables → Actions → Secrets → New repository secret**

分别添加以下三个 **Repository secrets**：

| Name（名称，必须完全一致） | Secret（值） | 示例 |
| --- | --- | --- |
| `SMTP_USERNAME` | 完整的 QQ 发信邮箱地址 | `123456789@qq.com` |
| `SMTP_PASSWORD` | QQ 邮箱生成的 SMTP 授权码 | 填你自己的授权码 |
| `MAIL_TO` | 接收提醒的邮箱地址 | `yourname@icloud.com` |

示例地址需要替换为自己的邮箱。不要把这些配置加到 **Variables** 或 **Environment secrets**，当前工作流从 Repository secrets 读取。

邮箱地址和授权码仅保存到 Secrets，不要写入代码、README、Issue 或提交记录。

### 4. 启用 Actions 和监控工作流

进入你自己的仓库的 **Actions** 页面。如果出现启用 Fork 工作流的提示，按页面提示启用。

在左侧选择 **hanserLIVE 动态监控**。若显示工作流已停用，点击 **Enable workflow**。

> GitHub 默认停用公开 Fork 的定时工作流。仅 Fork 仓库、仅配置 Secrets 都不足以让定时任务开始运行。[官方说明](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/disable-and-enable-workflows)

工作流已经声明 `contents: write`，用于提交去重状态。如果保存状态时出现权限错误，检查 **Settings → Actions → General** 中的工作流权限、组织策略及默认分支保护规则，确保工作流可以提交 `state.json`。

### 5. 按顺序做三次验证

仍在 **Actions → hanserLIVE 动态监控** 中，点击 **Run workflow**，分支选择默认分支（通常为 `main`），分别选择以下 `mode` 运行：

| 顺序 | mode | 作用与成功标志 |
| --- | --- | --- |
| ① | `check` | 读取真实动态列表及最新帖子正文，不发邮件、不改状态。日志显示作者、最新帖子 ID 等信息。 |
| ② | `test-email` | 发送主题为“hanserLIVE 监控测试邮件”的测试邮件。请实际检查收件箱和垃圾邮件。 |
| ③ | `monitor` | 首次没有状态文件时建立基线，日志显示 `Baseline saved`，并自动提交新的 `state.json`。已有基线时正常检查新动态。 |

每次运行完成后，点击该次记录查看结果。三步通过后，即可等待后续定时检查，不需要保持浏览器或电脑在线。

测试邮件日志中的 `SMTP accepted` 只表示发信服务器接受邮件；**是否实际收到，要以收件箱为准**。

## 检查频率与修改方法

默认配置位于 [.github/workflows/watch.yml](.github/workflows/watch.yml)：

```yaml
schedule:
  - cron: '9,39 * * * *'
```

即每小时第 9、39 分钟检查一次。可按需替换为：

| 频率 | cron |
| --- | --- |
| 每半小时，默认 | `9,39 * * * *` |
| 每小时 | `9 * * * *` |
| 每两小时 | `9 */2 * * *` |

cron 使用 UTC 时区；上表的检查间隔不受时区影响。修改后提交到自己的默认分支即可。

GitHub 定时任务可能延迟或跳过运行，不能保证严格按时送达。定时任务运行默认分支上的工作流，文件需要保留在该分支。[定时触发说明](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule)

## 使用其他发信邮箱

收件邮箱直接修改 `MAIL_TO` 即可。

如果发信邮箱不是 QQ，需要同时修改：

1. Secrets 中的 `SMTP_USERNAME` 与 `SMTP_PASSWORD`，使用对应服务商的账号及 SMTP 授权码／应用专用密码。
2. [.github/workflows/watch.yml](.github/workflows/watch.yml) 中的 `SMTP_HOST` 和 `SMTP_PORT`。它们当前是工作流中的固定值，**仅添加同名 Secret 或 Variable 不会覆盖**。

当前默认值：

```yaml
SMTP_HOST: smtp.qq.com
SMTP_PORT: '465'
```

脚本使用 465 端口时走 TLS 连接，其他端口走 STARTTLS；按邮箱服务商提供的支持配置填写，并保持证书验证。改好后重新运行 `test-email`。

## 去重、失败重试与维护

- `state.json` 保存监控起始时间、已见 ID、已通知 ID 和最后成功检查时间，不包含邮箱地址或授权码。
- 正常运行会自动提交状态文件，提交消息为 `Save monitor state [skip ci]`，无需手动维护。
- 网站读取失败、首页空列表或需要发信时发送失败，都不会推进状态，后续运行会重试。
- 发信成功和 Git 提交无法原子完成；如果邮件已被接受但状态提交失败，下次可能重复提醒。请检查 Actions 中的失败记录。
- 更新 Fork 时，保留自己的 `state.json`。同步上游若涉及此文件，应保留自身状态，避免被上游状态覆盖。
- 暂停提醒：进入 **Actions → hanserLIVE 动态监控 → 右上角菜单 → Disable workflow**；恢复时选择 **Enable workflow**。
- GitHub 对长期无仓库活动的公开仓库可能自动停用定时任务，定期查看 Actions 是否仍在运行。[启停说明](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/disable-and-enable-workflows)

网站数据来自公开页面使用的接口，不调用 GPT 或其他模型，无需付费数据 API。该接口没有长期稳定性保证，站点改版可能需要维护；遇到登录、验证码或访问限制时应停止并检查，不绕过限制。请保持合理频率。

## 常见问题

| 情况 | 检查方法 |
| --- | --- |
| `Missing GitHub Secrets: SMTP_PASSWORD` 等错误 | 检查三个 Secret 的拼写和大小写；确认放在自己 Fork 的 Repository secrets 中，值非空。 |
| `SMTPAuthenticationError` | 检查发信邮箱和授权码。使用 SMTP 授权码，不是邮箱登录密码；确认 SMTP 服务已开启。 |
| `SMTP accepted` 但没收到邮件 | 检查垃圾邮件、`MAIL_TO` 地址及邮箱服务商的投递状态。 |
| 网站超时、JSON 或作者校验错误 | 查看站点是否可访问，稍后手动运行 `check`；持续失败可能需要适配网站接口。 |
| `git push` 或保存状态失败 | 检查 Actions 写权限、分支保护、是否有人同时修改默认分支。状态未保存可能导致重复邮件。 |
| 工作流成功却没有邮件 | 首次建立基线和没有新动态时均不发邮件。先用 `test-email` 单独验证发信。 |
| Fork 后没有自动运行 | 确认 Actions 与该定时工作流均已启用；查看默认分支及最近的运行记录。 |
| 看不到 `Run workflow` | 确认位于自己的仓库、工作流已启用，并且默认分支包含 `watch.yml`。 |

可在 GitHub 个人通知设置中启用 Actions 失败通知，避免监控中断而不知情。报告问题时提供运行链接或去除敏感信息的报错，不要附授权码。

## 本地运行与开发

Python 3.12 或更新版本，无需额外 Python 依赖。在 Linux、macOS 或带有 IANA 时区数据库的环境中运行：

```sh
git clone https://github.com/你的用户名/hanser-live-watch.git
cd hanser-live-watch

# 离线测试：不访问网站，不发邮件
python -m unittest discover -s tests -v

# 实际读取网站，不需要邮件配置
python monitor.py --mode check
```

监控与测试邮件从环境变量读取 `SMTP_USERNAME`、`SMTP_PASSWORD`、`MAIL_TO`。可通过自己使用的运行环境注入，避免将授权码写入脚本或命令历史：

```sh
# 配置上述环境变量后
python monitor.py --mode test-email
python monitor.py --mode monitor
```

本地默认 SMTP 同样为 QQ，可通过环境变量 `SMTP_HOST`、`SMTP_PORT` 调整。需要新建基线时，可在确认不覆盖既有状态的前提下运行 `python monitor.py --mode initialize`；若状态文件已存在，此模式会拒绝覆盖。

Windows 等缺少 IANA 时区数据库的环境需要先提供该数据库，例如安装 Python 的 `tzdata` 包，以支持邮件中的北京时间转换。

本项目为个人动态提醒工具，非网站官方服务。动态内容及图片版权归原作者所有。
