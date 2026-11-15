"""让 request.user 在同步 middleware 链里完成求值。

djust 的 SSE 视图是 async，会在 _request_user_pk 里读 request.user.pk；
AuthenticationMiddleware 挂的是 SimpleLazyObject，首次求值要查 session/用户表，
在 async 上下文会抛 SynchronousOnlyOperation（登录用户打开任何 LiveView 页面 500，
匿名访问因不需查库而正常）。这里提前触发一次求值即可让后续属性读取不再查库。
"""


class EagerUserMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, 'user', None)
        if user is not None:
            _ = user.is_authenticated
            _ = getattr(user, 'pk', None)
        return self.get_response(request)
