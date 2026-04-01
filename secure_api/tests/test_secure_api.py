import requests
import base64
from odoo.tests import Form, tagged
from odoo.addons.secure_api.tests.common import TestSecureApiCommon, generate_random_string
from odoo.exceptions import UserError
from odoo.addons.secure_api.controllers.hashids import Hashids
from odoo.release import version_info  # (18, ...)

import logging

_logger = logging.getLogger(__name__)


@tagged("secure_api")
class TestSecureApi(TestSecureApiCommon):
    # ------------------------
    # | Functions of new API |
    # ------------------------
    # Field options:
    # - 'mode': ['prod', 'test']
    # - 'api_action': ['rest', 'search', 'create', 'read', 'update', 'delete', 'rpc']
    # - 'model_ids': test on one or multi models
    # - 'auth': ['none', 'user']
    # - 'cors': '*', '<domain name>'    => test manually
    # - 'method_ids ': GET, POST, PUT, DELETE, PATCH
    # - 'is_stats': [True, False]
    # - 'app_ids': one2many             => test @ test_secure_api_app.py
    # - 'is_secure_record_id': [True, False]
    # - 'security_user_id': many2one
    # - 'domain': <char>
    # - 'listing_limit': <int>
    # - 'is_allow_multi': [True, False]
    # - 'binary_field_return': ['url', 'base64']
    # - 'allowed_field_type': ['all', 'specific']
    # - 'related_model_field_ids': one2many
    #
    # Test function naming convention: test_api_mode_prod(), test_api_mode_test(), test_api_api_aciton_rest(), test_api_auth_none(), test_api_auth_user(), ...
    #

    # ----------------------------
    # | 'mode': ['prod', 'test'] |
    # ----------------------------
    def test_api_mode_prod(self):
        api = self.create_api(mode="prod")
        # create new partner via API
        new_partner = self.send_request("POST", api.route, json_data={"name": "Test Partner"})  # {...}
        self.assert_record_exists(record_data=new_partner)
        pass

    def test_api_mode_test(self):
        api = self.create_api(mode="test")
        # create new partner via API
        new_partner = self.send_request("POST", api.route, json_data={"name": "Test Partner"})  # {...}
        self.assertEqual(api.mode, "test")
        self.assertTrue(new_partner)
        record_id = new_partner["result"]["id"]
        record = self.env[self.get_default_model_name()].browse(record_id)
        self.assertFalse(record.exists(), "There should not be a record (%d) on %s" % (record_id, self.get_default_model_name()))

    # ----------------------------------------------------------------------------------
    # | 'api_action': ['rest', 'search', 'create', 'read', 'update', 'delete', 'rpc'] |
    # ----------------------------------------------------------------------------------
    def test_api_api_action_rest(self):
        api = self.create_api(api_action="rest")
        # C
        resp_create = self.send_request(method="POST", url=api.route, json_data={"name": "Test"})
        self.assert_record_exists(record_data=resp_create)
        record_id = resp_create["result"]["id"]
        # L
        resp_list = self.send_request(method="GET", url=api.route)
        self.assertTrue("result" in resp_list, "There should be a result key in the response")
        self.assertTrue(isinstance(resp_list["result"], dict))
        self.assertGreaterEqual(resp_list["result"]["length"], 1, "There should be at least one record")
        self.assertGreaterEqual(len(resp_list["result"]["records"]), 1, "There should be at least one record")
        # R
        resp_read = self.send_request(method="GET", url=api.route + "/" + str(record_id))
        self.assertEqual(resp_read["result"]["name"], "Test")
        # U
        resp_update = self.send_request(method="PATCH", url=api.route + "/" + str(record_id), json_data={"name": "Updated"})
        self.assertEqual(resp_update["result"]["name"], "Updated")
        # D
        resp_delete = self.send_request(method="DELETE", url=api.route + "/" + str(record_id))
        self.assertEqual(
            resp_delete["result"],
            [
                record_id,
            ],
        )
        record = self.env[self.get_default_model_name()].browse(record_id)
        self.assertFalse(record.exists(), "There should not be a record (%d) on %s" % (record_id, self.get_default_model_name()))
        pass

    def test_api_api_action_listing(self):
        api = self.create_api(api_action="search")
        # L
        resp_list = self.send_request(method="GET", url=api.route)
        self.assertTrue("result" in resp_list, "There should be a result key in the response")
        self.assertTrue(isinstance(resp_list["result"], dict))
        self.assertGreaterEqual(resp_list["result"]["length"], 1, "There should be at least one record")
        self.assertGreaterEqual(len(resp_list["result"]["records"]), 1, "There should be at least one record")
        pass

    def test_api_api_action_create(self):
        api = self.create_api(api_action="create")
        # C
        resp_create = self.send_request(method="POST", url=api.route, json_data={"name": "Test"})
        self.assert_record_exists(record_data=resp_create)
        pass

    def test_api_api_action_read(self):
        api = self.create_api(api_action="read", model_ids=["base.model_res_users"])
        # R
        resp_read = self.send_request(method="GET", url=api.route + "/" + str(self.admin_user.id))
        self.assertEqual(resp_read["result"]["id"], self.admin_user.id)
        self.assertEqual(resp_read["result"]["name"], self.admin_user.name)
        self.assertEqual(resp_read["result"]["login"], self.admin_user.login)
        self.assertEqual(resp_read["result"]["email"], self.admin_user.email)
        pass

    def test_api_api_action_update(self):
        api_create = self.create_api(api_action="create")
        api_update = self.create_api(api_action="update")
        # C
        target_record_name = "Test"
        resp_create = self.send_request(method="POST", url=api_create.route, json_data={"name": target_record_name})
        self.assert_record_exists(record_data=resp_create)
        target_record_id = resp_create["result"]["id"]
        # U
        name_before_adjust = target_record_name
        name_after_adjust = "Minh Nguyen"
        resp_update = self.send_request(method="PATCH", url=api_update.route + "/" + str(target_record_id), json_data={"name": name_after_adjust})
        self.assertEqual(resp_update["result"]["name"], name_after_adjust)
        record = self.env["res.partner"].browse(target_record_id)
        self.assertEqual(record.name, name_after_adjust)
        # # set back to original value -> not work?!
        # resp_update = self.send_request(method='PATCH', url=api_update.route + '/' + str(target_record_id), json_data={'name': name_before_adjust})
        # self.assertEqual(resp_update['result']['name'], name_before_adjust)
        # record = self.env['res.partner'].browse(target_record_id)
        # self.assertEqual(record.name, name_before_adjust)
        pass

    def test_api_api_action_delete(self):
        api_create = self.create_api(api_action="create")
        api_delete = self.create_api(api_action="delete")
        # C
        resp_create = self.send_request(method="POST", url=api_create.route, json_data={"name": "Test"})
        self.assert_record_exists(record_data=resp_create)
        record_id = resp_create["result"]["id"]
        # D
        resp_delete = self.send_request(method="DELETE", url=api_delete.route + "/" + str(record_id))
        self.assertEqual(
            resp_delete["result"],
            [
                record_id,
            ],
        )
        record = self.env[self.get_default_model_name()].browse(record_id)
        self.assertFalse(record.exists(), "There should not be a record (%d) on %s" % (record_id, self.get_default_model_name()))
        pass

    def test_api_api_action_rpc(self):
        api_create = self.create_api(api_action="rpc", rpc_method="create", method_ids=["secure_api.secure_api_method_post"])
        api_search = self.create_api(api_action="rpc", rpc_method="search", method_ids=["secure_api.secure_api_method_get"])
        # test on create api
        resp_create = self.send_request(method="POST", url=api_create.route, json_data={"vals_list": [{"name": "RPC Partner"}]})
        self.assertTrue("result" in resp_create and resp_create["result"], "Create API response is missing or invalid")
        self.assertTrue(
            self.env[self.get_default_model_name()].search([("name", "=", "RPC Partner")]).exists(),
            "Record should exist",
        )
        # test on search api
        if version_info[0] >= 16:
            resp_search = self.send_request(method="GET", url=api_search.route, json_data={"domain": [("name", "like", "RPC")]})
            self.assertTrue("result" in resp_search and resp_search["result"], "Search API response is missing or invalid")
        else:
            resp_search = self.send_request(method="GET", url=api_search.route, json_data={"args": [("name", "like", "RPC")]})
            self.assertTrue("result" in resp_search and resp_search["result"], "Search API response is missing or invalid")
        pass

    # --------------------------------------------
    # | 'model_ids': test on one or multi models |
    # --------------------------------------------

    def test_api_model_ids_multiple(self):
        api = self.create_api(api_action="rest", model_ids=["base.model_res_partner", "base.model_res_company"])
        for model in ["res.partner", "res.company"]:
            # C
            resp_create = self.send_request(method="POST", url=api.route + "/" + model, json_data={"name": "Test"})
            self.assert_record_exists(record_data=resp_create, expected_model=model)
            record_id = resp_create["result"]["id"]
            # L
            resp_list = self.send_request(method="GET", url=api.route + "/" + model)
            # self.assertGreaterEqual(len(resp_list['result']), 1, 'There should be at least one record')
            self.assertTrue("result" in resp_list, "There should be a result key in the response")
            self.assertTrue(isinstance(resp_list["result"], dict))
            self.assertGreaterEqual(resp_list["result"]["length"], 1, "There should be at least one record")
            self.assertGreaterEqual(len(resp_list["result"]["records"]), 1, "There should be at least one record")
            # R
            resp_read = self.send_request(method="GET", url=api.route + "/" + model + "/" + str(record_id))
            self.assertEqual(resp_read["result"]["name"], "Test")
            # U
            resp_update = self.send_request(method="PATCH", url=api.route + "/" + model + "/" + str(record_id), json_data={"name": "Updated"})
            self.assertEqual(resp_update["result"]["name"], "Updated")
            # D
            resp_delete = self.send_request(method="DELETE", url=api.route + "/" + model + "/" + str(record_id))
            self.assertEqual(
                resp_delete["result"],
                [
                    record_id,
                ],
            )
            record = self.env[model].browse(record_id)
            self.assertFalse(record.exists(), "There should not be a record (%d) on %s" % (record_id, model))
        pass

    # ----------------------------
    # | 'auth': ['none', 'user'] |
    # ----------------------------
    def test_api_auth_user(self):
        api = self.create_api(api_action="rest", auth="user")
        # test with unauthenticated user
        record_id = 1
        resp_create = self.send_request(method="POST", url=api.route, json_data={"name": "Test"})
        self.assertTrue("error" in resp_create)

        resp_list = self.send_request(method="GET", url=api.route)
        self.assertTrue("error" in resp_list)

        resp_read = self.send_request(method="GET", url=api.route + "/" + str(record_id))
        self.assertTrue("error" in resp_read)

        resp_update = self.send_request(method="PATCH", url=api.route + "/" + str(record_id), json_data={"name": "Updated"})
        self.assertTrue("error" in resp_update)

        resp_delete = self.send_request(method="DELETE", url=api.route + "/" + str(record_id))
        self.assertTrue("error" in resp_delete)

        # test with authenticated user
        self.authenticate(self.admin_u, self.admin_p)
        # C
        resp_create = self.send_request(method="POST", url=api.route, json_data={"name": "Test"})
        self.assert_record_exists(record_data=resp_create)
        record_id = resp_create["result"]["id"]
        # L
        resp_list = self.send_request(method="GET", url=api.route)
        # self.assertGreaterEqual(len(resp_list['result']), 1, 'There should be at least one record')
        self.assertTrue("result" in resp_list, "There should be a result key in the response")
        self.assertTrue(isinstance(resp_list["result"], dict))
        self.assertGreaterEqual(resp_list["result"]["length"], 1, "There should be at least one record")
        self.assertGreaterEqual(len(resp_list["result"]["records"]), 1, "There should be at least one record")
        # R
        resp_read = self.send_request(method="GET", url=api.route + "/" + str(record_id))
        self.assertEqual(resp_read["result"]["name"], "Test")
        # U
        resp_update = self.send_request(method="PATCH", url=api.route + "/" + str(record_id), json_data={"name": "Updated"})
        self.assertEqual(resp_update["result"]["name"], "Updated")
        # D
        resp_delete = self.send_request(method="DELETE", url=api.route + "/" + str(record_id))
        self.assertEqual(
            resp_delete["result"],
            [
                record_id,
            ],
        )
        record = self.env[self.get_default_model_name()].browse(record_id)
        self.assertFalse(record.exists(), "There should not be a record (%d) on %s" % (record_id, self.get_default_model_name()))
        pass

    # -----------------------------------------------
    # | 'method_ids': GET, POST, PUT, DELETE, PATCH |
    # -----------------------------------------------

    def test_api_method_ids_put(self):
        # create a custom api with put method
        api = self.create_api(api_action="rpc", rpc_method="create", method_ids=["secure_api.secure_api_method_put"])
        # test on search api
        for method in ("GET", "POST", "PUT", "DELETE", "PATCH"):
            resp, json_data = self.send_request(is_return_raw_response=True, method=method, url=api.route, json_data={"vals_list": [{"name": "RPC Partner"}]})
            if method == "PUT":
                self.assertEqual(resp.status_code, 200, "Search API response is missing or invalid")
                self.assertTrue("result" in json_data and json_data["result"], "Search API response is missing or invalid")
            else:  # should be failed
                self.assertTrue(resp.status_code == 404 or (resp.status_code == 200 and "error" in json_data))
        pass

    def test_api_method_ids_put_patch(self):
        # create a custom api with put method
        api = self.create_api(
            api_action="rpc",
            rpc_method="create",
            method_ids=["secure_api.secure_api_method_put", "secure_api.secure_api_method_patch"],
        )
        # test on create api
        for method in ("GET", "POST", "PUT", "DELETE", "PATCH"):
            partner_name = f"RPC Partner {hash(method)}"
            resp_create, json_data = self.send_request(
                is_return_raw_response=True,
                method=method,
                url=api.route,
                json_data={"vals_list": [{"name": partner_name}]},
            )
            if method in ("PUT", "PATCH"):
                self.assertEqual(resp_create.status_code, 200, "Search API response is missing or invalid")
                self.assertTrue("result" in json_data and json_data["result"], "Create API response is missing or invalid")
                self.assertTrue(
                    self.env[self.get_default_model_name()].search([("name", "=", partner_name)]).exists(),
                    "Record should exist",
                )
            else:  # should be failed
                self.assertTrue(resp_create.status_code == 404 or (resp_create.status_code == 200 and "error" in json_data))
        pass

    # -----------------------------
    # | 'is_stats': [True, False] |
    # -----------------------------

    def test_api_is_stats_true(self):
        # create a rest api
        api = self.create_api(api_action="rest", is_stats=True)
        self.assertNotEqual(api.secure_api_stats_id, False, "Secure API stats ID should not be False")
        self.assertTrue(api.secure_api_stats_id.exists(), "Secure API stats ID should exist")
        pass

    def test_api_is_stats_false(self):
        # create a rest api
        api = self.create_api(api_action="rest", is_stats=False)
        # "secure_api_stats_id" exists but not shown
        self.assertNotEqual(api.secure_api_stats_id, False, "Secure API stats ID should not be False")
        self.assertTrue(api.secure_api_stats_id.exists(), "Secure API stats ID should exist")
        pass

    # ----------------------------------------
    # | 'is_secure_record_id': [True, False] |
    # ----------------------------------------

    def test_api_is_secure_record_id_true(self):
        api = self.create_api(api_action="rest", is_secure_record_id=True)
        # C
        resp_create = self.send_request(method="POST", url=api.route, json_data={"name": "Test"})
        record_id = resp_create["result"]["id"]  # MYJnk
        self.assertFalse(isinstance(record_id, int))
        # L
        resp_list = self.send_request(method="GET", url=api.route)
        self.assertTrue("result" in resp_list, "There should be a result key in the response")
        self.assertTrue(isinstance(resp_list["result"], dict))
        self.assertGreaterEqual(resp_list["result"]["length"], 1, "There should be at least one record")
        self.assertGreaterEqual(len(resp_list["result"]["records"]), 1, "There should be at least one record")
        for rec_data in resp_list["result"]["records"]:
            self.assertFalse(isinstance(rec_data["id"], int))
        # R
        resp_read = self.send_request(method="GET", url=api.route + "/" + str(record_id))  # .../MYJnk
        self.assertEqual(resp_read["result"]["name"], "Test")
        self.assertEqual(resp_read["result"]["id"], record_id)
        # U
        resp_update = self.send_request(method="PATCH", url=api.route + "/" + str(record_id), json_data={"name": "Updated"})
        self.assertEqual(resp_update["result"]["name"], "Updated")
        self.assertEqual(resp_update["result"]["id"], record_id)
        # D
        resp_delete = self.send_request(method="DELETE", url=api.route + "/" + str(record_id))
        self.assertEqual(
            resp_delete["result"],
            [
                record_id,
            ],
        )
        pass

    def test_api_is_secure_record_id_true_rpc(self):
        api_create = self.create_api(
            api_action="rpc",
            rpc_method="create",
            is_secure_record_id=True,
            method_ids=["secure_api.secure_api_method_post"],
        )
        api_write = self.create_api(
            api_action="rpc",
            rpc_method="write",
            is_secure_record_id=True,
            method_ids=["secure_api.secure_api_method_put"],
        )

        # test on create api
        resp_create = self.send_request(method="POST", url=api_create.route, json_data={"vals_list": [{"name": "RPC Partner"}]})
        self.assertTrue("result" in resp_create and resp_create["result"], "Create API response is missing or invalid")
        record = self.env[self.get_default_model_name()].search([("name", "=", "RPC Partner")])
        self.assertTrue(record.exists(), "Record should exist")

        # test on write api
        record_id = record.id
        resp_write_to_be_failed, json_data = self.send_request(
            method="PUT",
            is_return_raw_response=True,
            url=api_write.route + "/" + str(record_id),
            json_data={"vals": {"name": "Updated Name"}},
        )
        self.assertTrue(resp_write_to_be_failed.status_code == 404 or (resp_write_to_be_failed.status_code == 200 and "error" in json_data))

        # call api with hashed id
        # Get default values from settings
        # ---
        salt = api_write.hashids_salt or self.env["ir.config_parameter"].sudo().get_param("secure_api.hashids_salt")
        min_length = api_write.hashids_min_length or int(self.env["ir.config_parameter"].sudo().get_param("secure_api.hashids_min_length", 5))

        hash_manager = Hashids(salt=salt, min_length=min_length)
        record_hashed_id = hash_manager.encode(record_id)
        resp_write_to_be_successful = self.send_request(
            method="PUT",
            url=api_write.route + "/" + str(record_hashed_id),
            json_data={"vals": {"name": "Updated Name"}},
        )
        self.assertTrue(
            "result" in resp_write_to_be_successful and resp_write_to_be_successful["result"] is True,
            "Write API response is missing or invalid",
        )

        # check on server
        target_record = self.env[self.get_default_model_name()].browse(record_id)
        self.assertEqual(target_record.name, "Updated Name")

    # --------------------------------
    # | 'security_user_id': many2one |
    # --------------------------------
    def test_api_security_user_id_auth_none(self):
        # create rest api with security_user_id=normal user
        api = self.create_api(api_action="rest", auth="none", security_user_id=self.normal_user.id)
        # the normal user don't have permission to create records
        resp_create, resp_data = self.send_request(method="POST", url=api.route, is_return_raw_response=True, json_data={"name": "New Record"})
        self.assertTrue(resp_create.status_code != 200 or (resp_create.status_code == 200 and "error" in resp_data))
        # the normal user allow to see other parnters
        resp_read, resp_data = self.send_request(method="GET", url=api.route + "/1", is_return_raw_response=True)
        self.assertTrue(resp_read.status_code == 200 and "error" not in resp_data)

    def test_api_security_user_id_auth_private(self):
        api = self.create_api(api_action="rest", auth="user", security_user_id=self.normal_user.id)
        # with private mode, the permission is granted to the current logged-in user
        self.authenticate(self.admin_u, self.admin_p)

        resp_create = self.send_request(method="POST", url=api.route, is_return_raw_response=False, json_data={"name": "New Record"})
        self.assert_record_exists(record_data=resp_create)

        resp_read, resp_data = self.send_request(method="GET", url=api.route + "/1", is_return_raw_response=True)
        self.assertTrue(resp_read.status_code == 200 and "result" in resp_data and resp_data["result"]["id"] == 1)

        updated_name = "Updated Name by Private Admin"
        normal_partner = self.normal_user.partner_id
        resp_update, resp_data = self.send_request(
            method="PATCH",
            url=api.route + "/" + str(normal_partner.id),
            is_return_raw_response=True,
            json_data={"name": updated_name},
        )
        self.assertTrue(resp_update.status_code == 200 and "error" not in resp_data)
        self.assertEqual(self.normal_user.partner_id.id, resp_data["result"]["id"])
        self.assertEqual(self.normal_user.partner_id.name, updated_name)
        pass

    # ------------------------------
    # | 'domain': [('id', '>', 0)] |
    # ------------------------------
    def test_api_domain_rest(self):
        api = self.create_api(api_action="rest", domain="[('id', '>', 2)]")
        # L
        resp_list = self.send_request(method="GET", url=api.route)
        self.assertTrue("result" in resp_list, "There should be a result key in the response")
        self.assertTrue(isinstance(resp_list["result"], dict))
        for partner in resp_list["result"]["records"]:
            self.assertTrue(partner["id"] > 2)
        pass

    def test_api_domain_search(self):
        api = self.create_api(api_action="search", domain="[('id', '>', 2)]")
        # L
        resp_list = self.send_request(method="GET", url=api.route)
        self.assertTrue("result" in resp_list, "There should be a result key in the response")
        self.assertTrue(isinstance(resp_list["result"], dict))
        for partner in resp_list["result"]["records"]:
            self.assertTrue(partner["id"] > 2)
        pass

    # --------------------------
    # | 'listing_limit': <int> |
    # --------------------------
    def test_api_listing_limit_rest(self):
        api = self.create_api(api_action="rest", listing_limit=2)
        # L
        resp_list = self.send_request(method="GET", url=api.route)
        self.assertTrue("result" in resp_list, "There should be a result key in the response")
        self.assertTrue(isinstance(resp_list["result"], dict))
        self.assertLessEqual(len(resp_list["result"]["records"]), 2)
        pass

    def test_api_listing_limit_search(self):
        api = self.create_api(api_action="search", listing_limit=2)
        # L
        resp_list = self.send_request(method="GET", url=api.route)
        self.assertTrue("result" in resp_list, "There should be a result key in the response")
        self.assertTrue(isinstance(resp_list["result"], dict))
        self.assertLessEqual(len(resp_list["result"]["records"]), 2)
        pass

    # -----------------------------------
    # | 'is_allow_multi': [True, False] |
    # -----------------------------------
    def test_api_is_allow_multi_create_read(self):
        api = self.create_api(api_action="rest", is_allow_multi=True)
        # C
        resp_create = self.send_request(method="POST", url=api.route, json_data=[{"name": "Peter"}, {"name": "Mitchell"}])
        self.assertTrue("result" in resp_create, "There should be a result key in the response")
        self.assertTrue(isinstance(resp_create["result"], list))
        self.assertEqual(len(resp_create["result"]), 2)
        self.assertTrue(
            resp_create["result"][0]["id"] > 0 and resp_create["result"][1]["id"] > 0,
            "There should be two records created",
        )
        # R
        record_ids = [record["id"] for record in resp_create["result"]]  # [1, 2]
        resp_read = self.send_request(method="GET", url=api.route + f'/bulk?ids={",".join([str(record_id) for record_id in record_ids])}')
        self.assertTrue(isinstance(resp_read["result"], list))
        self.assertEqual(len(resp_read["result"]), 2)
        self.assertEqual([record["id"] for record in resp_read["result"]], record_ids)
        pass

    def test_api_is_allow_multi_create_update(self):
        api = self.create_api(api_action="rest", is_allow_multi=True)
        # C
        resp_create = self.send_request(method="POST", url=api.route, json_data=[{"name": "Peter"}, {"name": "Mitchell"}])
        self.assertTrue("result" in resp_create, "There should be a result key in the response")
        self.assertTrue(isinstance(resp_create["result"], list))
        self.assertEqual(len(resp_create["result"]), 2)
        self.assertTrue(
            resp_create["result"][0]["id"] > 0 and resp_create["result"][1]["id"] > 0,
            "There should be two records created",
        )
        # U
        record_ids = [record["id"] for record in resp_create["result"]]  # [1, 2]
        resp_update = self.send_request(
            method="PATCH",
            url=api.route,
            json_data=[{"id": record_ids[0], "name": "Updated"}, {"id": record_ids[1], "name": "Updated"}],
        )
        self.assertEqual(resp_update["result"][0]["name"], "Updated")
        self.assertEqual(resp_update["result"][1]["name"], "Updated")
        resp_update = self.send_request(method="PATCH", url=api.route, json_data={"ids": record_ids, "name": "Updated 2"})
        self.assertEqual(resp_update["result"][0]["name"], "Updated 2")
        self.assertEqual(resp_update["result"][1]["name"], "Updated 2")
        pass

    def test_api_is_allow_multi_create_delete(self):
        api = self.create_api(api_action="rest", is_allow_multi=True)
        # C
        resp_create = self.send_request(method="POST", url=api.route, json_data=[{"name": "Peter"}, {"name": "Mitchell"}])
        self.assertTrue("result" in resp_create, "There should be a result key in the response")
        self.assertTrue(isinstance(resp_create["result"], list))
        self.assertEqual(len(resp_create["result"]), 2)
        self.assertTrue(
            resp_create["result"][0]["id"] > 0 and resp_create["result"][1]["id"] > 0,
            "There should be two records created",
        )
        # D (1)
        record_ids = [record["id"] for record in resp_create["result"]]  # [1, 2]
        resp_delete = self.send_request(method="DELETE", url=api.route, json_data=record_ids)
        self.assertEqual(resp_delete["result"], record_ids)
        record = self.env[self.get_default_model_name()].browse(record_ids)
        self.assertFalse(record.exists(), "There should not be records (%s) on %s" % (str(record_ids), self.get_default_model_name()))
        # C
        resp_create = self.send_request(method="POST", url=api.route, json_data=[{"name": "Peter II"}, {"name": "Mitchell II"}])
        self.assertTrue("result" in resp_create, "There should be a result key in the response")
        self.assertTrue(isinstance(resp_create["result"], list))
        self.assertEqual(len(resp_create["result"]), 2)
        self.assertTrue(
            resp_create["result"][0]["id"] > 0 and resp_create["result"][1]["id"] > 0,
            "There should be two records created",
        )
        # D (2)
        record_ids = [record["id"] for record in resp_create["result"]]  # [1, 2]
        resp_delete = self.send_request(method="DELETE", url=api.route, json_data={"ids": record_ids})
        self.assertEqual(resp_delete["result"], record_ids)
        record = self.env[self.get_default_model_name()].browse(record_ids)
        self.assertFalse(record.exists(), "There should not be records (%s) on %s" % (str(record_ids), self.get_default_model_name()))
        pass

    def test_api_is_allow_multi_with_is_secure_record_id_read_update_delete(self):
        api = self.create_api(api_action="rest", is_allow_multi=True, is_secure_record_id=True)
        # C
        resp_create = self.send_request(method="POST", url=api.route, json_data=[{"name": "Peter"}, {"name": "Mitchell"}])
        self.assertTrue("result" in resp_create, "There should be a result key in the response")
        self.assertTrue(isinstance(resp_create["result"], list))
        self.assertEqual(len(resp_create["result"]), 2)
        self.assertTrue(
            isinstance(resp_create["result"][0]["id"], str) and isinstance(resp_create["result"][1]["id"], str),
            'All items in "record_ids" should be string',
        )
        record_ids = [record["id"] for record in resp_create["result"]]  # ["zKgmG", "8aDOG"]
        self.assertFalse(any(isinstance(item, int) for item in record_ids), 'All items in "record_ids" should not be integer')
        # R
        resp_read = self.send_request(method="GET", url=api.route + f'/bulk?ids={",".join(record_ids)}')
        self.assertTrue(isinstance(resp_read["result"], list))
        self.assertEqual(len(resp_read["result"]), 2)
        self.assertEqual([record["id"] for record in resp_read["result"]], record_ids)
        # U
        resp_update = self.send_request(
            method="PATCH",
            url=api.route,
            json_data=[{"id": record_ids[0], "name": "Updated"}, {"id": record_ids[1], "name": "Updated"}],
        )
        self.assertEqual(resp_update["result"][0]["name"], "Updated")
        self.assertEqual(resp_update["result"][1]["name"], "Updated")
        resp_update = self.send_request(method="PATCH", url=api.route, json_data={"ids": record_ids, "name": "Updated 2"})
        self.assertEqual(resp_update["result"][0]["name"], "Updated 2")
        self.assertEqual(resp_update["result"][1]["name"], "Updated 2")
        # D (1)
        resp_delete = self.send_request(method="DELETE", url=api.route, json_data=record_ids)
        self.assertEqual(resp_delete["result"], record_ids)
        # C
        resp_create = self.send_request(method="POST", url=api.route, json_data=[{"name": "Peter II"}, {"name": "Mitchell II"}])
        self.assertTrue("result" in resp_create, "There should be a result key in the response")
        self.assertTrue(isinstance(resp_create["result"], list))
        self.assertEqual(len(resp_create["result"]), 2)
        self.assertTrue(
            isinstance(resp_create["result"][0]["id"], str) and isinstance(resp_create["result"][1]["id"], str),
            'All items in "record_ids" should be string',
        )
        # D (2)
        record_ids = [record["id"] for record in resp_create["result"]]  # ["WG6ay", "6yRL8"]
        resp_delete = self.send_request(method="DELETE", url=api.route, json_data={"ids": record_ids})
        self.assertEqual(resp_delete["result"], record_ids)
        pass

    # --------------------------------------------
    # | 'binary_field_return': ['url', 'base64'] |
    # --------------------------------------------
    def test_api_binary_field_return_url(self):
        # Create a test record with binary data
        test_binary_data = b"iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
        test_partner = self.env["res.partner"].create(
            {
                "name": "Binary Test Partner URL",
                "image_1920": test_binary_data,
            }
        )

        # Create API with binary_field_return = 'url'
        api = self.create_api(api_action="rest", binary_field_return="url")

        # Test reading the record
        resp_read = self.send_request(method="GET", url=api.route + "/" + str(test_partner.id))

        # Verify the response contains a URL for the binary field
        self.assertTrue("result" in resp_read, "Response should contain result")
        self.assertTrue("image_1920" in resp_read["result"], "Response should contain image_1920 field")
        image_value = resp_read["result"]["image_1920"]

        # Check that the image field contains a URL
        self.assertTrue(isinstance(image_value, str), "Binary field should be returned as string")
        self.assertTrue(
            image_value.startswith("/") and "res.partner" in image_value and "image_1920" in image_value,
            f"Binary field should be returned as URL, got: {image_value}",
        )

        # Test that the URL format is correct
        media_prefix = "/web/image" if api.auth == "user" else "/api/image"
        expected_url_pattern = f"{media_prefix}/{api.id}/res.partner/{test_partner.id}/image_1920"
        self.assertEqual(image_value, expected_url_pattern, "Binary field URL format is incorrect")

        # Verify the binary content by fetching the image from the URL
        url = self.get_url(image_value)

        image_response = self.opener.request("GET", url, timeout=5) if version_info[0] >= 19 else requests.get(url, timeout=5)

        # Convert the binary response to base64
        response_base64 = base64.b64encode(image_response.content).decode("ascii")
        self.assertEqual(
            response_base64,
            test_binary_data.decode("ascii"),
            "Downloaded image content does not match original binary data",
        )

        # Clean up
        test_partner.unlink()

    def test_api_binary_field_return_url_image_retrieval(self):
        """Test that the binary field URL can be used to retrieve the actual image"""
        # Create a test record with binary data (small 1x1 transparent PNG)
        test_binary_data = b"iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
        test_partner = self.env["res.partner"].create(
            {
                "name": "Binary Test Partner URL Image Retrieval",
                "image_1920": test_binary_data,
            }
        )

        # Create API with binary_field_return = 'url' and no authentication
        api = self.create_api(api_action="rest", binary_field_return="url", auth="none", is_secure_record_id=False)

        # Test reading the record
        resp_read = self.send_request(method="GET", url=api.route + "/" + str(test_partner.id))

        # Verify the response contains a URL for the binary field
        self.assertTrue("result" in resp_read, "Response should contain result")
        self.assertTrue("image_1920" in resp_read["result"], "Response should contain image_1920 field")
        image_url = resp_read["result"]["image_1920"]

        # Verify URL format
        self.assertTrue(image_url.startswith("/api/image"), "Image URL should start with /api/image")
        self.assertTrue(str(api.id) in image_url, f"API ID {api.id} should be in the URL: {image_url}")
        self.assertTrue(str(test_partner.id) in image_url, f"Partner ID {test_partner.id} should be in the URL: {image_url}")
        self.assertTrue("image_1920" in image_url, "Field name should be in the URL")

        # Now request the image using the URL from the response
        url = self.get_url(image_url)

        image_response = self.opener.request("GET", url, timeout=5) if version_info[0] >= 19 else requests.get(url, timeout=5)

        # Convert the binary response to base64
        response_base64 = base64.b64encode(image_response.content).decode("ascii")
        self.assertEqual(
            response_base64,
            test_binary_data.decode("ascii"),
            "Downloaded image content does not match original binary data (1)",
        )

        # Verify the image response
        self.assertEqual(
            image_response.status_code,
            200,
            f"Image URL should return 200 status code, got {image_response.status_code}",
        )
        self.assertTrue("Content-Type" in image_response.headers, "Response should have Content-Type header")
        content_type = image_response.headers.get("Content-Type", "")
        self.assertTrue(content_type.startswith("image/"), f"Content-Type should be an image type, got: {content_type}")

        # Test with secure record ID
        # try:
        # Create a new API with secure record ID
        api_secure = self.create_api(api_action="rest", binary_field_return="url", auth="none", is_secure_record_id=True)

        hash_manager = api_secure.get_hash_manager()

        # Test reading the record with secure API
        resp_read_secure = self.send_request(method="GET", url=api_secure.route + "/" + str(hash_manager.encode(test_partner.id)))

        # Get the image URL with encoded ID
        image_url_secure = resp_read_secure["result"]["image_1920"]

        # Verify URL format contains encoded ID
        self.assertTrue("/api/image" in image_url_secure, "Image URL should contain /api/image")
        self.assertNotEqual(image_url, image_url_secure, "Secure URL should be different from non-secure URL")

        # Request the image using the secure URL
        url_secure = self.get_url(image_url_secure)
        secure_image_response = self.opener.request("GET", url_secure, timeout=5) if version_info[0] >= 19 else requests.get(url_secure, timeout=5)
        # Convert the binary response to base64
        response_base64 = base64.b64encode(secure_image_response.content).decode("ascii")
        self.assertEqual(
            response_base64,
            test_binary_data.decode("ascii"),
            "Downloaded image content does not match original binary data (2)",
        )

        # Verify the secure image response
        self.assertEqual(
            secure_image_response.status_code,
            200,
            f"Secure image URL should return 200 status code, got {secure_image_response.status_code}",
        )
        self.assertTrue("Content-Type" in secure_image_response.headers, "Response should have Content-Type header")
        secure_content_type = secure_image_response.headers.get("Content-Type", "")
        self.assertTrue(
            secure_content_type.startswith("image/"),
            f"Content-Type should be an image type, got: {secure_content_type}",
        )
        # except Exception as e:
        #     # Log the error but don't fail the test
        #     # This is to ensure the basic functionality works even if secure ID has issues
        #     _logger.warning(f"Secure URL test failed: {str(e)}")

        # Clean up
        test_partner.unlink()

    def test_api_binary_field_return_base64(self):
        # Create a test record with binary data
        test_binary_data = b"iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
        test_partner = self.env["res.partner"].create(
            {
                "name": "Binary Test Partner Base64",
                "image_1920": test_binary_data,
            }
        )

        # Create API with binary_field_return = 'base64'
        api = self.create_api(api_action="rest", binary_field_return="base64")

        # Test reading the record
        resp_read = self.send_request(method="GET", url=api.route + "/" + str(test_partner.id))

        # Verify the response contains base64 data for the binary field
        self.assertTrue("result" in resp_read, "Response should contain result")
        self.assertTrue("image_1920" in resp_read["result"], "Response should contain image_1920 field")
        image_value = resp_read["result"]["image_1920"]

        # Check that the image field contains base64 data
        self.assertTrue(isinstance(image_value, str), "Binary field should be returned as string")

        # For base64 mode, the binary field should be returned as is (base64 encoded)
        # The value should not be a URL
        self.assertFalse(image_value.startswith("/web/"), "Binary field should not be returned as URL")

        # The value should not be empty
        self.assertTrue(len(image_value) > 0, "Binary field should not be empty")

        # Verify the base64 content matches the original binary data
        self.assertEqual(image_value, test_binary_data.decode("ascii"), "Decoded base64 content does not match original binary data")

        # Clean up
        test_partner.unlink()

    # ---------------------------------------------
    # | 'allowed_field_type': ['all', 'specific'] |
    # ---------------------------------------------
    def test_api_allowed_field_type_all(self):
        # Create API with allowed_field_type = 'all'
        api = self.create_api(api_action="rest", allowed_field_type="all")

        # Create a test partner with various fields populated
        test_partner = self.env["res.partner"].create(
            {
                "name": "Field Type Test Partner - All",
                "email": "all_fields@example.com",
                "phone": "+1234567890",
                "comment": "This is a test comment",
            }
        )

        # Test reading the record
        resp_read = self.send_request(method="GET", url=api.route + "/" + str(test_partner.id))

        # Verify the response contains all expected fields
        self.assertTrue("result" in resp_read, "Response should contain result")
        result = resp_read["result"]

        # Check that all standard fields are present
        self.assertEqual(result["name"], "Field Type Test Partner - All")
        self.assertEqual(result["email"], "all_fields@example.com")
        self.assertEqual(result["phone"], "+1234567890")
        self.assertIn("This is a test comment", result["comment"])

        # Check that other standard fields are also present (even if not explicitly set)
        self.assertTrue("id" in result)
        self.assertTrue("create_date" in result)
        self.assertTrue("write_date" in result)

        # Clean up
        test_partner.unlink()

    def test_api_allowed_field_type_specific(self):
        # Get some specific fields from res.partner model
        partner_model = self.env["ir.model"].search([("model", "=", "res.partner")], limit=1)
        name_field = self.env["ir.model.fields"].search([("model_id", "=", partner_model.id), ("name", "=", "name")], limit=1)
        email_field = self.env["ir.model.fields"].search([("model_id", "=", partner_model.id), ("name", "=", "email")], limit=1)

        # Create API with allowed_field_type = 'specific' and only name and email fields
        api_form = Form(self.env["secure.api"].with_user(self.admin_user))
        api_form.name = self.default_api_name_of_this_test
        api_form.route = "/test/" + generate_random_string(length=4)
        api_form.api_action = "rest"
        api_form.allowed_field_type = "specific"
        api_form.model_ids.add(partner_model)
        api = api_form.save()

        # Add specific fields
        api.write({"field_ids": [(6, 0, [name_field.id, email_field.id])]})  # Use write with 6, 0 command to replace all fields
        api.btn_publish_api()

        # Create a test partner with various fields populated
        test_partner = self.env["res.partner"].create(
            {
                "name": "Field Type Test Partner - Specific",
                "email": "specific_fields@example.com",
                "phone": "+1234567890",  # This field should not be returned
                "comment": "This is a test comment",  # This field should not be returned
            }
        )

        # Test reading the record
        resp_read = self.send_request(method="GET", url=api.route + "/" + str(test_partner.id))

        # Verify the response contains only the specified fields
        self.assertTrue("result" in resp_read, "Response should contain result")
        result = resp_read["result"]

        # Check that only the specified fields are present
        self.assertEqual(result["name"], "Field Type Test Partner - Specific")
        self.assertEqual(result["email"], "specific_fields@example.com")
        self.assertTrue("id" in result, "ID field should always be present")

        # Check that other fields are not present
        self.assertFalse("phone" in result, "Phone field should not be present")
        self.assertFalse("comment" in result, "Comment field should not be present")

        # Clean up
        test_partner.unlink()

    # ---------------------------------------
    # | 'related_model_field_ids': one2many |
    # ---------------------------------------
    def test_api_related_model_field_many2one(self):
        # Test that many2one fields are properly expanded with related model data

        # Create a test company
        test_company = self.env["res.company"].create(
            {
                "name": "Test Related Company",
                "email": "related_test@example.com",
                "phone": "+1234567890",
            }
        )

        # Create a test partner linked to the company
        test_partner = self.env["res.partner"].create(
            {
                "name": "Related Field Test Partner",
                "email": "related_fields@example.com",
                "company_id": test_company.id,
            }
        )

        # Get the models and fields needed for the API configuration
        partner_model = self.env["ir.model"].search([("model", "=", "res.partner")], limit=1)
        company_model = self.env["ir.model"].search([("model", "=", "res.company")], limit=1)
        company_name_field = self.env["ir.model.fields"].search([("model_id", "=", company_model.id), ("name", "=", "name")], limit=1)
        company_email_field = self.env["ir.model.fields"].search([("model_id", "=", company_model.id), ("name", "=", "email")], limit=1)
        company_phone_field = self.env["ir.model.fields"].search([("model_id", "=", company_model.id), ("name", "=", "phone")], limit=1)

        # Create API with related_model_field_ids for company
        api = self.create_api(api_action="rest")

        # Create a related field configuration for the company model
        self.env["secure.api.rfield"].create(
            {
                "model_id": company_model.id,
                "field_ids": [(6, 0, [company_name_field.id, company_email_field.id, company_phone_field.id])],
                "secure_api_id": api.id,
            }
        )

        # Test reading the partner record
        resp_read = self.send_request(method="GET", url=api.route + "/" + str(test_partner.id))

        # Verify the response contains expanded company data
        self.assertTrue("result" in resp_read, "Response should contain result")
        result = resp_read["result"]

        # Check that the company_id field is expanded with company data
        self.assertTrue("company_id" in result, "Response should contain company_id field")
        self.assertTrue(isinstance(result["company_id"], list), "company_id should be a list")
        self.assertEqual(len(result["company_id"]), 2, "company_id should have id and data")
        self.assertEqual(result["company_id"][0], test_company.id, "First element should be the company ID")

        # Check that the company data contains the expected fields
        company_data = result["company_id"][1]
        self.assertEqual(company_data["name"], "Test Related Company")
        self.assertEqual(company_data["email"], "related_test@example.com")
        self.assertEqual(company_data["phone"], "+1234567890")

        # Clean up
        test_partner.unlink()
        test_company.unlink()

    def test_api_related_model_field_one2many(self):
        # Test that one2many fields are properly expanded with related model data

        # Create a test partner as parent
        parent_partner = self.env["res.partner"].create(
            {
                "name": "Parent Partner",
                "email": "parent@example.com",
            }
        )

        # Create child partners linked to the parent
        child1 = self.env["res.partner"].create(
            {
                "name": "Child Partner 1",
                "email": "child1@example.com",
                "parent_id": parent_partner.id,
            }
        )

        child2 = self.env["res.partner"].create(
            {
                "name": "Child Partner 2",
                "email": "child2@example.com",
                "parent_id": parent_partner.id,
            }
        )

        # Get the models and fields needed for the API configuration
        partner_model = self.env["ir.model"].search([("model", "=", "res.partner")], limit=1)
        partner_name_field = self.env["ir.model.fields"].search([("model_id", "=", partner_model.id), ("name", "=", "name")], limit=1)
        partner_email_field = self.env["ir.model.fields"].search([("model_id", "=", partner_model.id), ("name", "=", "email")], limit=1)

        # Create API with related_model_field_ids for child partners
        api = self.create_api(api_action="rest")

        # Create a related field configuration for the partner model (for child_ids)
        self.env["secure.api.rfield"].create(
            {
                "model_id": partner_model.id,
                "field_ids": [(6, 0, [partner_name_field.id, partner_email_field.id])],
                "secure_api_id": api.id,
            }
        )

        # Test reading the parent partner record
        resp_read = self.send_request(method="GET", url=api.route + "/" + str(parent_partner.id))

        # Verify the response contains expanded child_ids data
        self.assertTrue("result" in resp_read, "Response should contain result")
        result = resp_read["result"]

        # Check that the child_ids field is expanded with child data
        self.assertTrue("child_ids" in result, "Response should contain child_ids field")
        self.assertTrue(isinstance(result["child_ids"], list), "child_ids should be a list")
        self.assertEqual(len(result["child_ids"]), 2, "There should be 2 child records")

        # Check that each child record contains the expected fields
        child_data = {child["name"]: child for child in result["child_ids"]}

        self.assertTrue("Child Partner 1" in child_data, "Child 1 should be in the response")
        self.assertEqual(child_data["Child Partner 1"]["email"], "child1@example.com")

        self.assertTrue("Child Partner 2" in child_data, "Child 2 should be in the response")
        self.assertEqual(child_data["Child Partner 2"]["email"], "child2@example.com")

        # Clean up
        child1.unlink()
        child2.unlink()
        parent_partner.unlink()

    def test_api_related_model_field_many2many(self):
        # Test that many2many fields are properly expanded with related model data

        # Create test categories
        category1 = self.env["res.partner.category"].create(
            {
                "name": "Test Category 1",
            }
        )

        category2 = self.env["res.partner.category"].create(
            {
                "name": "Test Category 2",
            }
        )

        # Create a test partner with categories
        test_partner = self.env["res.partner"].create(
            {
                "name": "M2M Related Field Test Partner",
                "email": "m2m_related_fields@example.com",
                "category_id": [(6, 0, [category1.id, category2.id])],
            }
        )

        # Get the models and fields needed for the API configuration
        partner_model = self.env["ir.model"].search([("model", "=", "res.partner")], limit=1)
        category_model = self.env["ir.model"].search([("model", "=", "res.partner.category")], limit=1)
        category_name_field = self.env["ir.model.fields"].search([("model_id", "=", category_model.id), ("name", "=", "name")], limit=1)

        # Create API with related_model_field_ids for categories
        api = self.create_api(api_action="rest")

        # Create a related field configuration for the category model
        self.env["secure.api.rfield"].create(
            {
                "model_id": category_model.id,
                "field_ids": [(6, 0, [category_name_field.id])],
                "secure_api_id": api.id,
            }
        )

        # Test reading the partner record
        resp_read = self.send_request(method="GET", url=api.route + "/" + str(test_partner.id))

        # Verify the response contains expanded category data
        self.assertTrue("result" in resp_read, "Response should contain result")
        result = resp_read["result"]

        # Check that the category_id field is expanded with category data
        self.assertTrue("category_id" in result, "Response should contain category_id field")
        self.assertTrue(isinstance(result["category_id"], list), "category_id should be a list")
        self.assertEqual(len(result["category_id"]), 2, "There should be 2 category records")

        # Check that each category record contains the expected fields
        category_names = [cat["name"] for cat in result["category_id"]]
        self.assertIn("Test Category 1", category_names, "Category 1 should be in the response")
        self.assertIn("Test Category 2", category_names, "Category 2 should be in the response")

        # Clean up
        test_partner.unlink()
        category1.unlink()
        category2.unlink()

    # --------------
    # | Delete API |
    # --------------
    def test_delete_draft_api(self):
        api = self.create_api(is_published=False)
        res = api.unlink()
        self.assertEqual(res, True)

    def test_delete_deactivated_api(self):
        api = self.create_api()
        api.btn_deactivate_api()
        res = api.unlink()
        self.assertEqual(res, True)

    def test_delete_published_api(self):
        api = self.create_api()
        with self.assertRaises(UserError), self.cr.savepoint():
            api.unlink()

    # ------------------------------
    # | Test Deactivated Endpoints |
    # ------------------------------
    def test_deactivated_all_endpoints(self):
        # Create and publish a REST API
        api = self.create_api(api_action="rest")
        self.assertEqual(api.state, "published")

        # Test that the API is accessible
        resp_create = self.send_request(method="POST", url=api.route, json_data={"name": "Test Partner"})
        self.assert_record_exists(record_data=resp_create)
        record_id = resp_create["result"]["id"]

        # Deactivate the API
        api.btn_deactivate_api()
        self.assertEqual(api.state, "deactivated")

        # Test that all endpoints are no longer accessible (should return 404 Not Found)
        # Test CREATE endpoint
        resp_create, json_data = self.send_request(method="POST", url=api.route, json_data={"name": "Another Test Partner"}, is_return_raw_response=True)
        self.assertTrue(resp_create.status_code == 404 or (resp_create.status_code == 200 and "error" in json_data))

        # Test LIST endpoint
        resp_list, json_data = self.send_request(method="GET", url=api.route, is_return_raw_response=True)
        self.assertTrue(resp_list.status_code == 404 or (resp_list.status_code == 200 and "error" in json_data))

        # Test READ endpoint
        resp_read, json_data = self.send_request(method="GET", url=api.route + "/" + str(record_id), is_return_raw_response=True)
        self.assertTrue(resp_read.status_code == 404 or (resp_read.status_code == 200 and "error" in json_data))

        # Test UPDATE endpoint
        resp_update, json_data = self.send_request(
            method="PATCH",
            url=api.route + "/" + str(record_id),
            json_data={"name": "Updated Name"},
            is_return_raw_response=True,
        )
        self.assertTrue(resp_update.status_code == 404 or (resp_update.status_code == 200 and "error" in json_data))

        # Test DELETE endpoint
        resp_delete, json_data = self.send_request(method="DELETE", url=api.route + "/" + str(record_id), is_return_raw_response=True)
        self.assertTrue(resp_delete.status_code == 404 or (resp_delete.status_code == 200 and "error" in json_data))

        # Reactivate the API
        api.btn_publish_api()
        self.assertEqual(api.state, "published")

        # Test that the API is accessible again
        resp_list = self.send_request(method="GET", url=api.route)
        self.assertTrue("result" in resp_list, "API should be accessible after reactivation")

    def test_deactivated_some_endpoints(self):
        # Create and publish a REST API
        api = self.create_api(api_action="rest")
        self.assertEqual(api.state, "published")

        # Test that the API is accessible
        resp_create = self.send_request(method="POST", url=api.route, json_data={"name": "Test Partner"})
        self.assert_record_exists(record_data=resp_create)
        record_id = resp_create["result"]["id"]

        # Deactivate the endpoints
        target_endpoints = api.endpoint_ids.filtered(lambda x: x.api_action in ["create", "update", "delete"])
        target_endpoints.action_deactivate()

        # Test that all endpoints are no longer accessible (should return 404 Not Found)
        # Test CREATE endpoint
        resp_create, json_data = self.send_request(method="POST", url=api.route, json_data={"name": "Another Test Partner"}, is_return_raw_response=True)
        self.assertTrue(resp_create.status_code == 404 or (resp_create.status_code == 200 and "error" in json_data))

        # Test UPDATE endpoint
        resp_update, json_data = self.send_request(
            method="PATCH",
            url=api.route + "/" + str(record_id),
            json_data={"name": "Updated Name"},
            is_return_raw_response=True,
        )
        self.assertTrue(resp_update.status_code == 404 or (resp_update.status_code == 200 and "error" in json_data))

        # Test DELETE endpoint
        resp_delete, json_data = self.send_request(method="DELETE", url=api.route + "/" + str(record_id), is_return_raw_response=True)
        self.assertTrue(resp_delete.status_code == 404 or (resp_delete.status_code == 200 and "error" in json_data))

        # Reactivate the API
        target_endpoints.action_activate()

        # Test that the API is accessible again
        resp_create = self.send_request(method="POST", url=api.route, json_data={"name": "Test Partner"})
        self.assert_record_exists(record_data=resp_create)

