# djust 博客

一个用 **Django 5.2 + djust 1.2.8** 写的博客示例：服务端 LiveView 交互、Markdown 写作、三套国风主题、后台数据看板、独立图床与相册。

纯 ASGI / SSE，不需要 Node、不需要前端构建步骤，也不需要 WebSocket。

## 功能

- **前台**：首页、文章列表（实时搜索 + 标签筛选）、文章详情、图床相册（按分类筛选 + Lightbox 翻阅）
- **主题**：墨韵·水墨 / 青花·瓷 / 敦煌·朱砂，明暗切换，霞鹜文楷字体，偏好存 cookie
- **后台**：数据看板（热力图 / 词云 / 日历）、VDitor 所见即所得 Markdown 编辑器、图床管理
- **数据**：博客 JSON 导入导出、图片 ZIP 导入导出（保持文件名，Markdown 链接不失效）

## 技术栈

| 层 | 选型 |
| --- | --- |
| Web | Django 5.2.19 + djust 1.2.8（LiveView / Rust 模板引擎） |
| 服务器 | granian 2.8.7，`--interface asginl --no-ws` |
| 传输 | SSE（`/djust/sse/`），不走 WebSocket |
| 存储 | SQLite + 本地 `media/` 目录 |
| 前端 | 无框架、无构建步骤；VDitor、霞鹜文楷、Tailwind 全部本地 `static/`，无外部 CDN 依赖 |

## 启动方式

**只需一条命令：**
```sh
sh start.sh
```

`start.sh` 已完成所有初始化并直接启动服务。端口默认 `8000`，通过 `$PORT` 环境变量修改。

打开 <http://127.0.0.1:8000/>，后台在 `/admin/`，默认账号 `admin` / `admin12345`（**仅本地演示，上线务必改**）。

## 环境变量

所有配置参数在 `start.sh` 中统一维护，优先读环境变量，读不到用默认值；`settings.py` 直接 `os.environ.get()` 读取，启动脚本**不改写源码**。项目不读 `.env` 文件，请直接 `export` 变量后再运行（变量名见 `.env.example`）。

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `DJANGO_SECRET_KEY` | 开发用占位值 | 生产必填，用 `python -c "import secrets;print(secrets.token_urlsafe(50))"` 生成 |
| `BLOG_ADMIN_PASSWORD` | `admin12345` | 首次初始化创建 admin 时的密码 |
| `DJANGO_ALLOWED_HOSTS` | `*` | 逗号分隔，生产改成真实域名 |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | 本地回环域名 | 逗号分隔；反代改写 Host 时必须配，否则所有 POST 被 CSRF 拦成 403 |
| `PORT` | `8000` | 监听端口 |
| `SKIP_DEMO_DATA` | 空 | 设为 `1` 跳过相册演示数据 |

> ⚠️ **上线前必做**
> 1. 设置 `DJANGO_SECRET_KEY`；
> 2. 设置 `BLOG_ADMIN_PASSWORD`，或部署后立刻在后台改掉默认口令；
> 3. 把 `DJANGO_ALLOWED_HOSTS` / `DJANGO_CSRF_TRUSTED_ORIGINS` 改成自己的域名。

## 上传到 GitHub

```bash
unzip djust-blog-source.zip
cd djust-blog
git init
git add .
git commit -m "Initial import"
git remote add origin https://github.com/<you>/<repo>.git
git push -u origin main
```

`.gitignore` 只排除 `.venv/`、`__pycache__/`、`.env` 等无关文件；`db.sqlite3` 与 `media/` 是本站的数据本体，**需要一起提交**。

个人项目直接把数据库和图片随源码一起推送：部署时仓库整包上传即可带上全部内容，不需要在线同步。`bootstrap.py` 只在首次（库为空）时建表、创建管理员、生成 2 篇示例文章与 5 张相册示意图，不会覆盖已有数据。日常仍可用后台「数据与图床」导出 JSON / ZIP 做额外备份。

## 部署

### A. 单端口 PaaS / 容器（WorkBuddy 云应用等）

`start.sh` 已按平台约定读取 `$PORT`、绑定 `0.0.0.0`，并完成迁移与初始化：

```sh
pip install -r requirements.txt   # 安装命令
sh start.sh                       # 启动命令
```

启动脚本内部依次执行 `migrate --skip-checks` → `bootstrap.py` → 清理残留进程 → `granian`。

### B. 手动运行

```sh
export PORT=8000
export PYTHONPATH="$PWD/src"
sh start.sh
```

### 关于持久化

项目用 SQLite + 本地 `media/`，两者都随 git 提交，所以不需要持久卷，也不需要在线同步脚本（已移除）。

⚠️ 本地仓库是数据的权威来源：若在线上后台新增了文章或图片，而本地仓库仍是旧数据，重新发布会用本地版本覆盖线上。发布前请先在后台导出备份，或把线上数据提交回仓库。

### 反代注意事项

- 站点用 SSE，**不要**配置 WebSocket upgrade 转发。
- 反代改写 `Host` 时，`CSRF_TRUSTED_ORIGINS` 必须包含浏览器看到的 Origin，否则登录、上传、导入等 POST 全部 403。
- `SECURE_PROXY_SSL_HEADER` 已按 `X-Forwarded-Proto: https` 配好。

## 数据导入导出

后台 `/admin/data/` 提供两套独立备份：

- **博客 JSON**：按 slug upsert，导入不会删除现有文章；
- **图片 ZIP**：`images.json` + `files/<relpath>`，保持原文件名与 URL。

两套互不耦合。迁移时建议先导入图片再导入文章，Markdown 里的 `/media/images/...` 链接就能原样可用。

## 相册如何按文章分类

图片与文章**没有外键**。`GalleryView` 扫描已发布文章正文里的 `/media/images/<32hex>.<ext>` 引用，把图片归到该文章的 Tag 下；未被任何文章引用的图片进入「未归档」。

好处是导入导出不需要额外字段，文章换标签后相册自动跟着变。Lightbox 用的是 djust 的 `ImageLightbox` 服务端组件，翻页/关闭走 SSE 事件，键盘导航由页面一小段 JS 转成按钮点击。

## 目录结构

```
django_blog/          settings / urls / asgi（纯 HTTP + 静态文件处理器）
src/blog/             文章、标签、LiveView、主题、后台原生页面、导入导出
src/imagehost/        图床 APP：模型、上传、媒体服务、图片 ZIP 导入导出
templates/djust_admin/ 项目级覆盖的后台模板（原生页面 + 登录）
start.sh / bootstrap.py / seed_gallery.py   部署与初始化
static/                    字体、VDitor、Tailwind 等全部本地资源（无 CDN）
```

> VDitor 的 `cdn` 参数固定拼接 `/dist/js/...`，而应用发布平台会把名为 `dist/` 的目录当作构建产物过滤。因此仓库里保存的是 `static/vditor/_bundle/`，`start.sh` 启动时会自动还原成 `static/vditor/dist/`（该生成目录已被 `.gitignore` 排除）。

## 已知限制

- `DJANGO_SECRET_KEY` 占位值会导致管理命令的检查报错，因此迁移时加 `--skip-checks`。
- VDitor、霞鹜文楷、后台 Tailwind 全部在 `static/` 本地托管，断网也能正常写作；VDitor 的 `js/`（lute / i18n / 代码高亮等）已完整随包提供。
- djust 的 Rust 模板引擎不渲染 Django 表单对象，后台原生页面的字段 HTML 在视图里预渲染；模板注释 `{# ... #}` 必须写成单行。
- 默认管理员口令只用于本地演示，公网部署请立即更换。
