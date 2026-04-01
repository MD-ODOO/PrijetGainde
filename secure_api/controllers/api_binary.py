# -*- coding: utf-8 -*-
from odoo import http
from odoo import SUPERUSER_ID
from odoo.http import request
import werkzeug
from werkzeug.exceptions import NotFound
from .request_handler import decode_now

from odoo.release import version_info  # (18, ...)

if version_info[0] >= 16:
    from odoo.addons.web.controllers.binary import Binary
else:
    from odoo.addons.web.controllers.main import Binary

extra_args = {"readonly": False} if version_info[0] >= 19 else {}

import logging

_logger = logging.getLogger(__name__)


class ApiBinary(http.Controller):
    def _get_security_user(self, api_record):
        if api_record.auth != "user":  # public api
            security_user_id = api_record.security_user_id.id if api_record.security_user_id else SUPERUSER_ID
        else:  # private api
            # Already set in request
            return None

        if api_record.auth == "user" and api_record.app_ids:  # => controller with 'public' auth => the user session is logged-in user or "base.public_user"
            if request.uid == request.env.ref("base.public_user").id:  # base.public_user
                access_token = request.httprequest.headers.get("Authorization")
                if access_token and access_token.startswith("Bearer "):
                    access_token = access_token[7:]
                    app = request.env["secure.api.app.token"].sudo().get_3rd_party_app(access_token=access_token)
                    if app:
                        app_scope_actions = app.get_scope_actions()
                        if api_record.api_action in ("search", "create", "read", "update", "delete", "rpc") and api_record.api_action in app_scope_actions:  # OK
                            security_user_id = app.security_user_id.id
                        elif api_record.api_action == "rest":
                            api_action = ""
                            # extract api_action
                            http_method = request.httprequest.method
                            if http_method == "GET":  # search or read
                                api_action = ("read", "search")  ##if target_id else "search"
                            elif http_method == "POST":  # create
                                api_action = "create"
                            elif http_method == "PATCH":  # update
                                api_action = "update"
                            elif http_method == "DELETE":  # delete
                                api_action = "delete"

                            # Check if api_action is allowed
                            if isinstance(api_action, (tuple, list, set)):
                                action_allowed = any(a in app_scope_actions for a in api_action)
                            else:
                                action_allowed = api_action in app_scope_actions

                            if action_allowed:  # OK
                                security_user_id = app.security_user_id.id
                            else:  # out of scope
                                raise werkzeug.exceptions.Unauthorized()
                        else:
                            raise werkzeug.exceptions.Unauthorized()
                    else:  # expired or not existed token
                        raise werkzeug.exceptions.Unauthorized()
            else:  # normal user
                # do nothing
                pass

        uid = security_user_id
        return uid

    def _check_security_and_process_id(self, api_id, model, id, field, **kw):
        """Common security check method for API endpoints

        Args:
            api_id: ID of the secure.api record
            model: Model name to check access
            id: Record ID (may be encoded)
            field: Field name to check access
            **kw: Additional keyword arguments

        Returns:
            tuple: (processed_id, kw) or NotFound exception if security checks fail
        """
        secure_api = request.env["secure.api"].sudo().browse(api_id)
        if not secure_api:
            return NotFound()

        # validate model
        rel_model_names = [x.model_id.model for x in secure_api.related_model_field_ids]
        if model not in secure_api.model_ids.mapped("model") and model not in rel_model_names:
            return NotFound()

        # validate id
        if secure_api.is_secure_record_id:
            hash_manager = secure_api.get_hash_manager()
            decoded_result = decode_now(hash_manager, id)
            if decoded_result == id:  # cannot decode smoothly
                raise NotFound()
            id = int(decoded_result)
        else:
            try:
                id = int(id)
            except:
                raise NotFound()

        # validate field
        rel_field_names = [api_rfield.field_ids.mapped("name") for api_rfield in secure_api.related_model_field_ids.filtered(lambda x: x.model_id.model == model)]
        rel_field_names = [item for sublist in rel_field_names for item in sublist]  # flatten list
        exposed_field_names = list(secure_api.field_ids.mapped("name"))

        if model in secure_api.model_ids.mapped("model"):
            if secure_api.allowed_field_type == "all":
                pass
            elif model in rel_model_names:
                check_field_names = rel_field_names + exposed_field_names
                if field not in check_field_names:
                    return NotFound()
                pass
            else:
                check_field_names = exposed_field_names
                if field not in check_field_names:
                    return NotFound()
                pass
            pass
        else:  # this means => model in rel_model_names
            check_field_names = rel_field_names
            if field not in check_field_names:
                return NotFound()
            pass

        kw["id"] = id  # re-assign correct type
        kw["model"] = model
        kw["field"] = field
        kw.pop("api_id", False)

        secured_uid = self._get_security_user(api_record=secure_api)
        if secured_uid:
            if version_info[0] >= 19:
                request.env = request.env(user=secured_uid)
            else:
                request.env.uid = secured_uid
        return kw

    @http.route(
        [
            "/api/image",
            "/api/image/<int:api_id>/<string:model>/<string:id>/<string:field>",
            "/api/image/<int:api_id>/<string:model>/<string:id>/<string:field>/<string:filename>",
            "/api/image/<int:api_id>/<string:model>/<string:id>/<string:field>/<int:width>x<int:height>",
            "/api/image/<int:api_id>/<string:model>/<string:id>/<string:field>/<int:width>x<int:height>/<string:filename>",
        ],
        type="http",
        auth="none",
        sitemap=False,
        cors="*",
        csrf=False,
        save_session=False,
        **extra_args
    )
    def api_image(self, api_id, model, id, field, **kw):
        result = self._check_security_and_process_id(api_id, model, id, field, **kw)
        if isinstance(result, NotFound):
            return result

        kw = result
        return Binary().content_image(**kw)

    @http.route(
        [
            "/api/content",
            "/api/content/<int:api_id>/<string:model>/<string:id>/<string:field>",
            "/api/content/<int:api_id>/<string:model>/<string:id>/<string:field>/<string:filename>",
        ],
        type="http",
        auth="none",
        sitemap=False,
        cors="*",
        csrf=False,
        save_session=False,
        **extra_args
    )
    def api_content(self, api_id, model, id, field, **kw):
        original_uid = request.env.uid
        result = self._check_security_and_process_id(api_id, model, id, field, **kw)
        if isinstance(result, NotFound):
            return result

        kw = result
        result = Binary().content_common(**kw)
        if request.env.uid != original_uid:
            if version_info[0] >= 19:
                request.env = request.env(user=original_uid)
            else:
                request.env.uid = original_uid
        return result
