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

---

## 十一、第十二轮：卡顿剖析与性能整改（2026-11-15）

### 11.1 实测方法

- `/home/simon/.cache/perf_probe.py`：各页面 8 次 HTTP 计时；首页在 5 组 CSS 变体下各采样 2.6 秒 `requestAnimationFrame` 帧间隔（静止 + 滚动）；记录长任务、字体分片请求、SSE 往返、搜索交互延迟。变体为 A 原样 / B 禁墨晕动画 / C 移除墨晕层 / D 禁 header 毛玻璃 / E 两者都禁。
- `/home/simon/.cache/perf_profile.py`：`cProfile` 剖析 3 次首页 LiveView GET，拆开 Python 侧调用树。

### 11.2 结论一：墨汁动画不是主要瓶颈，但按授权取消

| 变体 | 静止 fps | p95 帧间隔 | 滚动 fps |
| --- | --- | --- | --- |
| A 原样 | 60.0 | 17.3ms | 60.0 |
| B 禁墨晕动画 | 60.4 | 17.2ms | 60.0 |
| C 移除墨晕层 | 60.4 | 17.2ms | 60.0 |
| D 禁 header 毛玻璃 | 59.6 | 17.4ms | 60.0 |
| E 两者都禁 | 60.4 | 17.2ms | 60.0 |

五组都是满帧、p95 约 17.2ms、长任务 0。也就是说动画本身没有 canvas / rAF / JS 定时器，在测试环境里不产生主线程开销。但真机上仍有风险：3 个 46vmax 渐变层带 `scale()` 变换，叠加 sticky header 的 `backdrop-filter: blur(10px)` 会要求浏览器每帧重新采样整条 header 背后的像素，低端设备 / 移动端容易掉帧。按你的授权，**取消动态特性**：删掉全部 `@keyframes`、`will-change`、`visibilitychange` 暂停逻辑，只保留静态渐变纹理（首次栅格化后零运行时开销），并把 header 改为不透明底色、去掉毛玻璃。

### 11.3 结论二：Rust 引擎确实不慢，慢在它外围的 Python 层

`cProfile`（3 次首页 GET）优化前总计 **1.815s**，优化后 **0.829s**：

| 环节 | 优化前 | 优化后 | 说明 |
| --- | --- | --- | --- |
| `RustLiveView.render`（6 次） | 0.421s（约 41ms/次） | 0.168s（约 28ms/次） | Rust 引擎本体，只占整条链路 15–20% |
| `render_with_diff`（3 次） | 0.107s | 0.041s | VDOM diff |
| `theme_context` 上下文处理器（6 次） | **0.637s** | **0.254s** | 每次 GET 跑 2 次；888 次 `get_state()`、12 次枚举主题预设，并预渲染 4 个主题组件（面板 / 预设选择器等前台根本没用） |
| context 序列化 `normalize_django_value`（7152 次） | 0.232s | 明显下降 | 把 Django model 对象（含 Markdown 正文）转成 Rust 可消费的字典 |
| `_sync_state_to_rust` | 0.176s | 下降 | 135KB LiveView state |
| SQLite commit | 0.018s | 0.018s | 数据库本身几乎不耗时 |

**所以「有 Rust 引擎还这么慢」并不矛盾**：Rust 只负责渲染 + diff 那 30–40ms，时间花在它前面的主题系统、对象序列化、状态同步，以及它后面的 SSE 传输。

其它固有开销：
- `LIVEVIEW_CONFIG['use_websocket'] = False`：每次交互是一次 HTTP POST + EventSource 推送，比 WebSocket 多一次往返。
- 每个 SSE 事件都会**全量重渲染整个 `dj-root`**（50–58KB HTML）再算 diff，不是局部更新。
- 搜索框 `dj-debounce="300"`：实测从输入到结果更新 449ms，其中 300ms 是刻意等待用户停止打字，服务端约 150ms。

**关于 `Large LiveView state 133.7KB` 警告**：当时判断为「框架固有的 VDOM 快照」，第十二节深挖后确认是**误判**——真正来源是模板 context 里约 84KB 前台完全没用到的主题组件 HTML，见 12.2。该警告已在第十二轮从根源消除。

### 11.4 本轮改动

