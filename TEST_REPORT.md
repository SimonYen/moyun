# 全量测试报告 · 2026-11-14

## 一、结论

| 项目 | 结果 |
| --- | --- |
| HTTP 层回归（A–J 共 10 组） | **126 / 126 通过** |
| 真实浏览器回归（Firefox + Playwright） | **32 / 32 通过** |
| 合计 | **158 项，失败 0 项** |
| 本轮发现并修复的真实缺陷 | 1 类，13 个触发点 |
| 测试数据 | 已全部清理，库内只剩 5 篇文章 / 5 标签 / 5 图片 |
| 线上同步 | 见第八节 |

自动化测试脚本：
- `/home/simon/.cache/full_test_http.py`（HTTP，结果 `/home/simon/.cache/full_test_results.json`）
- `/home/simon/.cache/browser_full.py`（真实浏览器，截图 `/home/simon/.cache/blog_{home,admin,login}.png`）

---

## 二、覆盖范围

**HTTP 层 126 项**

| 组 | 内容 | 项数 |
| --- | --- | --- |
| A | 未登录访问控制（后台各页、POST、上传） | 11 |
| B | 登录与会话（错误密码、CSRF、next 回跳、外链 next） | 8 |
| C | 文章 CRUD（新建/落库/自动 slug/Markdown/草稿隔离/编辑/删除/异常 ID） | 16 |
| D | 标签 CRUD（中文名、重复名、重复 slug、编辑、删除） | 8 |
| E | 图床与媒体（上传、去重、MIME、非法格式、超 5MB、路径校验） | 12 |
| F | 导入导出（JSON/ZIP 有效、upsert 幂等、图片链接保留、畸形文件） | 11 |
| G | 前台页面（首页/列表/相册/主题 CSS、404、XSS 转义） | 9 |
| H | 后台页面完整性（5 个页面、无 dj-root、无外部 CDN、退出登录） | 17 |
| I | 边界与安全（XSS、主题 cookie 注入、搜索特殊输入、路径遍历、开放重定向、ZIP 穿越、非法 UUID） | 22 |
| J | 畸形备份容错（16 种结构/字段异常） | 16 |

**浏览器层 32 项**：写作主链路、编辑页与列表页「停留不自动跳转」、VDitor 初始化、标签与删除确认、仪表盘入口、点赞 SSE、搜索/清除筛选 SSE、相册分类与灯箱、明暗切换与 cookie、静态资源、外部请求、控制台错误、字体加载、退出登录、截图。

---

## 三、发现并修复的缺陷

### BUG-01　畸形备份文件会让导入接口返回 500

**现象**：后台「数据与图床」里选错文件（例如把 ZIP 选进博客 JSON 导入框），或备份文件结构被改坏 / 来自旧版本，页面直接变成服务器错误页（500），而不是给出提示。

**触发点（13 个，修复前全部 500，修复后全部返回友好的 302 提示）**

- 图片备份里 `id` 不是合法 UUID → `ValidationError`（Django 校验异常未被捕获）
- 博客备份顶层是数组 / 字符串 → `AttributeError`
- `tags`、`posts` 不是列表 → 遍历字符串后 `.get()` 报错
- `tags` / `posts` 列表元素是字符串或 `null` → `.get()` 报错
- 图片备份 `images` 不是列表、元素是字符串、`images.json` 顶层是数组 → 同类报错

**根因**
1. `merge_blog` / `merge_images` 直接对外部文件内容做 `.get()`，没有校验顶层与列表结构；
2. `merge_images` 把备份里的 `id` 直接塞进 UUIDField，非法值触发 `ValidationError`；
3. 两个导入视图只捕获了 `ValueError / KeyError / TypeError / JSONDecodeError`，漏掉 `AttributeError / ValidationError / IntegrityError / UnicodeDecodeError`。

**修复**（`src/blog/admin_data.py`、`src/imagehost/views.py`）
- 先校验结构：顶层必须是对象，`tags/posts/images` 必须是列表，元素必须是对象；不合法抛中文 `ValueError`。
- 字段逐项容错：`id` 用 `uuid.UUID()` 安全解析（坏值重新生成）、`likes` 非数字归零、非法 `status` 回落草稿、单个坏日期只跳过该字段、名称按字段长度截断。
- 导入包在 `transaction.atomic()` 里，中途失败整体回滚，不留半截数据。
- 视图捕获更宽的异常，统一返回「导入失败：…」中文提示。
- 图片路径仍强制匹配 `images/<32位十六进制>.<扩展名>`，ZIP 路径穿越依旧被拒（已单测验证不会写出越界文件）。

