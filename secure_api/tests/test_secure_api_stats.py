# -*- coding: utf-8 -*-
from odoo.tests import Form, tagged
from odoo.addons.secure_api.tests.common import TestSecureApiCommon, generate_random_string
from odoo.exceptions import UserError

import logging

_logger = logging.getLogger(__name__)


@tagged("secure_api", "stats")
class TestSecureApiStats(TestSecureApiCommon):
    def setUp(self):
        super(TestSecureApiStats, self).setUp()
        # Create test HTTP methods
        self.get_method = self.env.ref("secure_api.secure_api_method_get")
        self.post_method = self.env.ref("secure_api.secure_api_method_post")

        # Create a test API with stats enabled
        self.test_api_with_stats = self.create_api(api_action="rest", is_stats=True, is_published=True)

        # Create a test API with stats disabled
        self.test_api_without_stats = self.create_api(api_action="rest", is_stats=False, is_published=True)

        self.assertTrue(self.test_api_with_stats.exists(), "Test API With Stats should exist")
        self.assertTrue(self.test_api_without_stats.exists(), "Test API Without Stats should exist")

        # # Ensure the API with stats has a stats record
        # if not self.test_api_with_stats.secure_api_stats_id:
        #     stats = self.env['secure.api.stats'].create({
        #         'name': self.test_api_with_stats.name + " Stats"
        #     })
        #     self.test_api_with_stats.secure_api_stats_id = stats.id

    def test_stats_creation(self):
        """Test that stats record is properly created and linked to API"""
        # Check that the API with stats has a stats record
        self.assertTrue(self.test_api_with_stats.secure_api_stats_id, "API with stats should have a stats record")

        # Check that the stats record is properly linked to the API
        self.assertEqual(
            self.test_api_with_stats.secure_api_stats_id.secure_api_id,
            self.test_api_with_stats,
            "Stats record should be linked to the API",
        )

        # Check initial values
        self.assertEqual(self.test_api_with_stats.secure_api_stats_id.hit_success, 0, "Initial success count should be 0")
        self.assertEqual(self.test_api_with_stats.secure_api_stats_id.hit_fail, 0, "Initial fail count should be 0")
        self.assertEqual(self.test_api_with_stats.secure_api_stats_id.total_hit, 0, "Initial total hit count should be 0")

    def test_stats_successful_request_stats(self):
        """Test that successful requests increment the success counter"""
        # Get initial stats values
        initial_success = self.test_api_with_stats.secure_api_stats_id.hit_success
        initial_total = self.test_api_with_stats.secure_api_stats_id.total_hit

        # Make a successful request
        response = self.send_request("GET", self.test_api_with_stats.route)

        # Refresh the record to get updated values
        if hasattr(self.env, "invalidate_all"):
            self.env.invalidate_all()
        else:
            self.test_api_with_stats.secure_api_stats_id.invalidate_cache()
        self.test_api_with_stats = self.env["secure.api"].browse(self.test_api_with_stats.id)

        # Check that the success counter was incremented
        self.assertEqual(
            self.test_api_with_stats.secure_api_stats_id.hit_success,
            initial_success + 1,
            "Success counter should be incremented after successful request",
        )
        self.assertEqual(
            self.test_api_with_stats.secure_api_stats_id.total_hit,
            initial_total + 1,
            "Total hit counter should be incremented after successful request",
        )

        # Check that a stats line was created
        stats_line = self.env["secure.api.stats.line"].search(
            [
                ("stats_id", "=", self.test_api_with_stats.secure_api_stats_id.id),
                ("line_type", "=", "success"),
                ("method", "=", "GET"),
            ],
            limit=1,
        )

        self.assertTrue(stats_line, "A stats line should be created for successful request")
        self.assertEqual(stats_line.secure_api_id, self.test_api_with_stats, "Stats line should be linked to the correct API")

    def test_stats_failed_request_stats(self):
        """Test that failed requests increment the fail counter"""
        # Create an API that will generate an error (invalid domain filter)
        error_api = self.create_api(
            name="Error API",
            route="/test/error_api",
            api_action="search",
            method_ids=[self.get_method.id],
            domain="[('invalid_field', '=', 'value')]",  # This will cause an error
            is_stats=True,
            is_published=True,
        )

        # Get initial stats values
        initial_fail = error_api.secure_api_stats_id.hit_fail
        initial_total = error_api.secure_api_stats_id.total_hit

        # Make a request that will fail
        try:
            self.send_request("GET", error_api.route, is_return_raw_response=True)
        except Exception as e:
            # Expected to fail
            pass

        # Refresh the record to get updated values
        if hasattr(self.env, "invalidate_all"):
            self.env.invalidate_all()
        else:
            error_api.secure_api_stats_id.invalidate_cache()
        error_api = self.env["secure.api"].browse(error_api.id)

        # Check that the fail counter was incremented
        self.assertEqual(
            error_api.secure_api_stats_id.hit_fail,
            initial_fail + 1,
            "Fail counter should be incremented after failed request",
        )
        self.assertEqual(
            error_api.secure_api_stats_id.total_hit,
            initial_total + 1,
            "Total hit counter should be incremented after failed request",
        )

        # Check that a stats line was created
        stats_line = self.env["secure.api.stats.line"].search(
            [("stats_id", "=", error_api.secure_api_stats_id.id), ("line_type", "=", "error"), ("method", "=", "GET")],
            limit=1,
        )

        self.assertTrue(stats_line, "A stats line should be created for failed request")
        self.assertTrue(stats_line.error, "Error information should be recorded")

    def test_stats_disabled_stats(self):
        """Test that requests to APIs with stats disabled don't create stats records"""
        total_hit_before = self.test_api_without_stats.secure_api_stats_id.total_hit

        # Make a request to the API without stats
        response = self.send_request("GET", self.test_api_without_stats.route)

        total_hit_after = self.test_api_without_stats.secure_api_stats_id.total_hit
        # Check that no stats line was created (there should be no stats record linked to this API)
        # self.assertFalse(self.test_api_without_stats.secure_api_stats_id,
        #                  "API with stats disabled should not have a stats record")
        self.assertEqual(total_hit_before, total_hit_after, "Total hit counter should not be incremented for API with stats disabled")

    def test_stats_calculation(self):
        """Test that success and failure rates are correctly calculated"""
        stats = self.test_api_with_stats.secure_api_stats_id

        # Manually set hit counts
        stats.hit_success = 75
        stats.hit_fail = 25

        # Check calculated fields
        self.assertEqual(stats.total_hit, 100, "Total hits should be sum of success and fail")
        self.assertEqual(stats.rate_success, 0.75, "Success rate should be 75%")
        self.assertEqual(stats.rate_fail, 0.25, "Fail rate should be 25%")

    def test_stats_multiple_requests(self):
        """Test that multiple requests correctly increment counters"""
        # Get initial stats values
        initial_success = self.test_api_with_stats.secure_api_stats_id.hit_success

        # Make multiple successful requests
        num_requests = 5
        for i in range(num_requests):
            self.send_request("GET", self.test_api_with_stats.route)

        # Refresh the record to get updated values
        if hasattr(self.env, "invalidate_all"):
            self.env.invalidate_all()
        else:
            self.test_api_with_stats.secure_api_stats_id.invalidate_cache()
        self.test_api_with_stats = self.env["secure.api"].browse(self.test_api_with_stats.id)

        # Check that the success counter was incremented correctly
        self.assertEqual(
            self.test_api_with_stats.secure_api_stats_id.hit_success,
            initial_success + num_requests,
            f"Success counter should be incremented by {num_requests} after {num_requests} successful requests",
        )

        # Check that the correct number of stats lines were created
        stats_lines = self.env["secure.api.stats.line"].search(
            [
                ("stats_id", "=", self.test_api_with_stats.secure_api_stats_id.id),
                ("line_type", "=", "success"),
                ("method", "=", "GET"),
            ]
        )

        self.assertTrue(
            len(stats_lines) >= num_requests,
            f"At least {num_requests} stats lines should be created for {num_requests} successful requests",
        )

    def test_stats_line_data(self):
        """Test that request data is correctly stored in stats lines"""
        # Make a request with specific data
        test_data = {"name": "test_value"}
        response = self.send_request("POST", self.test_api_with_stats.route, json_data=test_data)

        # Find the stats line for this request
        stats_line = self.env["secure.api.stats.line"].search(
            [
                ("stats_id", "=", self.test_api_with_stats.secure_api_stats_id.id),
                # ('line_type', '=', 'success'),
                ("method", "=", "POST"),
            ],
            limit=1,
            order="id desc",
        )

        self.assertTrue(stats_line, "A stats line should be created for the request")
        self.assertTrue("name" in stats_line.data, "Request data should be stored in the stats line")
        self.assertTrue("test_value" in stats_line.data, "Request data should be stored in the stats line")

