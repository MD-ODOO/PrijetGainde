# -*- coding: utf-8 -*-
from odoo.tests import tagged
from odoo.addons.secure_api.tests.common import TestSecureApiCommon, generate_random_string

import logging
import json

_logger = logging.getLogger(__name__)


@tagged("secure_api", "search_fields")
class TestSearchFields(TestSecureApiCommon):
    """Test cases for the search_field_ids feature that limits exposed fields in search endpoints."""

    def setUp(self):
        super(TestSearchFields, self).setUp()
        # Create a test partner to be used in searches
        self.test_partner = self.env["res.partner"].create(
            {
                "name": "Search Fields Test Partner",
                "email": "test.search.fields@example.com",
                "phone": "123456789",
                "street": "123 Test Street",
                "city": "Test City",
                "country_id": self.env.ref("base.us").id,
            }
        )

    def test_search_fields_all_fields(self):
        """Test when allowed_field_type is 'all' and search_field_ids is empty."""
        api = self.create_api(
            api_action="rest",
            allowed_field_type="all",
            # No search_field_ids specified
        )

        # Perform a search request
        response = self.send_request(method="GET", url=api.route, params={"domain": "[('id', '=', %s)]" % self.test_partner.id})

        # Verify all standard fields are returned
        self.assertTrue("result" in response)
        self.assertTrue("records" in response["result"])
        self.assertEqual(len(response["result"]["records"]), 1)

        record = response["result"]["records"][0]
        # Check that standard fields are present
        self.assertTrue("id" in record)
        self.assertTrue("name" in record)
        self.assertTrue("email" in record)
        self.assertTrue("phone" in record)

        _logger.info(f"All fields test - fields returned: {list(record.keys())}")

    def test_search_fields_specific_fields_no_search_fields(self):
        """Test when allowed_field_type is 'specific' but search_field_ids is empty."""
        # Create API with specific fields but no search fields
        api = self.create_api(api_action="rest", allowed_field_type="specific")

        # Add specific fields
        field_ids = self.env["ir.model.fields"].search([("model_id.model", "=", "res.partner"), ("name", "in", ["name", "email", "phone"])])
        api.write({"field_ids": [(6, 0, field_ids.ids)]})

        # Perform a search request
        response = self.send_request(method="GET", url=api.route, params={"domain": "[('id', '=', %s)]" % self.test_partner.id})

        # Verify only specified fields are returned
        self.assertTrue("result" in response)
        self.assertTrue("records" in response["result"])
        self.assertEqual(len(response["result"]["records"]), 1)

        record = response["result"]["records"][0]
        # Check that only the specified fields are present
        self.assertTrue("id" in record)  # id is always included
        self.assertTrue("name" in record)
        self.assertTrue("email" in record)
        self.assertTrue("phone" in record)
        # Street should not be present as it wasn't in field_ids
        self.assertFalse("street" in record)

        _logger.info(f"Specific fields test - fields returned: {list(record.keys())}")

    def test_search_fields_with_search_fields_subset(self):
        """Test when search_field_ids is a subset of field_ids."""
        # Create API with specific fields
        api = self.create_api(api_action="rest", allowed_field_type="specific")

        # Add specific fields
        field_ids = self.env["ir.model.fields"].search([("model_id.model", "=", "res.partner"), ("name", "in", ["name", "email", "phone", "street", "city"])])
        api.write({"field_ids": [(6, 0, field_ids.ids)]})

        # Add search fields (subset of field_ids)
        search_field_ids = self.env["ir.model.fields"].search(
            [
                ("model_id.model", "=", "res.partner"),
                ("name", "in", ["name", "email"]),  # Only name and email for search
            ]
        )
        api.write({"search_field_ids": [(6, 0, search_field_ids.ids)]})

        # Perform a search request
        response = self.send_request(method="GET", url=api.route, params={"domain": "[('id', '=', %s)]" % self.test_partner.id})

        # Verify only search fields are returned
        self.assertTrue("result" in response)
        self.assertTrue("records" in response["result"])
        self.assertEqual(len(response["result"]["records"]), 1)

        record = response["result"]["records"][0]
        # Check that only the search fields are present
        self.assertTrue("id" in record)  # id is always included
        self.assertTrue("name" in record)
        self.assertTrue("email" in record)
        # These should not be present as they weren't in search_field_ids
        self.assertFalse("phone" in record)
        self.assertFalse("street" in record)
        self.assertFalse("city" in record)

        _logger.info(f"Search fields subset test - fields returned: {list(record.keys())}")

    def test_search_fields_all_fields_with_search_fields(self):
        """Test when allowed_field_type is 'all' but search_field_ids is specified."""
        # Create API with all fields
        api = self.create_api(api_action="rest", allowed_field_type="all")

        # Add search fields
        search_field_ids = self.env["ir.model.fields"].search(
            [
                ("model_id.model", "=", "res.partner"),
                ("name", "in", ["name", "email"]),  # Only name and email for search
            ]
        )
        api.write({"search_field_ids": [(6, 0, search_field_ids.ids)]})

        # Perform a search request
        response = self.send_request(method="GET", url=api.route, params={"domain": "[('id', '=', %s)]" % self.test_partner.id})

        # Verify only search fields are returned
        self.assertTrue("result" in response)
        self.assertTrue("records" in response["result"])
        self.assertEqual(len(response["result"]["records"]), 1)

        record = response["result"]["records"][0]
        # Check that only the search fields are present
        self.assertTrue("id" in record)  # id is always included
        self.assertTrue("name" in record)
        self.assertTrue("email" in record)
        # These should not be present as they weren't in search_field_ids
        self.assertFalse("phone" in record)
        self.assertFalse("street" in record)

        _logger.info(f"All fields with search fields test - fields returned: {list(record.keys())}")