**回归**：13/13 由 500 变为 302；F 组正常导入导出 11 项全部仍通过，说明正常备份不受影响。

---

## 四、记录但判定为「非缺陷」的项

| 项 | 判定依据 |
| --- | --- |
| 未登录上传图片返回 403 而非 401 | 匿名且完全无 token 的 POST 先被 Django CSRF 中间件拦截，属正常安全行为。已补测「带有效 CSRF token 但 session 过期」→ 视图正确返回 `401 JSON {"code":401,"msg":"需要登录"}`。 |
| 编辑页不显示「已保存」 | 提示只在 `?saved=1` 时出现（保存并继续编辑的重定向会带上）。原测试漏带参数；已同时验证普通编辑页不会误显示。 |
| Markdown 正文含 `onerror` 字样 | 渲染器把整段 HTML 转义成 `&lt;img …&gt;`，文本里仍含字符串但不可执行；改用「是否存在活动标签」判定，结果安全。 |
| 切页时 SSE 请求 `NS_BINDING_ABORTED` | 浏览器离开页面时主动取消未结束的 EventSource 长连接，是 SSE 正常生命周期；控制台 0 错误，点赞/搜索/相册交互均生效。 |

## 五、测试脚本自身修正（非产品代码）

- 补项目根到 `sys.path`（原脚本中途崩溃 `No module named django_blog`，并残留一条测试文章）。
- 修正 ZIP round-trip 的变量覆盖（原先把登录页 HTML 当 ZIP 上传）。
- 修正断言的运算符优先级；相册容器选择器由 `.gallery-item` 改为实际的 `.gf-album-item`。
- 加入退出时自动清理，即使中途异常也不残留测试数据。

---

## 六、数据清理

- 删除上轮崩溃残留的 `FULLTEST 文章 1794669571`。
- 删除早期 CSRF 测试留下的草稿 `origin-test-post`。
- 所有 E2E 自建文章 / 标签 / 图片均由脚本自动清理并删除对应图片文件。
- 当前库：5 篇文章（2 篇相册示例 + 3 篇初始示例）、5 个标签、5 张图片。

> 提示：3 篇初始示例文章标题含技术名词（如「用 Django 与 djust 构建一个实时博客」）。若不想在个人博客里展示，可在后台文章列表自行删除；我没有擅自删除它们。

---

## 七、明天手动复测清单

**最省事：直接用第八节的线上链接测** —— 线上已经是修复后的代码，不用启动任何东西。

如果要在本地测：用**全新端口**启动，例如 `PORT=9000 sh start.sh`，然后访问 `http://127.0.0.1:9000/`。
**不要**直接 `sh start.sh`：默认 8000 端口被一个位于其他进程命名空间、沙箱内结束不掉的旧实例占着，它内存里是旧代码，很容易误判成「改了没生效」。本次测试用的 8898 / 8899 实例已经关闭。

后台账号：`admin` / `admin12345`。

**① 写文章（原「自动跳转」bug，重点）**
1. 打开 `/admin/blog/post/add/` → 应跳到登录页，地址里带 `next=...add...`。
2. 登录后应**回到写新文章页**（不是仪表盘）。
3. 停留 5 秒 → 页面不动；VDitor 编辑器应完整显示（有工具栏，可输入）。
4. 填标题、正文，选「已发布」，保存 → 进入文章列表。
5. **在列表页停留 6 秒以上 → 不应自动跳到仪表盘**（这是原 bug）。
6. 前台打开这篇文章，能正常看到标题和 Markdown 渲染结果。

**② 编辑 / 标签 / 删除**
1. 列表点「编辑」→ 改标题 → 点「保存并继续编辑」→ 应显示绿色「已保存，可以继续编辑。」
2. 新建标签、编辑标签、删除确认页（只打开不提交）都应正常，且停留时不会跳走。
3. 仪表盘点「写新文章」应直接停在编辑页。

**③ 数据与图床（本轮修复点，重点）**
1. 「导出博客 JSON」「导出图片 ZIP」都能下载且能打开。
2. **故意选错文件**：把 ZIP 选到「导入博客」、把 JSON 选到「导入图片」→ 应回到数据页并显示中文「导入失败：…」，**不能出现 500 错误页**。
3. 正常导入一遍备份 → 文章数不重复增加（按 slug 更新）。
4. 编辑页里插入一张图片 → 图片 URL 形如 `/media/images/….png`，前台可见。

**④ 前台交互**
1. 文章详情页点「♥」→ 数字 +1（SSE 生效）。
2. `/posts/` 搜索框输入不存在的词 → 列表变空；点 ALL → 恢复。
3. `/gallery/` 点分类（如「水墨」）→ 图片数量变化；点图片 → 灯箱弹出，←/→/Esc 可用。