| 项 | 改动 |
| --- | --- |
| 动态背景 | 移除全部动画与暂停逻辑，保留静态墨韵渐变；header 去 `backdrop-filter` |
| 主题渲染 | `{% theme_head %}` → `{{ theme_head }}`（djust 官方推荐的预渲染变量），避免把同一个标签再渲染一遍；已核对 head 输出完整（critical CSS / deferred.css / components.css / theme.js / print.css 全在，未被转义） |
| LiveView state | `HomeView` / `PostListView` / `PostDetailView` 不再把文章对象、标签列表、整篇 Post 存在实例上；实例只留 `query` / `tag_slug` / `slug` 标量，列表统一在 `get_context_data()` 现查（SQLite 本地查询几毫秒，远便宜于序列化上百 KB） |
| 点赞与模型 | 见 11.5 |
| 回归脚本 | 点赞断言改为「详情页已无点赞按钮」，墨晕断言改为「静态渐变 / 无动画 / 无毛玻璃」，旧备份 likes 用例改名 |

### 11.5 点赞功能移除与数据库模型整理

- `Post.likes` 字段删除，生成并应用迁移 `src/blog/migrations/0002_remove_post_likes.py`（`RemoveField`）。当前 `blog_post` 表 10 列：`id, title, slug, excerpt, content, status, created_at, updated_at, published_at, author_id`。
- 同步清理：详情页点赞按钮与 `PostDetailView.like` 事件 / `likes` 上下文、文章列表的 `♥ {{ post.likes }}`、后台 `PostAdmin` 的 `readonly_fields` 与「Stats & timestamps」字段组（中文化为「时间戳」）、仪表盘「累计点赞」统计与「赞」列、导出 JSON 的 `likes` 字段、导入逻辑（旧版备份里的 `likes` 直接忽略，仍兼容）、数据页提示文案。
- 数据完整性：迁移后 **6 篇文章 / 5 标签 / 6 图片** 全部保留，`django_migrations` 已记录 `0001_initial` 与 `0002_remove_post_likes`。

### 11.6 优化效果

| 指标 | 优化前 | 优化后 | 变化 |
| --- | --- | --- | --- |
| 首页 GET | 350ms | **207ms** | −41% |
| 文章列表 GET | 251ms | **157ms** | −37% |
| 相册 GET | 213ms | **132ms** | −38% |
| 关于页 GET（纯 Django 视图） | 113ms | **80ms** | −29% |
| cProfile 3 次首页 | 1.815s | **0.829s** | −54% |
| SSE message 往返 | 53ms | **31ms** | −41% |
| 搜索输入 → 结果 | 509ms | **449ms** | −12%（300ms 是 debounce） |

### 11.7 回归结果

| 层面 | 结果 |
| --- | --- |
| HTTP 全量（`full_test_http.py`） | **137 / 137 通过** |
| 桌面 Firefox（`browser_full.py`） | **40 / 40 通过**，控制台 0 错误 |
| 移动端 390×844（`browser_mobile.py`） | **29 / 29 通过** |
| 合计 | **206 项，失败 0 项** |

### 11.8 残留事项与可选进一步优化

1. `DjustPerformanceWarning: Large LiveView state ~133KB` 当时判定为框架固有开销、本轮未处理；**第十二轮已从根源消除**，见 12.2–12.4。
2. 搜索仍有 300ms 前端 debounce。若还觉得打字反馈慢，可把 `dj-debounce` 降到 200ms，但会增加 SSE 请求频率。
3. 第九节记录的两条非致命提示（`StreamingHttpResponse` 同步迭代器、主题状态体积）依旧存在。
4. 本轮改动**尚未上线**，线上仍是「墨韵」上一版；等你确认后再同步原分享链接并复核。

---

## 十二、第十三轮：消除 `Large LiveView state` 警告（2026-11-15）

### 12.1 现象

在自己终端 `./start.sh` 后访问首页，stderr 稳定出现：

```
DjustPerformanceWarning: Large LiveView state detected for
'r9nxq3gssc3stbzzt35ft2sbp3cfjv66_liveview_/_t6b0515a0': 134–136KB
(threshold: 100KB)
```

重启 granian 后依旧出现。

### 12.2 定位：警告只在「同一会话第二次访问」触发

`/home/simon/.cache/state_probe2.py` hook `InMemoryStateBackend.set`，把每次 `serialize_msgpack()` 的真实长度和捕获到的警告对齐：