@tagged("secure_api", "search_fields", "security")
class TestSearchDomainInjection(TestSecureApiCommon):
    """Test cases for domain injection prevention in search endpoints."""

    def setUp(self):
        super(TestSearchDomainInjection, self).setUp()
        # Create a test partner
        self.test_partner = self.env["res.partner"].create(
            {
                "name": "Injection Test Partner",
                "email": "injection.test@example.com",
            }
        )

    def test_domain_code_injection_import_os(self):
        """Test that __import__('os').popen(...) code injection is blocked."""
        api = self.create_api(api_action="rest", allowed_field_type="all")

        # Attempt code injection via domain parameter
        # This is the exact payload reported by the user
        malicious_domain = "[('output', '=', __import__('os').popen('ip addr').read())] #\""

        response, response_data = self.send_request(
            method="GET",
            url=api.route,
            params={"domain": malicious_domain},
            is_return_raw_response=True,
        )

        # The request should fail (not return 200) or return an error in response
        # ast.literal_eval should reject this as it contains function calls
        self.assertTrue(
            response.status_code != 200 or (response.status_code == 200 and "error" in response_data),
            "Code injection attempt should be rejected, but got status 200 without error")
        _logger.info(f"Code injection blocked with status: {response.status_code}")

    def test_domain_code_injection_eval(self):
        """Test that eval() injection attempts are blocked."""
        api = self.create_api(api_action="rest", allowed_field_type="all")

        malicious_domain = "[('name', '=', eval('1+1'))]"

        response, response_data = self.send_request(
            method="GET",
            url=api.route,
            params={"domain": malicious_domain},
            is_return_raw_response=True,
        )

        self.assertTrue(
            response.status_code != 200 or (response.status_code == 200 and "error" in response_data),
            "eval() injection attempt should be rejected")
        _logger.info(f"eval() injection blocked with status: {response.status_code}")

    def test_domain_code_injection_exec(self):
        """Test that exec() injection attempts are blocked."""
        api = self.create_api(api_action="rest", allowed_field_type="all")

        malicious_domain = "[('name', '=', exec('import os'))]"

        response, response_data = self.send_request(
            method="GET",
            url=api.route,
            params={"domain": malicious_domain},
            is_return_raw_response=True,
        )

        self.assertTrue(
            response.status_code != 200 or (response.status_code == 200 and "error" in response_data),
            "exec() injection attempt should be rejected")
        _logger.info(f"exec() injection blocked with status: {response.status_code}")

    def test_domain_code_injection_open_file(self):
        """Test that open() file access injection attempts are blocked."""
        api = self.create_api(api_action="rest", allowed_field_type="all")

        malicious_domain = "[('name', '=', open('/etc/passwd').read())]"

        response, response_data = self.send_request(
            method="GET",
            url=api.route,
            params={"domain": malicious_domain},
            is_return_raw_response=True,
        )

        self.assertTrue(
            response.status_code != 200 or (response.status_code == 200 and "error" in response_data),
            "open() file access injection should be rejected")
        _logger.info(f"open() injection blocked with status: {response.status_code}")

    def test_domain_code_injection_subprocess(self):
        """Test that subprocess command injection attempts are blocked."""
        api = self.create_api(api_action="rest", allowed_field_type="all")

        malicious_domain = "[('name', '=', __import__('subprocess').check_output(['whoami']))]"

        response, response_data = self.send_request(
            method="GET",
            url=api.route,
            params={"domain": malicious_domain},
            is_return_raw_response=True,
        )

        self.assertTrue(
            response.status_code != 200 or (response.status_code == 200 and "error" in response_data),
            "subprocess injection attempt should be rejected")
        _logger.info(f"subprocess injection blocked with status: {response.status_code}")

    def test_domain_valid_search_still_works(self):
        """Test that valid domain searches still work after security checks."""
        api = self.create_api(api_action="rest", allowed_field_type="all")

        # Valid domain that should work
        valid_domain = "[('id', '=', %s)]" % self.test_partner.id

        response = self.send_request(
            method="GET",
            url=api.route,
            params={"domain": valid_domain},
        )

        self.assertTrue("result" in response)
        self.assertTrue("records" in response["result"])
        self.assertEqual(len(response["result"]["records"]), 1)
        self.assertEqual(response["result"]["records"][0]["id"], self.test_partner.id)
        _logger.info("Valid domain search works correctly")
