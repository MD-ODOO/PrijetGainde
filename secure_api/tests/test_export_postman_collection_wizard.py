# -*- coding: utf-8 -*-
import base64
import json
from odoo.tests import Form, tagged
from odoo.addons.secure_api.tests.common import TestSecureApiCommon, generate_random_string

import logging

_logger = logging.getLogger(__name__)


@tagged("secure_api", "postman")
class TestExportPostmanCollectionWizard(TestSecureApiCommon):
    def setUp(self):
        super(TestExportPostmanCollectionWizard, self).setUp()
        # Create test HTTP methods
        self.get_method = self.env.ref("secure_api.secure_api_method_get")
        self.post_method = self.env.ref("secure_api.secure_api_method_post")

        # Create test APIs for collection export
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

    def test_postman_wizard_creation(self):
        """Test the creation of the export wizard"""
        wizard_form = Form(self.env["export.postman.collection.wizard"].with_context(active_model="secure.api", active_ids=[self.test_api_1.id, self.test_api_2.id]))
        wizard_form.name = "Test Collection"
        wizard_form.description = "Test Collection Description"
        wizard = wizard_form.save()

        self.assertEqual(wizard.name, "Test Collection")
        self.assertEqual(wizard.description, "Test Collection Description")

    def test_postman_generate_postman_collection(self):
        """Test the generation of Postman collection from APIs"""
        # Create a wizard with context containing the API ids
        wizard = (
            self.env["export.postman.collection.wizard"]
            .with_context(active_model="secure.api", active_ids=[self.test_api_1.id, self.test_api_2.id])
            .create({"name": "Test Collection", "description": "Test Collection Description"})
        )

        # Call the download method
        result = wizard.download_postman_collection()

        # Verify the result
        self.assertEqual(result["type"], "ir.actions.act_url")
        self.assertTrue(result["url"].startswith("/web/content/export.postman.collection.wizard/"))
        self.assertEqual(result["target"], "self")

        # Verify the content was generated
        self.assertTrue(wizard.content, "Postman collection content should be generated")

        # Decode and parse the content
        collection_json = json.loads(base64.b64decode(wizard.content).decode("utf-8"))

        # Verify the collection structure
        self.assertEqual(collection_json["info"]["name"], "Test Collection")
        self.assertEqual(collection_json["info"]["description"], "Test Collection Description")
        self.assertEqual(collection_json["info"]["schema"], "https://schema.getpostman.com/json/collection/v2.1.0/collection.json")

        # Verify the collection items (folders)
        self.assertTrue(len(collection_json["item"]) > 0, "Collection should have items")

    def test_postman_collection_structure(self):
        """Test the structure of the generated Postman collection"""
        # Create a wizard with context containing the API ids
        wizard = (
            self.env["export.postman.collection.wizard"]
            .with_context(active_model="secure.api", active_ids=[self.test_api_1.id, self.test_api_2.id])
            .create({"name": "Test Collection", "description": "Test Collection Description"})
        )

        # Call the download method
        wizard.download_postman_collection()

        # Decode and parse the content
        collection_json = json.loads(base64.b64decode(wizard.content).decode("utf-8"))

        # Verify folders are created for each API
        folder_names = [folder["name"] for folder in collection_json["item"]]
        self.assertTrue(any(self.test_api_1.name in name for name in folder_names))
        self.assertTrue(any(self.test_api_2.name in name for name in folder_names))

        # Verify each folder contains the correct endpoints
        for folder in collection_json["item"]:
            if self.test_api_1.name in folder["name"]:
                # Test API 1 should have endpoints
                self.assertTrue(len(folder["item"]) > 0)
                endpoint_names = [item["name"] for item in folder["item"]]
                self.assertEqual(len(folder["item"]), 5)

            if self.test_api_2.name in folder["name"]:
                # Test API 2 should have endpoints
                self.assertTrue(len(folder["item"]) > 0)
                endpoint_names = [item["name"] for item in folder["item"]]
                self.assertEqual(len(folder["item"]), 1)

    def test_postman_request_details(self):
        """Test the details of the requests in the Postman collection"""
        # Create a wizard with context containing the API ids
        wizard = (
            self.env["export.postman.collection.wizard"]
            .with_context(active_model="secure.api", active_ids=[self.test_api_1.id])
            .create({"name": "Test Collection", "description": "Test Collection Description"})
        )

        # Call the download method
        wizard.download_postman_collection()

        # Decode and parse the content
        collection_json = json.loads(base64.b64decode(wizard.content).decode("utf-8"))

        # Get the first request
        first_folder = collection_json["item"][0]
        first_request = first_folder["item"][0]["request"]

        # Verify request details
        self.assertTrue("method" in first_request)
        self.assertTrue("header" in first_request)
        self.assertTrue("url" in first_request)

        # Verify URL structure
        url = first_request["url"]
        self.assertTrue("raw" in url)
        self.assertTrue("protocol" in url)
        self.assertTrue("host" in url)
        self.assertTrue("path" in url)

        # Verify headers
        headers = first_request["header"]
        content_type_headers = [h for h in headers if h["key"] == "Content-Type"]
        self.assertTrue(len(content_type_headers) > 0)
        self.assertEqual(content_type_headers[0]["value"], "application/json")

    def test_postman_empty_apis(self):
        """Test generating collection with no APIs"""
        # Create a wizard with context containing no API ids
        wizard = (
            self.env["export.postman.collection.wizard"]
            .with_context(active_model="secure.api", active_ids=[])
            .create({"name": "Empty Collection", "description": "Empty Collection Description"})
        )

        # Call the download method
        wizard.download_postman_collection()

        # Decode and parse the content
        collection_json = json.loads(base64.b64decode(wizard.content).decode("utf-8"))

        # Verify the collection structure
        self.assertEqual(collection_json["info"]["name"], "Empty Collection")
        self.assertEqual(collection_json["info"]["description"], "Empty Collection Description")
        self.assertEqual(len(collection_json["item"]), 0, "Collection should have no items")
