"""三个国风主题包（墨韵 / 青花 / 敦煌），经 settings.DJUST_THEMES 注册。"""

from djust.theming.themes._base import (
    AnimationStyle,
    ColorScale,
    DesignSystem,
    IconStyle,
    InteractionStyle,
    LayoutStyle,
    SurfaceStyle,
    ThemePack,
    ThemePreset,
    ThemeTokens,
    TypographyStyle,
    ILLUST_LINE,
    PATTERN_MINIMAL,
)


# 字体栈：CDN 不可达时回退系统楷体 / 宋体
FONT_STACK = (
    '"LXGW WenKai", "LXGW WenKai Lite", "Kaiti SC", "STKaiti", "KaiTi", '
    '"Songti SC", "STSong", "SimSun", serif'
)


# 由精简色板派生完整 ThemeTokens
def _tokens(p: dict) -> ThemeTokens:
    """只写关键颜色，其余 token 按语义派生。"""

    def c(key, default=None):
        value = p.get(key)
        if value is not None:
            return ColorScale(*value) if isinstance(value, tuple) else value
        if default is None:
            raise KeyError(f"theme token '{key}' is required")
        return default

    background = c("background")
    foreground = c("foreground")
    card = c("card", background)
    card_foreground = c("card_foreground", foreground)
    primary = c("primary")
    primary_foreground = c("primary_foreground")
    muted = c("muted", background)
    muted_foreground = c("muted_foreground", foreground)
    border = c("border", muted)
    white = ColorScale(0, 0, 100)

    return ThemeTokens(
        background=background,
        foreground=foreground,
        card=card,
        card_foreground=card_foreground,
        popover=c("popover", card),
        popover_foreground=c("popover_foreground", card_foreground),
        primary=primary,
        primary_foreground=primary_foreground,
        secondary=c("secondary", muted),
        secondary_foreground=c("secondary_foreground", foreground),
        muted=muted,
        muted_foreground=muted_foreground,
        accent=c("accent", muted),
        accent_foreground=c("accent_foreground", foreground),
        destructive=c("destructive", primary),
        destructive_foreground=c("destructive_foreground", primary_foreground),
        success=c("success", ColorScale(150, 26, 36)),
        success_foreground=c("success_foreground", white),
        warning=c("warning", ColorScale(38, 55, 46)),
        warning_foreground=c("warning_foreground", white),
        info=c("info", ColorScale(210, 28, 38)),
        info_foreground=c("info_foreground", white),
        link=c("link", primary),
        link_hover=c("link_hover", primary),
        code=c("code", muted),
        code_foreground=c("code_foreground", foreground),
        selection=c("selection", primary),
        selection_foreground=c("selection_foreground", primary_foreground),
        brand=c("brand", primary),
        brand_foreground=c("brand_foreground", primary_foreground),
        border=border,
        input=c("input", border),
        ring=c("ring", primary),
        surface_1=c("surface_1", background),
        surface_2=c("surface_2", card),
        surface_3=c("surface_3", card),
    )


def _extra_vars(pattern: str, rust: str, dark: str, panel: str,
                text: str, muted: str, border: str) -> dict:
    """品牌变量 + hero 纹路（hsl(var(--border)) 延迟展开，明暗自适应）。"""
    return {
        "background-image-grid-pattern": pattern,
        "background-image-gradient-radial": "radial-gradient(var(--tw-gradient-stops))",
        "animation-pulse-slow": "pulse 4s cubic-bezier(0.4, 0, 0.6, 1) infinite",
        "color-brand-rust": rust,
        "color-brand-dark": dark,
        "color-brand-panel": panel,
        "color-brand-text": text,
        "color-brand-muted": muted,
        "color-brand-border": border,
        "color-brand-django": "#44B78B",
        "color-brand-danger": "#F43F5E",
        "color-brand-success": "#10B981",
    }


# 共用设计系统
def _typography(name: str, *, scale: float = 1.25, prose: str = "38rem",
                spacing: str = "0.02em") -> TypographyStyle:
    return TypographyStyle(
        name=name,
        heading_font=FONT_STACK,
        body_font=FONT_STACK,
        base_size="16px",
        heading_scale=scale,
        line_height="1.75",
        body_line_height="1.9",
        heading_weight="600",
        section_heading_weight="600",
        body_weight="400",
        letter_spacing=spacing,
        prose_max_width=prose,
        badge_radius="2px",
    )