| 访问 | state 大小 |
| --- | --- |
| 首次 `GET /` | 27,413 B |
| 同会话第二次 `GET /` | **136,940 B（133.7KB）** ← 触发警告 |

`/home/simon/.cache/state_probe3.py` 解包 msgpack 对比两次结构：

| 位置 | 内容 | 大小 |
| --- | --- | --- |
| `root/[0]` | 模板源码字符串（两次相同） | 27,400 B |
| `root/[1]` | **模板 context dict（42 键，仅第二次出现）** | **109,331 B** |
| └ `theme_panel` | 主题面板 HTML（前台未使用） | 39,810 B |
| └ `posts` | 6 篇文章，每篇含完整 author dict | 23,969 B |
| └ `theme_head` | 主题 head HTML | 20,365 B |
| └ `theme_presets` | 71 个主题预设 | 12,200 B |
| └ `theme_switcher` | 主题切换器 HTML | 7,254 B |
| └ `theme_preset_selector` | 预设选择器 HTML | 3,789 B |
| └ `theme_mode_toggle` | 模式切换按钮 HTML | 808 B |

**约 84KB 是前台一个都没用到的主题组件**。它们由 `djust.theming.context_processors.theme_context` 预渲染后塞进模板 context，而 LiveView 会把整个 context 连同 VDOM 一起 msgpack 序列化进内存 state。第十一节把这笔账记到「框架 VDOM 快照」是误判，已更正。

### 12.3 修复

- 新增 `src/blog/theme_context_light.py`：只返回模板真正读取的 4 个标量（`theme_resolved_mode` / `theme_pack` / `theme_mode` / `theme_preset`），从 `get_theme_manager(request).get_state()` 取值，异常时回落默认浅色主题。
- `settings.py` 两个 TEMPLATES 后端的 `context_processors` 都从 `djust.theming.context_processors.theme_context` 换成轻量版。
- `base.html` 把 `{{ theme_head }}` 改回 `{% theme_head %}` 标签：该标签通过 `build_theme_head_context` 独立渲染，不占 context，因此 20KB HTML 不再进 state。上一轮为省一次标签渲染改成变量形式，反而把这段 HTML 塞进了 state；head 输出完整性与主题切换均已回归验证。

**没有调阈值**：`STATE_SIZE_WARNING_KB` 仍是框架默认 100KB。警告消失是因为 state 真的变小，而不是把报警器调哑。

### 12.4 结果

| 页面（同会话第 2 次访问） | 修复前 | 修复后 |
| --- | --- | --- |
| 首页 | 133.7KB | **51.3KB** |
| 文章列表 | 约 115KB | **31.6KB** |
| 相册 | — | **13.0KB** |
| 文章详情 | 约 101KB | **19.0KB** |
| 捕获到的警告 | 每次必现 | **0 条** |

9002 实例跑完全部 206 项回归后，stderr 只剩 `StreamingHttpResponse must consume synchronous iterators` 一条非致命提示。

响应时间（热实例，12 次均值）：

| 页面 | 最初 | 上一轮 | 本轮 |
| --- | --- | --- | --- |
| `/` | 350ms | 207ms | **151.8ms** |
| `/posts/` | 251ms | 157ms | **108.8ms** |
| `/gallery/` | 213ms | 132ms | **72.0ms** |
| `/about/` | 113ms | 80ms | **23.9ms** |

### 12.5 回归

**206 项 0 失败**：HTTP 137 / 桌面 Firefox 40 / 移动端 29；控制台 0 错误，外观菜单展开、深色即时生效、cookie 持久化均通过。

测试脚本自身修正：`NS_BINDING_ABORTED` 的忽略规则从「仅 `/djust/sse/` 路径」放宽到所有页面卸载取消的请求（VDitor 懒加载图标 `ant.js` 在切页时被取消属同类误报）；真实 4xx/5xx 仍由「静态资源无 4xx/5xx」独立断言覆盖。

### 12.6 残留与可选后续

1. `StreamingHttpResponse must consume synchronous iterators` 仍在：Django 对 SSE / 文件响应使用同步迭代器的性能提示，不影响功能。
2. state 里的 `posts` 仍约 24KB（6 篇，每篇是完整 Django model + author 对象）。文章增至约 20+ 篇时可能再次接近 100KB。可选优化：列表 / 首页改传精简 dict（title / slug / url / excerpt / published_at / author 字符串 / tags），并截断 `content`；本轮未做。
3. 本轮改动**尚未上线**，线上仍是更早的版本；等你确认后再同步原分享链接并复核。

