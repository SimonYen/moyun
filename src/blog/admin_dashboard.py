"""后台首页 dashboard：统计、发布热力图、词云、日历，全部服务端渲染。"""
import calendar
import collections
import datetime
import html
import re

from django.shortcuts import redirect, render
from django.utils import timezone

from .models import Post, Tag

# 国风色阶：宣纸 → 朱砂
HEAT = ['#efece4', '#e6d2c1', '#d3a184', '#bf6647', '#B3392C']
CLOUD = ['#B3392C', '#2A5CAA', '#4A6B53', '#8A6B3F', '#3B3B3B']
STOP = set('''的 了 和 是 在 我 有 就 不 也 都 与 及 或 一个 我们 这个 那个 可以 什么 如何
为 对 从 到 把 被 让 使 之 其 以 于 而 并 但 更 很 最 一 二 三 中 上 下 里 后 前 时
the and for with that this from are was were you your our not but can will have has'''.split())


def _tokens(text):
    words = re.findall(r'[A-Za-z][A-Za-z0-9_-]{1,}', text.lower())
    for seg in re.findall(r'[\u4e00-\u9fff]{2,}', text):
        words.extend(seg[i:i + 2] for i in range(len(seg) - 1))
    return [w for w in words if len(w) >= 2 and w not in STOP]


def _heatmap(dates, today):
    """近 26 周的 GitHub 风格发布热力图。"""
    counts = collections.Counter(dates)
    end = today + datetime.timedelta(days=(6 - (today.weekday() + 1) % 7) % 7)
    start = end - datetime.timedelta(weeks=26) + datetime.timedelta(days=1)
    cells = []
    cur = start
    while cur <= end:
        n = counts.get(cur, 0)
        level = 0 if n == 0 else min(4, 1 + (n - 1))
        cells.append(
            '<i class="hm-cell" style="background:%s" title="%s · %d 篇"></i>'
            % (HEAT[level], cur.isoformat(), n)
        )
        cur += datetime.timedelta(days=1)
    return ''.join(cells)


def _calendar(dates, today):
    counts = collections.Counter(dates)
    year, month = today.year, today.month
    cal = calendar.Calendar(firstweekday=0)
    cells = ['<span class="cal-dow">%s</span>' % d for d in '一二三四五六日']
    for day in cal.itermonthdates(year, month):
        if day.month != month:
            cells.append('<span class="cal-day cal-empty"></span>')
            continue
        n = counts.get(day, 0)
        cls = 'cal-day cal-has' if n else 'cal-day'
        if day == today:
            cls += ' cal-today'
        cells.append(
            '<span class="%s" style="%s" title="%s · %d 篇">%d</span>'
            % (cls, ('background:%s22;border-color:%s' % (HEAT[min(4, n)], HEAT[min(4, n)])) if n else '',
               day.isoformat(), n, day.day)
        )
    return ''.join(cells)


def _wordcloud(posts, tags):
    freq = collections.Counter()
    for p in posts:
        for w in _tokens(p.title):
            freq[w] += 6
        for w in _tokens(p.excerpt or ''):
            freq[w] += 2
        for w in _tokens(p.content or ''):
            freq[w] += 1
    for t in tags:
        freq[t.name] += 10
    top = freq.most_common(42)
    if not top:
        return '<p class="gf-empty">暂无内容，发布几篇文章后这里会热闹起来。</p>'
    hi = top[0][1] or 1
    out = []
    for i, (word, n) in enumerate(top):
        size = 13 + round(20 * (n / hi))
        out.append(
            '<span class="cw-word" style="font-size:%dpx;color:%s" title="%d 次">%s</span>'
            % (size, CLOUD[i % len(CLOUD)], n, html.escape(word))
        )
    return ''.join(out)


def admin_dashboard(request):
    if not (request.user.is_authenticated and request.user.is_active and request.user.is_staff):
        return redirect('/admin/login/?next=/admin/')

    today = timezone.localdate()
    posts = list(Post.objects.all().order_by('-created_at'))
    tags = list(Tag.objects.all())
    published = [p for p in posts if p.status == Post.Status.PUBLISHED]
    dates = [timezone.localtime(p.published_at).date() for p in published if p.published_at]
    month_start = today.replace(day=1)

    stats = [
        ('文章总数', len(posts), '篇'),
        ('已发布', len(published), '篇'),
        ('草稿', len(posts) - len(published), '篇'),
        ('标签', len(tags), '个'),
        ('本月发布', sum(1 for d in dates if d >= month_start), '篇'),
    ]
    recent = [
        (p.title, p.get_absolute_url(), p.status,
         timezone.localtime(p.published_at or p.created_at).strftime('%Y-%m-%d'))
        for p in posts[:6]
    ]

    return render(request, 'djust_admin/dashboard.html', {
        'stats': stats,
        'heatmap': _heatmap(dates, today),
        'calendar_html': _calendar(dates, today),
        'wordcloud': _wordcloud(posts, tags),
        'recent': recent,
        'month_label': '%d 年 %d 月' % (today.year, today.month),
        'username': request.user.get_username(),
        'heat_legend': HEAT[1:],
    })
