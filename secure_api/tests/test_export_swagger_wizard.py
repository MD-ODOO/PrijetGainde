# -*- coding: utf-8 -*-
import base64
import json
from odoo.tests import Form, tagged
from odoo.addons.secure_api.tests.common import TestSecureApiCommon, generate_random_string

import logging

_logger = logging.getLogger(__name__)


@tagged("secure_api", "swagger")
class TestExportSwaggerWizard(TestSecureApiCommon):
    def setUp(self):
        super(TestExportSwaggerWizard, self).setUp()
        # Create test HTTP methods
        self.get_method = self.env.ref("secure_api.secure_api_method_get")
        self.post_method = self.env.ref("secure_api.secure_api_method_post")

        # Create test APIs for Swagger export
        self.test_api_1 = self.create_api(
            name="Test API 1",
            route="/test/api1",
            api_action="rest",
            method_ids=[self.get_method.id, self.post_method.id],
            is_published=True,
        )

        self.test_api_2 = self.create_api(
            name="Test API 2",
            route="/test/api2",
            api_action="search",
            method_ids=[self.get_method.id],
            is_published=True,
        )

    def test_swagger_wizard_creation(self):
        """Test the creation of the export wizard"""
        wizard_form = Form(self.env["export.swagger.wizard"].with_context(active_model="secure.api", active_ids=[self.test_api_1.id, self.test_api_2.id]))
        wizard_form.name = "Test API Spec"
        wizard_form.description = "Test API Specification Description"
        wizard_form.version = "2.0.0"
        wizard = wizard_form.save()

        self.assertEqual(wizard.name, "Test API Spec")
        self.assertEqual(wizard.description, "Test API Specification Description")
        self.assertEqual(wizard.version, "2.0.0")

    def test_swagger_generate_swagger_spec(self):
        """Test the generation of Swagger spec from APIs"""
        # Create a wizard with context containing the API ids
        wizard = (
            self.env["export.swagger.wizard"]
            .with_context(active_model="secure.api", active_ids=[self.test_api_1.id, self.test_api_2.id])
            .create({"name": "Test API Spec", "description": "Test API Specification Description", "version": "1.0.0"})
        )

        # Call the download method
        result = wizard.download_swagger_spec()

        # Verify the result
        self.assertEqual(result["type"], "ir.actions.act_url")
        self.assertTrue(result["url"].startswith("/web/content/export.swagger.wizard/"))
        self.assertEqual(result["target"], "self")

        # Verify the content was generated
        self.assertTrue(wizard.content, "Swagger spec content should be generated")

        # Decode and parse the content
        swagger_json = json.loads(base64.b64decode(wizard.content).decode("utf-8"))

        # Verify the swagger structure
        self.assertEqual(swagger_json["openapi"], "3.0.3")
        self.assertEqual(swagger_json["info"]["title"], "Test API Spec")
        self.assertEqual(swagger_json["info"]["description"], "Test API Specification Description")
        self.assertEqual(swagger_json["info"]["version"], "1.0.0")

        # Verify paths exist
        self.assertTrue(len(swagger_json["paths"]) > 0, "Swagger spec should have paths")

    def test_swagger_spec_structure(self):
        """Test the structure of the generated Swagger spec"""
        # Create a wizard with context containing the API ids
        wizard = (
            self.env["export.swagger.wizard"]
            .with_context(active_model="secure.api", active_ids=[self.test_api_1.id, self.test_api_2.id])
            .create({"name": "Test API Spec", "description": "Test Description", "version": "1.0.0"})
        )

        # Call the download method
        wizard.download_swagger_spec()

        # Decode and parse the content
        swagger_json = json.loads(base64.b64decode(wizard.content).decode("utf-8"))

        # Verify tags are created for each API
        tag_names = [tag["name"] for tag in swagger_json["tags"]]
        self.assertTrue(any(self.test_api_1.name in name for name in tag_names))
        self.assertTrue(any(self.test_api_2.name in name for name in tag_names))

        # Verify servers section
        self.assertTrue(len(swagger_json["servers"]) > 0)
        self.assertIn("url", swagger_json["servers"][0])

        # Verify components section
        self.assertIn("components", swagger_json)
        self.assertIn("securitySchemes", swagger_json["components"])
        self.assertIn("bearerAuth", swagger_json["components"]["securitySchemes"])
        self.assertIn("apiKeyAuth", swagger_json["components"]["securitySchemes"])

    def test_swagger_operation_details(self):
        """Test the details of operations in the Swagger spec"""
        # Create a wizard with context containing the API ids
        wizard = (
            self.env["export.swagger.wizard"]
            .with_context(active_model="secure.api", active_ids=[self.test_api_1.id])
            .create({"name": "Test API Spec", "description": "Test Description", "version": "1.0.0"})
        )

        # Call the download method
        wizard.download_swagger_spec()

        # Decode and parse the content
        swagger_json = json.loads(base64.b64decode(wizard.content).decode("utf-8"))

        # Get the first path and operation
        first_path = list(swagger_json["paths"].keys())[0]
        first_method = list(swagger_json["paths"][first_path].keys())[0]
        operation = swagger_json["paths"][first_path][first_method]

        # Verify operation details
        self.assertIn("tags", operation)
        self.assertIn("summary", operation)
        self.assertIn("operationId", operation)
        self.assertIn("responses", operation)
        self.assertIn("security", operation)

        # Verify responses
        self.assertIn("200", operation["responses"])
        self.assertIn("400", operation["responses"])
        self.assertIn("401", operation["responses"])
        self.assertIn("404", operation["responses"])
        self.assertIn("500", operation["responses"])

    def test_swagger_empty_apis(self):
        """Test generating Swagger spec with no APIs"""
        # Create a wizard with context containing no API ids
        wizard = (
            self.env["export.swagger.wizard"]
            .with_context(active_model="secure.api", active_ids=[])
            .create({"name": "Empty Spec", "description": "Empty Spec Description", "version": "1.0.0"})
        )

        # Call the download method
        wizard.download_swagger_spec()

        # Decode and parse the content
        swagger_json = json.loads(base64.b64decode(wizard.content).decode("utf-8"))

        # Verify the swagger structure
        self.assertEqual(swagger_json["info"]["title"], "Empty Spec")
        self.assertEqual(swagger_json["info"]["description"], "Empty Spec Description")
        self.assertEqual(len(swagger_json["paths"]), 0, "Swagger spec should have no paths")
        self.assertEqual(len(swagger_json["tags"]), 0, "Swagger spec should have no tags")

