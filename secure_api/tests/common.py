# -*- coding: utf-8 -*-
# from odoo.addons.mail.tests.common import mail_new_test_user
import random
import string
import json
import odoo
from odoo import SUPERUSER_ID
from odoo.tests import common, new_test_user
from odoo.tests import Form
from odoo.release import version_info  # (18, ...)

import logging

_logger = logging.getLogger(__name__)


def generate_random_string(length=10):
    """Generate a random string of specified length."""
    characters = string.ascii_letters + string.digits
    return "".join(random.choice(characters) for _ in range(length))


HOST = "127.0.0.1"
default_timeout = 10


# class TestSecureApiCommon(common.TransactionCase):
class TestSecureApiCommon(common.HttpCase):
    default_api_name_of_this_test = generate_random_string() + " Test Secure API"
    default_model = "base.model_res_partner"

    def setUp(self):
        super(TestSecureApiCommon, self).setUp()
        self.admin_u = "test_admin"
        self.admin_p = "test@admin!"
        self.admin_user = new_test_user(
            self.env,
            login=self.admin_u,
            password=self.admin_p,
            groups="base.group_system,base.group_partner_manager",
            name="Test Admin",
            email="test_admin@gmail.com",
        )
        self.normal_u = "test_normal"
        self.normal_p = "test@normal!"
        self.normal_user = new_test_user(
            self.env,
            login=self.normal_u,
            password=self.normal_p,
            groups="base.group_user",
            name="Test Normal",
            email="test_normal@gmail.com",
        )

    def tearDown(self):
        super(TestSecureApiCommon, self).tearDown()
        apis = self.env["secure.api"].search([("name", "=", self.default_api_name_of_this_test)])
        if apis:
            routes = apis.mapped("route")
            apis.btn_deactivate_api()
            _logger.info(f"Deactivated routes: {routes}")
        pass

    def assert_record_exists(self, record_data, expected_model=None):
        """Assert that a record exists in the database after API operation"""
        self.assertTrue(record_data)
        self.assertTrue("result" in record_data, 'Record data should contain a "result" key: %s' % str(record_data))
        result = record_data["result"][0] if isinstance(record_data["result"], list) and len(record_data["result"]) == 1 else record_data["result"]
        record_id = result["id"]
        model_name = expected_model or self.get_default_model_name()  # res.partner
        record = self.env[model_name].browse(record_id)
        self.assertTrue(record.exists(), "There should be a record (%d) on %s" % (record_id, model_name))
        return record

    def get_default_model_name(self):
        return self.default_model.split("model_")[1].replace("_", ".")  # res.partner

    def get_url(self, url):
        if version_info[0] >= 16:
            self.env.flush_all()
        else:
            self.env["base"].flush()
        if url.startswith("/"):
            url = "http://%s:%s%s" % (HOST, odoo.tools.config["http_port"], url)
        return url

    def send_request(
        self,
        method,
        url,
        is_return_raw_response=False,
        is_only_return_reponse=False,
        params=None,
        data=None,
        headers=None,
        cookies=None,
        files=None,
        auth=None,
        timeout=None,
        allow_redirects=True,
        proxies=None,
        hooks=None,
        stream=None,
        verify=None,
        cert=None,
        json_data=None,
    ):
        if headers is None:
            headers = {"Content-Type": "application/json"}
        elif "Content-Type" not in headers:
            headers["Content-Type"] = "application/json"
        assert method in ("GET", "POST", "PUT", "DELETE", "PATCH")
        url = self.get_url(url)
        # "opener" is a requests.Session() object
        # https://github.com/psf/requests/blob/main/src/requests/sessions.py#L500
        resp = self.opener.request(
            method,
            url,
            params=params,
            data=data,
            headers=headers,
            cookies=cookies,
            files=files,
            auth=auth,
            timeout=timeout if timeout else default_timeout,
            allow_redirects=allow_redirects,
            proxies=proxies,
            hooks=hooks,
            stream=stream,
            verify=verify,
            cert=cert,
            json=json_data,
        )
        if is_return_raw_response:
            if is_only_return_reponse:
                return resp
            return resp, json.loads(resp.content.decode("utf-8"))
        self.assertEqual(resp.status_code, 200)
        return json.loads(resp.content.decode("utf-8"))

    # def _check_api_endpoint_accessibility(self, route):
    #     # https://odoo.minhng.info/ => odoo/tests/common.py
    #     self.authenticate(None, None)
    #     # res = self.url_open(route, headers={'Content-Type': 'application/json'}, timeout=default_timeout)
    #     res = self.send_request(route, method='GET')
    #     self.assertEqual(res.status_code, 200)
    #     # result_dict = json.loads(res.content.decode('utf-8'))   # {'jsonrpc': '2.0', 'id': None, 'result': {'length': 37, 'records': [{'id': 14, 'name': 'Azure Interior', ...}]}}
    #     # _logger.info(f"XXX Result: {result_dict}")
    #     return res

    def create_api(self, is_published=True, **kwargs):
        SecureApiModel = self.env["secure.api"].with_user(self.admin_user)
        secure_api_form = Form(SecureApiModel)

        # computed fields
        random_route = "/test/" + generate_random_string(length=4)
        kwargs.update(
            {
                "name": self.default_api_name_of_this_test if "name" not in kwargs else kwargs["name"],
                "route": random_route if "route" not in kwargs else kwargs["route"],
            }
        )

        kwargs["security_user_id"] = (
            self.env["res.users"].sudo().browse(kwargs["security_user_id"]) if "security_user_id" in kwargs else self.env["res.users"].sudo().browse(SUPERUSER_ID)
        )

        for k, v in kwargs.items():
            if k in ["model_ids", "method_ids", "default_field_ids", "alias_field_ids"]:
                continue
            if secure_api_form._get_modifier(k, "invisible"):  # skip invisible fields
                continue
            # _logger.error(f"Set {k} to {v}")
            setattr(secure_api_form, k, v)

        model_list = kwargs.get(
            "model_ids",
            [
                self.default_model,
            ],
        )
        if not secure_api_form._get_modifier("model_ids", "invisible"):
            for model in model_list:
                secure_api_form.model_ids.add(self.env.ref(model, raise_if_not_found=True))
        else:
            secure_api_form.model_id_alias = self.env.ref(model_list[0], raise_if_not_found=True)

        if kwargs.get("api_action", "rest") == "rpc":
            for method in kwargs.get("method_ids", []):
                secure_api_form.method_ids.add(self.env.ref(method, raise_if_not_found=True) if isinstance(method, str) else self.env["secure.api.method"].browse(method))

        for api_default in kwargs.get("default_field_ids", []):
            with secure_api_form.default_field_ids.new() as line_default:
                model_record = self.env.ref(model_list[0], raise_if_not_found=True)
                line_default.model_id = model_record
                # _logger.error(f"fields: {self.env.ref(model_list[0], raise_if_not_found=True).field_id.mapped('name')}")
                # _logger.error(f'field_id: {api_default["field_id"]}')
                # ['__last_update', 'active', 'active_lang_count', 'bank_ids', 'barcode', 'category_id', 'child_ids', 'city', 'color', 'comment', 'commercial_company_name', 'commercial_partner_id', 'company_id', 'company_name', 'company_type', 'contact_address', 'country_id', 'create_date', 'create_uid', 'credit_limit', 'date', 'display_name', 'email', 'email_formatted', 'employee', 'function', 'id', 'image_1024', 'image_128', 'image_1920', 'image_256', 'image_512', 'industry_id', 'is_company', 'lang', 'mobile', 'name', 'parent_id', 'parent_name', 'partner_latitude', 'partner_longitude', 'partner_share', 'phone', 'ref', 'same_vat_partner_id', 'self', 'state_id', 'street', 'street2', 'title', 'type', 'tz', 'tz_offset', 'user_id', 'user_ids', 'vat', 'website', 'write_date', 'write_uid', 'zip']
                line_default.field_id = model_record.field_id.search(
                    [("name", "=", api_default["field_id"])], limit=1
                )  # model_record.field_id.filtered(lambda x: x.name == api_default["field_id"])[0]
                line_default.value = api_default["value"]

        for api_alias in kwargs.get("alias_field_ids", []):
            with secure_api_form.alias_field_ids.new() as line_alias:
                # Support both main model and related models via "model_ref" key
                model_ref = api_alias.get("model_ref", model_list[0])
                model_record = self.env.ref(model_ref, raise_if_not_found=True)
                line_alias.model_id = model_record
                line_alias.field_id = model_record.field_id.search(
                    [("name", "=", api_alias["field_id"])], limit=1
                )
                line_alias.alias = api_alias["alias"]

        secure_api = secure_api_form.save()

        secure_api.btn_publish_api() if is_published else None

        return secure_api