**⑤ 外观**
1. 右上角齿轮 → 点「深色」→ 页面立刻变暗；刷新后仍是深色。
2. 切换三套国风主题 → 页面刷新后配色改变。

**⑥ 退出登录**
1. 退出后访问 `/admin/` → 应跳回登录页。

**⑦ 观察项**：全站不应出现外部 CDN 请求、控制台不应有报错、字体不应加载失败。

---

## 八、线上同步

已按项目约定自动重新发布，分享链接保持不变：

**https://djust-blog.app.workbuddy.host/?sharecode=35IPXHTHEO**

部署后线上复核：

| 检查项 | 结果 |
| --- | --- |
| 首页 / 登录页 / 文章列表 / 相册 | 200 / 200 / 200 / 200 |
| VDitor JS / CSS / 中文语言包 / lute | 200，完整还原（`_bundle/` → `dist/`） |
| 后台样式、Tailwind、霞鹜文楷字体 | 200 |
| 后台登录 | 302 → 数据管理页 |
| **畸形备份导入连续 10 次** | **10 次全部 302**，修复生效且无残留旧进程 |
| 博客 JSON 导出 | 200，5 篇文章（与本地一致） |
| 图片 ZIP 导出 | 200 `application/zip` |

其它已知事项：
- 本地 8000 端口仍有一个残留实例（位于其他进程命名空间，沙箱内 `pkill` 无效）。它读磁盘上的新模板但内存里是旧配置，容易导致「改了没生效」的误判。在自己的终端里可执行 `pkill -9 -f "python -m granian"` 清掉后重新 `sh start.sh`。本次测试用的 8898 / 8899 已清理关闭。
- 线上链接直接 `curl` 不带 sharecode 会返回 403，用浏览器打开完整分享链接正常。

---

## 九、后续可选优化（本轮未改动）

测试结束后回收本地实例时，服务端日志带出两条**非致命**提示，均已记录，功能不受影响（158 项测试期间浏览器控制台 0 错误）：

| 提示 | 说明 | 处理 |
| --- | --- | --- |
| `StreamingHttpResponse must consume synchronous iterators...` | Django 对 SSE / 文件响应使用同步迭代器的性能提示 | 不影响 SSE 交互（点赞 / 搜索 / 相册筛选均已实测生效），暂不处理 |
| `DjustPerformanceWarning: Large LiveView state detected: 114–130KB (threshold 100KB)` | 首页 `/` 与文章列表 `/posts/` 的 LiveView 状态体积超过 djust 的 100KB 建议阈值 | 状态里带了文章列表与标签对象；文章增多时会继续变大。可用 djust 的 `temporary_assigns` 或把列表改为渲染时现查来优化 |

**为什么本轮没改**：这是性能提示而非功能缺陷，优化要调整 LiveView 的状态结构，属于架构改动；在功能全绿、线上刚发布的状态下，不宜未经完整回归就改动。建议等你明天手工复测确认功能无问题后，再单独安排这一项优化。

---

## 十、第十一轮：站点改名「墨韵」、关于页、中文导航、图标、移动端与墨汁背景（2026-11-15）

### 10.1 改动清单（对应你提的 6 点）

| # | 需求 | 落地位置 |
| --- | --- | --- |
| 1 | 正式名称统一为「墨韵」 | `base.html`（title / 品牌 / footer / 主题选项）、`home.html`、`post_list.html`、`post_detail.html`、`gallery.html`、`about.html`、7 个后台模板、`login_plain.html`、`django_blog/urls.py`（`admin_site.site_title` / `site_header`）、`.wbapp_*.genie`（应用显示名） |
| 2 | 新增「关于」页面 | `src/blog/urls.py` 加 `path('about/', about)`；`src/blog/views.py` 加普通 Django 视图 `about()`（不走 LiveView / SSE）；新增模板 `blog/about.html`，含「缘起」「这里有什么」两节国风文案，无任何技术栈表述 |
| 3 | navbar 中文化 + 去掉后台入口 | `base.html` 导航改为「首页 / 文章 / 相册 / 关于」，删除 `/admin/` 链接；后台仍可从 `/admin/` 直接访问，只是前台不再暴露 |
| 4 | 楷书「墨」字网页 icon | `static/favicon.png`（256×256）与 `static/favicon.ico`（PNG-in-ICO）。用项目自带的霞鹜文楷 regular 字形经本地浏览器渲染成朱砂印章白字，未用外部图片或 CDN；`base.html` 声明 ico / png / apple-touch-icon，`urls.py` 加 `/favicon.ico` → `/static/favicon.ico` 重定向，后台登录页同样声明 |
| 5 | 手机端阅读适配 | `base.html` 新增汉堡按钮 `#nav-toggle`（`aria-expanded` / `aria-controls`、点链接自动收起、Escape 关闭、当前页高亮）；shell / hero / post-grid 单列、搜索框与正文统一 `16px`（避免 iOS 输入框自动缩放）、代码块与表格横滚、图片自适应、like 按钮 44px 触控区；`gallery.html` 断点扩到 760px，网格 `minmax(140px,1fr)`、灯箱图 `92vw / 70vh` |
| 6 | 低开销墨汁流动背景 | `base.html` 新增 `.ink-flow` + 3 个 `.ink-blob`，纯 CSS `transform` / `opacity` 动画（GPU 合成层），**无 canvas、无 requestAnimationFrame、无 JS 定时器、无图片请求**；多层椭圆径向渐变模拟墨晕 |

