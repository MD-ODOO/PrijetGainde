# -*- coding: utf-8 -*-
from odoo.tests import Form, tagged
from odoo.addons.secure_api.tests.common import TestSecureApiCommon, generate_random_string
from odoo.exceptions import UserError

import logging

_logger = logging.getLogger(__name__)


@tagged("secure_api", "settings")
class TestResConfigSettings(TestSecureApiCommon):
    def setUp(self):
        super(TestResConfigSettings, self).setUp()
        # Create test HTTP methods
        self.get_method = self.env.ref("secure_api.secure_api_method_get")
        self.post_method = self.env.ref("secure_api.secure_api_method_post")

    def test_settings_default_values(self):
        """Test that default values are correctly set in the settings"""
        # Create a new settings record
        settings = self.env["res.config.settings"].create(
            {
                "default_auth": "user",
                "default_cors": "https://example.com",
                "default_is_secure_record_id": True,
                "default_listing_limit": 20,
                "default_is_allow_multi": True,
            }
        )

        # Save the settings
        settings.execute()

        # Create a new API form to check if defaults are applied
        api_form = Form(self.env["secure.api"])

        # Check that default values are applied
        self.assertEqual(api_form.auth, "user", "Default auth should be applied")
        self.assertEqual(api_form.cors, "https://example.com", "Default CORS should be applied")
        self.assertEqual(api_form.is_secure_record_id, True, "Default is_secure_record_id should be applied")
        self.assertEqual(api_form.listing_limit, 20, "Default listing_limit should be applied")
        self.assertEqual(api_form.is_allow_multi, True, "Default is_allow_multi should be applied")

    def test_settings_xml_rpc_flag(self):
        """Test that the XML-RPC flag is correctly set and retrieved"""
        # Create a new settings record with XML-RPC disabled
        settings = self.env["res.config.settings"].create({"is_disable_xml_rpc": True})

        # Save the settings
        settings.execute()

        # Check that the parameter is correctly set
        param_value = self.env["ir.config_parameter"].sudo().get_param("secure_api.is_disable_xml_rpc")
        self.assertEqual(param_value, "True", "XML-RPC disable flag should be set to True")

        # Create a new settings record with XML-RPC enabled
        settings = self.env["res.config.settings"].create({"is_disable_xml_rpc": False})

        # Save the settings
        settings.execute()

        # Check that the parameter is correctly set
        param_value = self.env["ir.config_parameter"].sudo().get_param("secure_api.is_disable_xml_rpc")
        self.assertFalse(param_value, "XML-RPC disable flag should be set to False")

    def test_settings_expose_api_flag(self):
        """Test that the expose API flag is correctly set and retrieved"""
        # Create a new settings record with expose API enabled
        settings = self.env["res.config.settings"].create({"is_expose_api_on_view": True})

        # Save the settings
        settings.execute()

        # Check that the parameter is correctly set
        param_value = self.env["ir.config_parameter"].sudo().get_param("secure_api.is_expose_api_on_view")
        self.assertEqual(param_value, "True", "Expose API flag should be set to True")

        # Create a new settings record with expose API disabled
        settings = self.env["res.config.settings"].create({"is_expose_api_on_view": False})

        # Save the settings
        settings.execute()

        # Check that the parameter is correctly set
        param_value = self.env["ir.config_parameter"].sudo().get_param("secure_api.is_expose_api_on_view")
        self.assertFalse(param_value, "Expose API flag should be set to False")

    def test_settings_route_prefix(self):
        """Test that the route prefix is correctly set and retrieved"""
        # Create a new settings record with a custom route prefix
        settings = self.env["res.config.settings"].create({"expose_api_route_prefix": "/custom/api"})

        # Save the settings
        settings.execute()

        # Check that the parameter is correctly set
        param_value = self.env["ir.config_parameter"].sudo().get_param("secure_api.expose_api_route_prefix")
        self.assertEqual(param_value, "/custom/api", "Route prefix should be correctly set")

    def test_settings_create_api_with_defaults(self):
        """Test creating an API with default settings applied"""
        # Set default values
        settings = self.env["res.config.settings"].create(
            {
                "default_auth": "user",
                "default_cors": "https://example.com",
                "default_is_secure_record_id": True,
                "default_listing_limit": 20,
                "default_is_allow_multi": True,
            }
        )
        settings.execute()

        # Create a new API
        api = self.create_api(
            name="Test API With Defaults",
            route="/test/api_with_defaults",
            api_action="rest",
            method_ids=[self.get_method.id, self.post_method.id],
            is_published=True,
        )

        # Check that default values were applied
        self.assertEqual(api.auth, "user", "Default auth should be applied")
        self.assertEqual(api.cors, "https://example.com", "Default CORS should be applied")
        self.assertEqual(api.is_secure_record_id, True, "Default is_secure_record_id should be applied")
        self.assertEqual(api.listing_limit, 20, "Default listing_limit should be applied")
        self.assertEqual(api.is_allow_multi, True, "Default is_allow_multi should be applied")

    def test_settings_expose_api_button_functionality(self):
        """Test the functionality of exposing API on a model"""
        # Enable expose API button
        settings = self.env["res.config.settings"].create({"is_expose_api_on_view": True})
        settings.execute()

        # Check that the parameter is correctly set
        param_value = self.env["ir.config_parameter"].sudo().get_param("secure_api.is_expose_api_on_view")
        self.assertEqual(param_value, "True", "Expose API flag should be set to True")

        # Call the method that is triggered when clicking the Expose API button
        result = self.env["secure.api"].btn_expose_new_api("res.partner")

        # Check the result
        self.assertEqual(result["type"], "ir.actions.act_window", "Should return a window action")
        self.assertEqual(result["res_model"], "secure.api", "Should open the secure.api model")
        self.assertEqual(
            result["context"]["default_model_id_alias"],
            self.env["ir.model"].search([("model", "=", "res.partner")]).id,
            "Should set the default model to res.partner",
        )

