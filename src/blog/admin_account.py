"""后台账号设置：原生表单修改登录用户名与密码。"""
from django.contrib.auth import get_user_model, update_session_auth_hash
from django.shortcuts import redirect, render


def admin_account(request):
    if not (request.user.is_authenticated and request.user.is_active and request.user.is_staff):
        return redirect('/admin/login/?next=/admin/account/')

    user = request.user
    error = ''
    success = ''
    if request.method == 'POST':
        new_username = (request.POST.get('username') or '').strip()
        current_password = request.POST.get('current_password') or ''
        new_password = request.POST.get('new_password') or ''
        confirm = request.POST.get('confirm_password') or ''
        User = get_user_model()

        if not user.check_password(current_password):
            error = '当前密码不正确。'
        elif not new_username:
            error = '用户名不能为空。'
        elif len(new_username) > 150:
            error = '用户名太长（最多 150 个字符）。'
        elif new_username != user.username and User.objects.filter(username=new_username).exists():
            error = '这个用户名已被占用。'
        elif new_password and new_password != confirm:
            error = '两次输入的新密码不一致。'
        elif new_password and len(new_password) < 8:
            error = '新密码至少 8 位。'
        else:
            user.username = new_username
            if new_password:
                user.set_password(new_password)
            user.save()
            # 改密码后保持当前会话不掉线
            update_session_auth_hash(request, user)
            success = '账号信息已更新，下次登录请使用新的用户名和密码。'

    return render(request, 'djust_admin/account.html', {
        'username': user.get_username(),
        'error': error,
        'success': success,
    })