### 10.2 墨汁背景的性能约束（逐条已测）

| 约束 | 实现 |
| --- | --- |
| 不占 CPU / 不卡滚动 | 只动 `transform` 与 `opacity`，元素 `will-change: transform`，`contain: layout paint style` 隔离重排重绘 |
| 移动端降负载 | `@media (max-width:760px)` 只保留 1 层墨晕，动画放慢到 96s |
| 后台标签页不耗电 | `visibilitychange` → `html.ink-paused`，`animation-play-state: paused` |
| 尊重系统设置 | `@media (prefers-reduced-motion: reduce)` → `animation: none` |
| 不遮挡交互 | `pointer-events: none`、`z-index: -1` |

### 10.3 本轮回归结果

| 层面 | 结果 |
| --- | --- |
| HTTP 全量（`full_test_http.py`，A–J 十组，含品牌 / 关于页 / 图标 / 墨晕断言） | **136 / 136 通过** |
| 桌面 Firefox（`browser_full.py`） | **40 / 40 通过**，控制台 0 错误、无外部 CDN 请求、字体分片全部加载 |
| 移动端 Firefox 390×844（`browser_mobile.py`） | **29 / 29 通过** |
| 合计 | **205 项，失败 0 项** |

### 10.4 本轮发现并处理的问题

1. **桌面灯箱关闭按钮被吸顶 header 拦截（真实回归）**：给 `main` 加 `position:relative; z-index:1` 会创建新的层叠上下文，把灯箱压到 header 之下。已删掉 `main` / footer 的 z-index，改为 `html` 承担背景色、`body` 透明、`.ink-flow { z-index:-1 }`。桌面灯箱开合已复测通过。
2. **移动端偶发 `[SSE] Message POST failed`（测试时序误报，非产品缺陷）**：关闭灯箱后脚本立刻跳页，尚未返回的 `message` POST 被浏览器主动取消。在测试脚本里等待 SSE 往返结束后再跳页，并为 console error 记录 URL；复跑后 SSE 错误 0，无需改产品代码。
3. **清理遗留文件**：删除 `static/js/vditor.min.js`（285KB，早期下载到错误路径留下的压缩脚本，全项目无任何引用）。当前 `static/js/` 只保留 `tailwind-play.js`。
4. **墨晕初版几乎不可见**：单层渐变透明度太低且墨团中心在视口外。改为多层椭圆渐变、提高透明度、把中心移入视口、加大漂移除幅度；截图目视确认淡朱砂墨晕可见且不干扰正文阅读。

### 10.5 明日复测补充清单（针对本轮 6 点）

① 手机真机或浏览器模拟 390px：汉堡按钮展开 / 收起、点「关于」跳转、四个页面均无横向滚动；② 手机上看文章正文，字号舒适、代码块可横滑；③ 手机相册点图放大、关闭按钮可点；④ 浏览器标签页右上角出现楷书「墨」字朱砂印章图标（含后台登录页）；⑤ 桌面首页静置十几秒，能看到淡墨晕缓慢漂移，快速滚动不卡顿；⑥ 系统开启「减少动态效果」后墨晕应静止；⑦ 切到别的标签页再回来，墨晕继续但无卡顿；⑧ 深色模式下墨晕仍可见且不过曝；⑨ 前台 navbar 只剩四个中文项、没有后台入口；⑩ 后台 `/admin/login/` 标题为「墨韵 · 后台」，写文章保存后仍不自动跳转。

### 10.6 线上状态

本轮改动**尚未同步到线上分享链接**。按发布平台规则，覆盖线上内容需要你本轮明确确认后再执行；确认后仍沿用原链接 `https://djust-blog.app.workbuddy.host/?sharecode=35IPXHTHEO`，并按惯例复核页面、VDitor / 字体静态资源与后台登录。