def _layout(name: str, *, container: str = "960px", hero_max: str = "46rem",
            section: str = "4rem", gap: str = "1.75rem",
            shape: str = "rounded") -> LayoutStyle:
    return LayoutStyle(
        name=name,
        space_unit="1rem",
        space_scale=1.5,
        border_radius_sm="2px",
        border_radius_md="4px",
        border_radius_lg="8px",
        button_shape=shape,
        card_shape=shape,
        input_shape=shape,
        container_width=container,
        grid_gap=gap,
        section_spacing=section,
        hero_padding_top="8rem",
        hero_padding_bottom="5rem",
        hero_line_height="1.15",
        hero_max_width=hero_max,
    )


def _surface(name: str, *, shadow: str = "none") -> SurfaceStyle:
    return SurfaceStyle(
        name=name,
        shadow_sm=shadow,
        shadow_md=shadow,
        shadow_lg=shadow,
        border_width="1px",
        border_style="solid",
        surface_treatment="flat",
        backdrop_blur="0px",
        noise_opacity=0.0,
    )


def _icon(name: str) -> IconStyle:
    return IconStyle(name=name, style="outlined", weight="thin",
                     size_scale=0.95, stroke_width="1.2", corner_rounding="0")


def _animation(name: str) -> AnimationStyle:
    return AnimationStyle(
        name=name,
        entrance_effect="fade",
        exit_effect="fade",
        hover_effect="none",
        hover_scale=1.0,
        hover_translate_y="0px",
        click_effect="none",
        loading_style="spinner",
        transition_style="gentle",
        duration_fast="0.12s",
        duration_normal="0.24s",
        duration_slow="0.4s",
        easing="ease-in-out",
    )


def _interaction(name: str) -> InteractionStyle:
    return InteractionStyle(
        name=name,
        button_hover="darken",
        link_hover="underline",
        card_hover="border",
        button_click="none",
        focus_style="outline",
        focus_ring_width="1px",
        focus_ring_offset="2px",
        cursor_style="pointer",
    )


def _design_system(name: str, display_name: str, description: str,
                   **kwargs) -> DesignSystem:
    return DesignSystem(
        name=name,
        display_name=display_name,
        description=description,
        category="elegant",
        typography=_typography(name, **kwargs.pop("typography", {})),
        layout=_layout(name, **kwargs.pop("layout", {})),
        surface=_surface(name, **kwargs.pop("surface", {})),
        icons=_icon(name),
        animation=_animation(name),
        interaction=_interaction(name),
    )


def _pack(name: str, display_name: str, description: str) -> ThemePack:
    return ThemePack(
        name=name,
        display_name=display_name,
        description=description,
        category="elegant",
        design_theme=name,
        color_preset=name,
        icon_style=_icon(name),
        animation_style=_animation(name),
        pattern_style=PATTERN_MINIMAL,
        interaction_style=_interaction(name),
        illustration_style=ILLUST_LINE,
    )


# 1. 墨韵 · 水墨  —  宣纸 / 松烟墨 / 朱砂印
SHUIMO_LIGHT = {
    "background": (40, 30, 95),
    "foreground": (30, 14, 13),
    "card": (42, 34, 98),
    "primary": (6, 58, 44),
    "primary_foreground": (40, 40, 97),
    "muted": (38, 18, 90),
    "muted_foreground": (30, 8, 42),
    "border": (35, 15, 80),
    "link": (6, 50, 38),
    "link_hover": (6, 60, 28),
    "code": (38, 14, 91),
    "code_foreground": (30, 14, 20),
    "selection": (6, 60, 88),
    "selection_foreground": (30, 14, 13),
    "surface_1": (40, 26, 92),
    "surface_2": (40, 22, 96),
    "surface_3": (42, 34, 98),
    "success": (150, 24, 34),
    "warning": (38, 52, 44),
    "info": (210, 22, 38),
}
SHUIMO_DARK = {
    "background": (30, 14, 9),
    "foreground": (40, 26, 88),
    "card": (30, 11, 13),
    "primary": (6, 62, 58),
    "primary_foreground": (30, 16, 8),
    "muted": (30, 9, 18),
    "muted_foreground": (40, 12, 62),
    "border": (30, 9, 25),
    "link": (6, 60, 65),
    "link_hover": (6, 70, 76),
    "code": (30, 14, 6),
    "code_foreground": (6, 58, 70),
    "selection": (6, 45, 26),
    "selection_foreground": (40, 26, 92),
    "surface_1": (30, 16, 7),
    "surface_2": (30, 14, 10),
    "surface_3": (30, 11, 14),
    "success": (150, 26, 52),
    "warning": (38, 55, 56),
    "info": (210, 30, 58),
}
SHUIMO_EXTRA = _extra_vars(
    pattern="repeating-linear-gradient(90deg, transparent 0 35px, hsl(var(--border) / 0.30) 35px 36px)",
    rust="#B3392C", dark="#1B1712", panel="#2A241C",
    text="#EDE4D2", muted="#9A8D78", border="#3B332A",
)

