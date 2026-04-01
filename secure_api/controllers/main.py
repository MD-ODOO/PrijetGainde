import odoo
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT
from odoo.http import request
from odoo import models, api, _, fields
import json
import secrets
from datetime import datetime, timezone, timedelta
from odoo.exceptions import AccessError
from odoo.release import version_info  # (18, ...)

import json
import logging

_logger = logging.getLogger(__name__)

# OAuth2 Request: https://github.com/requests/requests-oauthlib/blob/master/requests_oauthlib/oauth2_session.py#L202
# OAuth2 Response: https://github.com/oauthlib/oauthlib/blob/master/oauthlib/oauth2/rfc6749/clients/base.py#L376

main_args = {"type": "jsonrpc"} if version_info[0] >= 19 else {"type": "json"}
extra_args = {"readonly": False} if version_info[0] >= 18 else {}


class SecureAPI(odoo.http.Controller):
    @odoo.http.route("/api/jwt/token", type="http", auth="none", cors="*", csrf=False, methods=["POST"], **extra_args)
    def secure_api_jwt_token(self, **kw):
        """
        JWT Token Endpoint - Generates a stateless JWT access token.

        Request:
            POST /api/jwt/token
            Content-Type: application/x-www-form-urlencoded or application/json

            Parameters:
                - client_id: The client application's ID
                - client_secret: The client application's secret

        Response:
            {
                "access_token": "<jwt_token>",
                "token_type": "Bearer",
                "expires_in": <seconds>,
                "scope": "create read update delete search rpc"
            }
        """
        # Check if PyJWT is available by checking the model's JWT_AVAILABLE flag
        from odoo.addons.secure_api.models.secure_api_app import JWT_AVAILABLE
        if not JWT_AVAILABLE:
            status_param = {"status": 503} if version_info[0] >= 16 else {}
            res_response = request.make_response(
                json.dumps({
                    "error": "jwt_unavailable",
                    "error_description": "PyJWT library is not installed. Please install it with: pip install PyJWT"
                }),
                headers=[("Content-Type", "application/json")],
                **status_param
            )
            if not status_param:
                res_response.status_code = 503
            return res_response

        data = {}
        try:
            data = request.httprequest.args.to_dict()
        except:
            _logger.error("[/api/jwt/token] Cannot parse http request args (%s)" % str(request.httprequest.args))
            pass

        # Parse JSON data (for v14+)
        json_data = request.jsonrequest if hasattr(request, "jsonrequest") else {}
        json_data = json_data["__params"] if "__params" in json_data else json_data

        if isinstance(json_data, dict):
            data.update(json_data)
        else:
            data = json_data

        # https://werkzeug.palletsprojects.com/en/stable/wrappers/#werkzeug.wrappers.Request.get_data
        if not data:
            request_data = {}  # might be a dict or list
            if hasattr(request.httprequest, "data") and request.httprequest.data:
                try:
                    request_data = json.loads(request.httprequest.data)
                except json.JSONDecodeError:
                    _logger.error("Cannot parse http request data (%s)" % str(request.httprequest.data))
            data = request_data

        if kw:
            data.update(kw)

        client_id = data.get("client_id")
        client_secret = data.get("client_secret")

        _logger.warning(f"TODO: jwt token received data: {data}")

        if not client_id or not client_secret:
            status_param = {"status": 400} if version_info[0] >= 16 else {}
            res_response = request.make_response(
                json.dumps({"error": "invalid_request", "error_description": "Missing client_id or client_secret"}),
                headers=[("Content-Type", "application/json")],
                **status_param
            )
            if not status_param:
                res_response.status_code = 400
            return res_response

        app = request.env["secure.api.app"].sudo().search([
            ("client_id", "=", client_id),
            ("client_secret", "=", client_secret),
            ("state", "=", "enabled"),
            ("auth_type", "=", "jwt"),
        ], limit=1)

        if app:
            try:
                # Generate JWT Access Token
                access_token = app.generate_jwt_token()

                # Create response
                response_data = {
                    "access_token": access_token,
                    "token_type": "Bearer",
                    "expires_in": app.expire_minute * 60,
                    "scope": " ".join(app.get_scope_actions()),
                }

                return request.make_response(
                    json.dumps(response_data),
                    headers=[("Content-Type", "application/json"), ("Cache-Control", "no-store")]
                )
            except Exception as e:
                _logger.error("[/api/jwt/token] Error generating JWT: %s" % str(e))
                status_param = {"status": 500} if version_info[0] >= 16 else {}
                res_response = request.make_response(
                    json.dumps({"error": "server_error", "error_description": str(e)}),
                    headers=[("Content-Type", "application/json")],
                    **status_param
                )
                if not status_param:
                    res_response.status_code = 500
                return res_response
        else:
            raise AccessError(_("Unauthorized access"))

    @odoo.http.route("/api/oauth2/token", type="http", auth="none", cors="*", csrf=False, methods=["POST"], **extra_args)
    def secure_api_oauth2_token(self, **kw):
        data = {}
        try:
            data = request.httprequest.args.to_dict()
        except:
            _logger.error("[/api/oauth2/token] Cannot parse http request args (%s)" % str(request.httprequest.args))
            pass
        ## v14
        json_data = request.jsonrequest if hasattr(request, "jsonrequest") else {}
        json_data = json_data["__params"] if "__params" in json_data else json_data

        if isinstance(json_data, dict):
            data.update(json_data)
        else:  # [{}, {}]
            data = json_data

        # https://werkzeug.palletsprojects.com/en/stable/wrappers/#werkzeug.wrappers.Request.get_data
        if not data:
            request_data = {}  # might be a dict or list
            if hasattr(request.httprequest, "data") and request.httprequest.data:
                try:
                    request_data = json.loads(request.httprequest.data)
                except json.JSONDecodeError:
                    _logger.error("Cannot parse http request data (%s)" % str(request.httprequest.data))
            data = request_data

        if kw:
            data.update(kw)

        client_id, client_secret = data["client_id"], data["client_secret"]
        app = request.env["secure.api.app"].sudo().search([("client_id", "=", client_id), ("client_secret", "=", client_secret), ("state", "=", "enabled")])
        if app:
            # Generate Opaque Access Token
            access_token = secrets.token_urlsafe(64)
            is_expire = app.expire_minute > 0
            now_utc = datetime.now(timezone.utc).replace(tzinfo=None)  # Get current time in UTC
            expire_date = (now_utc + timedelta(minutes=app.expire_minute)) if is_expire else False
            record = (
                request.env["secure.api.app.token"]
                .sudo()
                .create(
                    {
                        "app_id": app.id,
                        "name": access_token,
                        "expire_date": expire_date,
                    }
                )
            )

            # Create OAuth2 compliant response
            response_data = {
                "access_token": record.name,
                "token_type": "Bearer",
                "scope": " ".join(
                    filter(
                        None,
                        [
                            "create" if app.scope_create else None,
                            "read" if app.scope_read else None,
                            "update" if app.scope_update else None,
                            "delete" if app.scope_delete else None,
                            "search" if app.scope_search else None,
                            "rpc" if app.scope_rpc else None,
                        ],
                    )
                ),
            }

            # Add expires_in if token expires
            if is_expire:
                response_data["expires_in"] = app.expire_minute * 60  # Convert minutes to seconds

            # Return JSON response with proper headers
            return request.make_response(json.dumps(response_data), headers=[("Content-Type", "application/json"), ("Cache-Control", "no-store")])
        else:
            raise AccessError(_("Unauthorized access"))

    @odoo.http.route("/secure/api/test/<id>", auth="none", cors="*", csrf=False, methods=["PATCH"], **main_args, **extra_args)
    def update_secure_api_test_result(self, id, **kw):
        data = kw if kw else {}
        if hasattr(request, "jsonrequest") and isinstance(request.jsonrequest, dict):
            data.update(request.jsonrequest)
        if hasattr(request, "params") and isinstance(request.params, dict):
            data.update(request.params)

        name = data.get("name", False)
        method = data.get("method", False)
        status = data.get("status", False)
        status_text = data.get("status_text", False)
        response = data.get("response", False)
        curl_command = data.get("curl_command", False)

        name = str(name) if name else name
        method = str(method) if method else method
        status = str(status) if status else status
        status_text = str(status_text) if status_text else status_text
        response = json.dumps(response, indent=4) if response else response
        curl_command = str(curl_command) if curl_command else curl_command

        w_data = {
            "name": name,
            "status": status,
            "status_text": status_text,
            "response": response,
            "curl_command": curl_command,
        }

        if method:
            w_data["live_test_method"] = method

        secure_api_test_record = request.env["secure.api.test"].sudo().browse(int(id))
        secure_api_test_record.secure_api_id.write({"live_test_response": response, "live_test_curl_command": curl_command})
        res = secure_api_test_record.write(w_data)
        return res