---

## 十三、文章列表无限滚动 / 滚动渲染（A 方案）

需求：此前文章列表是 `list(qs[:60])` 硬截断，没有分页；改用滚动到底自动加载下一批，同时不能把刚压下去的 LiveView state / 响应速度带回来。

### 13.1 调研结论更正（重要）

第十四轮调研时判断「`dj-viewport-bottom` + `dj-stream` 在 SSE 模式同样成立」，**实测证明不成立**。djust 1.2.8 在本项目纯 ASGI / SSE（`--no-ws`、无 WebSocket）部署下有三条限制：

| 尝试 | 实测现象 | 根因 |
| --- | --- | --- |
| `stream()` / `stream_insert()` / `stream_reset()` 增量 op | op 完全不到浏览器 | `session_utils.py` 明确写「StreamsMixin 的 ops are not delivered to a transport today，`_get_stream_operations()` 无调用者」；另一套 `StreamingMixin` 的 async `stream_insert(name, html)` 要求 `_ws_consumer`，只有 WebSocket 才有 |
| `dj-stream="posts"` + `streams.posts` 容器 | 卡片只增不减：筛选到空结果时 DOM 里仍残留 29 张旧卡片 | 客户端对 stream 容器是「保留 DOM、只追加」语义；清空本该靠 `stream_reset` op，而该 op 在 SSE 下没有传输通道 |
| `dj-viewport-bottom="load_more"` | 滚动后卡片数不变，SSE session 反复重建（4+ 个 uuid）、出现 `404 /message/` 与 `[SSE] Message POST failed` | `initInfiniteScroll.dispatch()` 调 `window.djust.handleEvent()`，那是 `liveViewWS`（WebSocket）入口；SSE 下 `liveViewWS` 为 null → 降级成「整页 HTTP 重渲染」→ 页面重载 → `mount()` 重跑，`loaded` 永远回到第一页 |

另外，`get_context_data()` 返回的整个 context 会被 msgpack 序列化进 LiveView state（第十二节已证实）：原来 6 篇完整 Post 对象占 23,969 B。若无限滚动继续把累积的 model 实例放进 context，加载几十篇就会把 100KB 警告带回来。

### 13.2 最终实现

- `src/blog/views.py`
  - `POSTS_PER_PAGE = 3`（与桌面三列网格一行对齐；调大可减少 SSE 往返）。
  - `PostListView` 实例只多一个整数 `loaded`（已加载条数）；`query` / `tag_slug` / `loaded` 全是标量。列表一律 `_filtered_qs()` 现查，`.distinct()` 避免多标签 join 产生重复 `data-key`。
  - 新增 `_post_card()`：把 Post 投影成纯标量 dict（`pk` / `title` / `url` / `date` / `excerpt` / `tags` / `author`），正文 Markdown 不进 context。这也把 12.6 第 2 条留下的「可选优化」落地了。
  - `load_more` 事件：到底时直接 return，不做无效重渲染；`search` / `filter_tag` / `clear_filters` 一律 `_reset_paging()` 把 `loaded` 归零（等价于 `stream_reset` 的效果）。
  - 模板 context 用普通 `posts` 变量，不用 `streams.posts`，不用 `dj-stream` 容器。
- `src/blog/templates/blog/post_list.html`
  - 容器保持普通 `.post-grid`，卡片保留 `data-key="post-{{ post.pk }}"`；每轮渲染「已加载的全部卡片」，由 VDOM keyed diff 保留已有节点、只 patch 新增节点（实测第一张卡片的 `data-probe` 标记在 3→14 全程保留）。
  - 容器外放 `#post-sentinel` / `#load-more-btn`（`dj-click="load_more"`），提示必须是容器外的元素，否则会变成滚动哨兵。
  - `dj-root` 外一段自写脚本：`scroll` 监听（`passive` + `requestAnimationFrame` 节流），距底 120px 内点击按钮，700ms 冷却防连发；首屏延时 900ms 补一次以覆盖「内容不足一屏」的情况。按钮在 `has_more=False` 时不渲染，观察者自然停止。