# 2. 青花 · 瓷  —  瓷白 / 钴蓝 / 釉下彩
QINGHUA_LIGHT = {
    "background": (195, 26, 97),
    "foreground": (212, 46, 17),
    "card": (190, 32, 99),
    "primary": (214, 62, 38),
    "primary_foreground": (0, 0, 100),
    "muted": (200, 22, 92),
    "muted_foreground": (212, 20, 44),
    "border": (205, 24, 82),
    "link": (214, 62, 38),
    "link_hover": (214, 70, 27),
    "code": (205, 24, 93),
    "code_foreground": (212, 46, 22),
    "selection": (214, 65, 88),
    "selection_foreground": (212, 46, 17),
    "surface_1": (198, 26, 94),
    "surface_2": (196, 26, 97),
    "surface_3": (190, 32, 99),
    "success": (168, 30, 34),
    "warning": (38, 55, 46),
    "info": (214, 40, 44),
}
QINGHUA_DARK = {
    "background": (214, 46, 9),
    "foreground": (195, 26, 90),
    "card": (214, 40, 13),
    "primary": (210, 70, 62),
    "primary_foreground": (214, 50, 8),
    "muted": (214, 30, 18),
    "muted_foreground": (200, 18, 62),
    "border": (214, 30, 25),
    "link": (210, 70, 66),
    "link_hover": (210, 78, 78),
    "code": (214, 48, 6),
    "code_foreground": (195, 30, 88),
    "selection": (214, 55, 26),
    "selection_foreground": (195, 26, 94),
    "surface_1": (214, 50, 7),
    "surface_2": (214, 46, 10),
    "surface_3": (214, 40, 14),
    "success": (168, 32, 52),
    "warning": (38, 55, 56),
    "info": (210, 45, 58),
}
QINGHUA_EXTRA = _extra_vars(
    pattern=(
        "linear-gradient(to right, hsl(var(--border) / 0.38) 1px, transparent 1px), "
        "linear-gradient(to bottom, hsl(var(--border) / 0.38) 1px, transparent 1px)"
    ),
    rust="#2A5CAA", dark="#08192B", panel="#10263E",
    text="#E4EEF6", muted="#8FA7BE", border="#1E3A55",
)

