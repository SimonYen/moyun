# 墨韵

一个开箱即用的个人博客：文章、标签、相册、Markdown 写作、三套国风主题、后台数据导入导出。仓库里是一个**空博客**（没有示例文章和图片），`db.sqlite3` 自带管理员 `admin` / `admin`。

## 启动

```sh
sh start.sh
```

打开 <http://127.0.0.1:8000/>，后台在 `/admin/`，用 `admin` / `admin` 登录。

> **公网部署后第一件事：进后台「账号设置」改掉默认用户名和密码。** 项目没有任何初始化脚本，账号就存在数据库里，只能从后台改。

启动脚本只做数据库迁移（`migrate --skip-checks`）然后拉起服务，不生成演示数据、不创建账号。依赖用 `pip install -r requirements.txt` 安装（Python 3.12+），脚本会自动优先使用仓库里的 `.venv/bin/python`。

## 环境变量

`start.sh` 优先读环境变量，读不到用默认值；脚本不会改写源码，也不读 `.env` 文件。

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `DJANGO_SECRET_KEY` | 开发用占位值 | 生产必填：`python -c 'import secrets; print(secrets.token_urlsafe(50))'` |
| `DJANGO_ALLOWED_HOSTS` | `*` | 逗号分隔域名，生产改成真实域名 |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | 本地回环 + `https://*.app.workbuddy.host` | 逗号分隔、带协议；反代改写 Host 时必配，否则登录、上传等 POST 全部 403 |
| `PORT` | `8000` | 监听端口，绑定 `0.0.0.0` |
| `BLOG_USE_WEBSOCKET` | `1` | `1` = WebSocket（默认），`0` = 回退 SSE；网关不转发 WS 时设 `0` |

生产启动示例：

```sh
export DJANGO_SECRET_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(50))')"
export DJANGO_ALLOWED_HOSTS='blog.example.com'
export DJANGO_CSRF_TRUSTED_ORIGINS='https://blog.example.com'
PORT=8000 sh start.sh
```

## 部署

单端口 PaaS / 容器：安装命令 `pip install -r requirements.txt`，启动命令 `sh start.sh`，服务监听平台注入的 `$PORT`。

- 默认走 WebSocket `/ws/live/`：反代需转发 `Upgrade` / `Connection` 头并放行长连接，`wss://` 需透传 `X-Forwarded-Proto`；网关不支持就用 `BLOG_USE_WEBSOCKET=0 sh start.sh` 回退 SSE，功能一致。
- 生产把 `DJANGO_ALLOWED_HOSTS` 改成真实域名后，浏览器 Origin 必须同时被允许，否则 WS 握手会被拒绝。
- 当前是单 worker + 内存 channel layer；多 worker / 多实例需要换 Redis channel layer。
- 迁移带 `--skip-checks` 是预期行为（djust 的生产检查会拦住管理命令）。

## 数据与后台

- `db.sqlite3` 和 `media/` 是数据本体，随仓库提交，不需要持久卷，也没有在线同步机制。仓库里 `media/images/` 为空。
- 后台 `/admin/account/` 修改用户名和密码，改完当前会话保持登录。
- 后台 `/admin/data/` 可导出文章 JSON、图片 ZIP 做备份。
- 本地仓库是数据的权威来源：线上新增了内容而本地没同步时，重新发布会用本地版本覆盖线上，发布前请先导出备份。

## 仓库

<https://github.com/SimonYen/moyun>

字体、Markdown 编辑器、后台样式都在 `static/` 本地托管，断网也能写作。`static/vditor/_bundle/` 是 VDitor 资源的存放形式（部分发布平台会过滤名为 `dist/` 的目录），`start.sh` 启动时会自动还原成 `static/vditor/dist/`。
