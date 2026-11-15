"""原生表单登录：避开 LiveView dj-input 的 debounce / 自动填充丢事件问题。"""
from django.contrib.auth import authenticate, login
from django.shortcuts import redirect, render

from djust.admin_ext import site as admin_site


def admin_login(request):
    next_url = request.POST.get('next') or request.GET.get('next') or '/admin/'
    if not next_url.startswith('/') or next_url.startswith('//'):
        next_url = '/admin/'

    if request.user.is_authenticated and request.user.is_active and request.user.is_staff:
        return redirect(next_url)

    error = ''
    username = ''
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        user = authenticate(request, username=username, password=password)
        if user is not None and user.is_active and user.is_staff:
            login(request, user)
            return redirect(next_url)
        error = '用户名或密码不正确。'

    return render(request, 'djust_admin/login_plain.html', {
        'error': error,
        'username': username,
        'next': next_url,
        'site_header': admin_site.site_header,
        'site_title': admin_site.site_title,
    })