# 3. 敦煌 · 朱砂  —  壁画土黄 / 赭红 / 石绿
DUNHUANG_LIGHT = {
    "background": (36, 46, 93),
    "foreground": (25, 30, 16),
    "card": (36, 48, 97),
    "primary": (10, 58, 42),
    "primary_foreground": (36, 46, 97),
    "muted": (35, 30, 87),
    "muted_foreground": (25, 20, 42),
    "border": (32, 26, 76),
    "link": (10, 52, 36),
    "link_hover": (10, 62, 27),
    "code": (35, 30, 88),
    "code_foreground": (25, 30, 20),
    "selection": (10, 55, 86),
    "selection_foreground": (25, 30, 16),
    "surface_1": (34, 38, 90),
    "surface_2": (36, 42, 94),
    "surface_3": (36, 48, 97),
    "success": (152, 28, 34),
    "warning": (40, 62, 44),
    "info": (190, 30, 36),
}
DUNHUANG_DARK = {
    "background": (25, 26, 9),
    "foreground": (36, 36, 88),
    "card": (25, 23, 13),
    "primary": (10, 66, 60),
    "primary_foreground": (25, 26, 9),
    "muted": (25, 20, 18),
    "muted_foreground": (36, 20, 62),
    "border": (25, 20, 26),
    "link": (10, 66, 66),
    "link_hover": (10, 74, 76),
    "code": (25, 28, 6),
    "code_foreground": (36, 40, 84),
    "selection": (10, 48, 24),
    "selection_foreground": (36, 36, 92),
    "surface_1": (25, 30, 7),
    "surface_2": (25, 26, 10),
    "surface_3": (25, 23, 14),
    "success": (152, 30, 52),
    "warning": (40, 62, 56),
    "info": (190, 34, 56),
}
DUNHUANG_EXTRA = _extra_vars(
    pattern="radial-gradient(hsl(var(--border) / 0.45) 0.8px, transparent 0.8px)",
    rust="#A63A2A", dark="#1C150E", panel="#2E2115",
    text="#F0E1C4", muted="#A4916F", border="#453420",
)


# 注册
def _preset(name: str, display_name: str, description: str,
            light: dict, dark: dict, extra: dict, radius: float) -> ThemePreset:
    return ThemePreset(
        name=name,
        display_name=display_name,
        description=description,
        light=_tokens(light),
        dark=_tokens(dark),
        radius=radius,
        default_mode="light",
        extra_css_vars=extra,
    )


PRESETS = {
    "cn_shuimo": _preset(
        "cn_shuimo", "墨韵 · 水墨",
        "宣纸米白、松烟墨与朱砂印，帘纹留白",
        SHUIMO_LIGHT, SHUIMO_DARK, SHUIMO_EXTRA, 0.2,
    ),
    "cn_qinghua": _preset(
        "cn_qinghua", "青花 · 瓷",
        "瓷白微青、钴蓝釉下彩，细网格如瓷纹",
        QINGHUA_LIGHT, QINGHUA_DARK, QINGHUA_EXTRA, 0.3,
    ),
    "cn_dunhuang": _preset(
        "cn_dunhuang", "敦煌 · 朱砂",
        "壁画土黄、赭红与石绿，斑驳点阵",
        DUNHUANG_LIGHT, DUNHUANG_DARK, DUNHUANG_EXTRA, 0.25,
    ),
}

DESIGN_SYSTEMS = {
    "cn_shuimo": _design_system(
        "cn_shuimo", "墨韵 · 水墨", "楷体、窄栏、无阴影 —— 留白即是内容",
        typography={"scale": 1.3, "prose": "34rem", "spacing": "0.04em"},
        layout={"container": "860px", "hero_max": "38rem", "section": "5rem",
                "gap": "2rem", "shape": "sharp"},
    ),
    "cn_qinghua": _design_system(
        "cn_qinghua", "青花 · 瓷", "楷体、匀称网格、细线收边",
        typography={"scale": 1.25, "prose": "38rem"},
        layout={"container": "980px", "hero_max": "48rem", "section": "4rem",
                "gap": "1.75rem"},
    ),
    "cn_dunhuang": _design_system(
        "cn_dunhuang", "敦煌 · 朱砂", "楷体、宽栏、暖色留白",
        typography={"scale": 1.28, "prose": "40rem", "spacing": "0.03em"},
        layout={"container": "1020px", "hero_max": "50rem", "section": "4.5rem",
                "gap": "2rem", "shape": "sharp"},
        surface={"shadow": "0 2px 10px hsl(25 30% 16% / 0.06)"},
    ),
}

THEME_PACKS = {
    "cn_shuimo": _pack(
        "cn_shuimo", "墨韵 · 水墨", "宣纸 · 松烟墨 · 朱砂印",
    ),
    "cn_qinghua": _pack(
        "cn_qinghua", "青花 · 瓷", "瓷白 · 钴蓝 · 釉下彩",
    ),
    "cn_dunhuang": _pack(
        "cn_dunhuang", "敦煌 · 朱砂", "土黄 · 赭红 · 石绿",
    ),
}

__all__ = ["PRESETS", "DESIGN_SYSTEMS", "THEME_PACKS", "FONT_STACK"]
