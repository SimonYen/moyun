"""Keep the theme mode cookie and djust's session state in sync."""
from django.conf import settings

_config = settings.LIVEVIEW_CONFIG.get('theme', {})
_namespace = (_config.get('cookie_namespace') or '').strip()
COOKIE_NAME = f"{_namespace}_djust_theme_mode" if _namespace else 'djust_theme_mode'
SESSION_KEY = 'djust_theme'
VALID_MODES = frozenset({'light', 'dark', 'system'})
DEFAULT_MODE = _config.get('default_mode', 'light')
MAX_AGE = 31536000


class ThemeModeCookieMiddleware:
    """Cookie is the source of truth; seed it on first visit and mirror it into the session."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        state = request.session.get(SESSION_KEY) or {}
        cookie_mode = request.COOKIES.get(COOKIE_NAME)
        session_mode = state.get('mode')
        mode = cookie_mode if cookie_mode in VALID_MODES else (
            session_mode if session_mode in VALID_MODES else DEFAULT_MODE
        )
        if state.get('mode') != mode:
            state['mode'] = mode
            request.session[SESSION_KEY] = state

        response = self.get_response(request)
        if cookie_mode != mode:
            response.set_cookie(
                COOKIE_NAME, mode, max_age=MAX_AGE, path='/', samesite='Lax'
            )
        return response
