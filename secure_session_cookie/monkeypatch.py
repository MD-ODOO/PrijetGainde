import logging
import werkzeug.wrappers

_logger = logging.getLogger(__name__)

if not getattr(werkzeug.wrappers.Response, "_secure_cookie_patch", False):
    _logger.info("Patching Werkzeug Response.set_cookie for secure session cookie")

    _orig = werkzeug.wrappers.Response.set_cookie

    def secure_set_cookie(self, key, value="", max_age=None, expires=None,
                          path="/", domain=None, secure=False, httponly=False,
                          samesite=None, **kwargs):

        if key == "session_id":
            secure = True
            httponly = True
            if not samesite:
                samesite = "Strict"

        return _orig(
            self, key, value=value, max_age=max_age, expires=expires,
            path=path, domain=domain, secure=secure, httponly=httponly,
            samesite=samesite, **kwargs
        )

    werkzeug.wrappers.Response.set_cookie = secure_set_cookie
    werkzeug.wrappers.Response._secure_cookie_patch = True
