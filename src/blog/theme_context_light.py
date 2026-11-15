"""前台专用的轻量主题上下文处理器。

djust 自带的 ``djust.theming.context_processors.theme_context`` 会把 4 个预渲染
主题组件（theme_panel / theme_switcher / theme_preset_selector / theme_mode_toggle）、
完整的 theme_head HTML 以及 71 个主题预设列表全部塞进模板 context。这些变量在前台
一个都没用到，却会被 LiveView 连同 context 一起 msgpack 序列化进内存 state：
实测同一会话第二次访问首页时 state 达 133.7KB（其中主题组件约 84KB），触发
``DjustPerformanceWarning``，并让每次 SSE 事件都多搬运上百 KB。

这里只提供模板真正读取的 4 个标量；主题 CSS / anti-FOUC 脚本仍由
``{% theme_head %}`` 标签自行渲染（该标签通过 build_theme_head_context 独立取状态，
不依赖 context processor 的返回值）。
"""
from djust.theming.manager import get_theme_manager

_DEFAULTS = {
    'theme_resolved_mode': 'light',
    'theme_pack': 'cn_shuimo',
    'theme_mode': 'light',
    'theme_preset': 'cn_shuimo',
}


def theme_context_light(request):
    try:
        state = get_theme_manager(request).get_state()
        return {
            'theme_resolved_mode': state.resolved_mode,
            'theme_pack': state.pack or 'cn_shuimo',
            'theme_mode': state.mode,
            'theme_preset': state.preset,
        }
    except Exception:
        # 主题配置异常不能让整页 500，回落到默认浅色主题
        return dict(_DEFAULTS)