**为什么这样仍是「用 djust 做滚动渲染」**：事件由 djust 的 `dj-click` DOM 委托走已验证可用的 SSE message 通道，服务端是 djust LiveView 的 `@event_handler` + Rust 模板引擎 + VDOM diff；只是把「触发端」从框架那条 SSE 下不可用的 WebSocket 入口换成自写滚动监听。项目里相册键盘导航也是同样的「自写 JS 转真实 click」模式。

### 13.3 性能：state 不回涨，反而更小

`/posts/` 同会话第 2 次访问的 `serialize_msgpack()`：

| 项 | 改造前 | 改造后 |
| --- | --- | --- |
| 整个 state | 32,409 B | **8,203 B**（-74.7%） |
| `posts` context | 23,969 B（6 个完整 model + author） | **513 B**（3 个标量 dict） |
| `Large LiveView state` 警告 | — | **0 条**（阈值仍是默认 100KB，未调） |

服务日志跑完 230 项回归后只有 `StreamingHttpResponse must consume synchronous iterators` 一条非致命提示。浏览器实测加载到 14 篇（3→6→9→12→14）期间无警告、无 SSE 错误。

### 13.4 回归结果

**230 项 0 失败**（干净单实例 9012，最终代码）：

| 套件 | 项数 | 结果 |
| --- | --- | --- |
| HTTP 全量 A–J | 137 | 0 失败 |
| 桌面 Firefox 全量 | 40 | 0 失败 |
| 移动端 390×844 | 29 | 0 失败 |
| 无限滚动专项（新增 `~/.cache/browser_infinite.py`） | 24 | 0 失败 |

专项覆盖：首屏只渲染第一批、分批逐步增长、最终加载全部、到底提示、已有卡片 DOM 节点保留、到底不重复追加、搜索/标签筛选重置分页、空结果容器清空、静态资源无 4xx、无 SSE/JS/控制台错误。测试临时创建 8 篇已发布文章凑够 14 篇，`atexit` 自动清理，回归后业务数据回到 **6 文章 / 5 标签 / 6 图片**。

**验证环境注意**：期间一度出现结果忽上忽下、SSE 反复 404，查明是 9003 端口被两个残留 granian 进程用 `SO_REUSEPORT` 同时监听（沙箱 `ps` 看不到这些进程，`pkill` 杀不掉），请求被随机分到不同进程、内存 state 不共享。换到干净端口 9011 / 9012 后结果稳定。这与项目里已记录的「残留进程陷阱」一致。

### 13.5 明日手动复测补充清单

1. 打开 `/posts/`：应显示 3 张卡片，右上「共 6 篇 · 已显示 3」，底部「··· 向下滚动，继续加载」。
2. 缓慢滚到底 → 自动追加 3 张，提示变「已经到底 · 共 6 篇」；再继续滚动，卡片数与提示不再变化，控制台无报错。
3. 加载过几批后输入关键词或点标签 → 列表立即回到第一批，不残留旧卡片；点「全部」恢复。
4. 输入不存在的关键词 → 显示「没有找到文章」，文章卡片区为空，且不会继续触发加载。
5. 手机端（或浏览器窄窗口）重复 1–3：单列、无横向溢出、汉堡菜单正常，滚动加载同样生效。
6. 想看多批加载：后台再发布 7–8 篇文章，桌面会按 3 篇一批逐次追加；想减少往返把 `views.py` 的 `POSTS_PER_PAGE` 调大即可。

### 13.6 遗留

- 示例文章标题仍是早期的技术向内容（属于文章数据，不是界面文案）；若要换成随笔风格可直接在后台改标题，不影响本轮实现。
- **已上线**：用户明确确认后重新部署，原分享链接不变 `https://djust-blog.app.workbuddy.host/?sharecode=35IPXHTHEO`。线上复核 **20 项全通过**（`~/.cache/online_verify.py`）：连续 12 次 `/posts/` 响应长度完全一致（54,773 B，说明没有残留旧进程分流）、首屏 3 篇、真实浏览器滚动 3→6 并提示「已经到底」、首页/关于/相册/文章详情/后台登录均 200、VDitor `dist/index.min.js` 与 `dist/index.css`、favicon、霞鹜文楷 CSS、Tailwind Play 全部 200、无控制台错误与失败请求。

