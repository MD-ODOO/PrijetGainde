import werkzeug
import odoo
from odoo import http
from odoo.release import version_info  # (18, ...)
from werkzeug.wrappers import Response

import logging

_logger = logging.getLogger(__name__)

## v14, v15
if hasattr(http, "JsonRequest") and hasattr(http, "Root"):
    def check_secure_api(r, httprequest):
        is_secure_api = False
        api_type = "http"
        try:
            http._request_stack.push(r)
            db = r.session.db
            if db:
                try:
                    odoo.registry(db).check_signaling()
                    with odoo.tools.mute_logger('odoo.sql_db'):
                        ir_http = r.registry['ir.http']
                except Exception as e:
                    pass
                else:
                    rule, _ = ir_http._match(httprequest.path)
                    if rule.endpoint.routing.get("_is_secure_api", False):
                        is_secure_api = True
                        api_type = rule.endpoint.routing.get("type", "http")
            http._request_stack.pop()
        except Exception as e:
            pass
        return is_secure_api, api_type

    class JsonRequestAllowEmptyData(http.JsonRequest):
        def __init__(self, *args):
            try:
                super(JsonRequestAllowEmptyData, self).__init__(*args)
            except werkzeug.exceptions.BadRequest:  # avoid error "Invalid JSON data"
                self.jsonrequest = {}
                self.params = dict(self.jsonrequest.get("params", {}))
                self.context = self.params.pop("context", dict(self.session.context))
            except AttributeError:  # [{}, {}]
                self.jsonrequest = {"__params": self.jsonrequest}
                self.params = {"args": self.jsonrequest}
                self.context = dict(self.session.context)

    def get_request(self, httprequest):
        # deduce type of request
        if httprequest.mimetype in ("application/json", "application/json-rpc"):
            r = JsonRequestAllowEmptyData(httprequest)  # Secure API modified this line of code!
            is_secure_api, api_type = check_secure_api(r, httprequest)
            if is_secure_api and r._request_type != api_type:
                r._request_type = api_type    # Matching request and api type to avoid mismatch => BadRequest
            elif httprequest.path.count("api/jwt/token")>0: # special case: /api/jwt/token (declare http but allow json, then keep orignal response like "http")
                r = http.HttpRequest(httprequest)
        else:
            r = http.HttpRequest(httprequest)
            is_secure_api, api_type = check_secure_api(r, httprequest)
            # Dec 17, 2025: All APIs managed by Secure API are type "json"
            if is_secure_api:
                r = JsonRequestAllowEmptyData(httprequest)
                r._request_type = api_type    # Matching request and api type to avoid mismatch => BadRequest
        return r

    http.Root.get_request = get_request  # overwrite original "get_request" method in Root class
    _logger.info("Secure API: Overwrite original 'get_request' method in Root class")
## ---

## v16, v17, v18, v19
if hasattr(http, "_dispatchers") and hasattr(http, "JsonRPCDispatcher") and hasattr(http, "Request"):

    class RequestAllowEmptyData(http.Request):
        def get_json_data(self):
            try:
                result = super().get_json_data()
                if isinstance(result, list):  # [{}, {}]
                    return {"__params": result}
                return result
            except ValueError:
                return {}

        # Dec 17, 2025: All APIs managed by Secure API are type "json"
        def _set_request_dispatcher(self, rule):
            try:
                is_secure = (
                    hasattr(rule, "endpoint")
                    and hasattr(rule.endpoint, "routing")
                    and rule.endpoint.routing.get("_is_secure_api", False)
                )
                if is_secure:
                    if version_info[0] >= 19:
                        self.dispatcher = http._dispatchers["jsonrpc"](self)
                    else:
                        self.dispatcher = http._dispatchers["json"](self)
                else:
                    super()._set_request_dispatcher(rule)
            except (AttributeError, KeyError):
                # Fallback for rules without routing metadata or missing dispatcher key
                super()._set_request_dispatcher(rule)

    # http._dispatchers['json'] = JsonRPCDispatcherAllowEmptyData
    http.Request = RequestAllowEmptyData
    _logger.info("Secure API: Overwrite original 'Request' in Root class")
    _logger.info(f"http.Request {http.Request}")
## ---
