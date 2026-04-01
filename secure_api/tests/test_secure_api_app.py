import datetime
import unittest
from odoo.addons.secure_api.tests.common import TestSecureApiCommon
from odoo.tests import TransactionCase, tagged
from odoo import fields
import logging

_logger = logging.getLogger(__name__)

# Try to import PyJWT - it's optional
try:
    import jwt
    JWT_AVAILABLE = True
except ImportError:
    jwt = None
    JWT_AVAILABLE = False


@tagged("secure_api_app")
class TestSecureApiApp(TestSecureApiCommon):
    def setUp(self):
        super().setUp()
        self.api = self.create_api(api_action="rest", mode="prod", auth="user")
        # Create a 3rd party app in test mode with specific scopes (OAuth2)
        self.app = self.env["secure.api.app"].create(
            {
                "name": "Test App",
                "auth_type": "oauth2",
                "mode": "test",
                "scope_create": True,
                "scope_read": True,
                "scope_update": False,
                "scope_delete": False,
                "scope_search": True,
                "scope_rpc": False,
                "expire_minute": 1,  # 1 minute expiry for testing
                "api_ids": [(6, 0, [self.api.id])],
            }
        )

    def test_app_client_id_and_secret_generated(self):
        self.assertTrue(self.app.client_id)
        self.assertTrue(self.app.client_secret)

    def test_app_access_token_issuance_and_expiry(self):
        # Issue token
        token = self.env["secure.api.app.token"].create(
            {
                "name": "tok123",
                "app_id": self.app.id,
                "expire_date": fields.Datetime.now() + datetime.timedelta(minutes=1),
            }
        )
        self.assertEqual(token.state, "active")
        # Simulate expiry
        token.expire_date = fields.Datetime.now() - datetime.timedelta(minutes=2)
        token._compute_state()
        self.assertEqual(token.state, "expired")

    def test_app_get_3rd_party_app_by_token(self):
        token = self.env["secure.api.app.token"].create(
            {
                "name": "tok456",
                "app_id": self.app.id,
                "expire_date": fields.Datetime.now() + datetime.timedelta(minutes=1),
            }
        )
        found_app = self.env["secure.api.app.token"].get_3rd_party_app("tok456")
        self.assertEqual(found_app.id, self.app.id)
        # Expired token should not return app
        token.expire_date = fields.Datetime.now() - datetime.timedelta(minutes=2)
        token._compute_state()
        found_app_expired = self.env["secure.api.app.token"].get_3rd_party_app("tok456")
        self.assertFalse(found_app_expired)

    def test_app_scope_enforcement(self):
        endpoint_scopes = set(self.app.endpoint_ids.mapped("api_action"))
        sc_names = ["create", "read", "update", "delete", "search", "rpc"]
        app_scopes = set([scn for scn in sc_names if getattr(self.app, "scope_" + scn)])
        self.assertEqual(endpoint_scopes, app_scopes)

    def test_app_test_mode_does_not_affect_real_data(self):
        response, data = self.send_request(
            method="POST",
            url="/api/oauth2/token",
            is_return_raw_response=True,
            data={"client_id": self.app.client_id, "client_secret": self.app.client_secret},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        self.assertEqual(response.status_code, 200)
        _logger.info(f"data: {data}")
        access_token = data["access_token"]
        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {access_token}"}

        # Create a test partner using the API with the OAuth2 token
        response = self.send_request("POST", self.api.route, headers=headers, json_data={"name": "Test Partner via OAuth2"})

        # Extract the partner ID from the response
        result = response["result"][0] if isinstance(response["result"], list) and len(response["result"]) == 1 else response["result"]
        record_id = result["id"]
        record = self.env[self.get_default_model_name()].browse(record_id)
        self.assertFalse(record.exists(), "There should be no record (%d) on %s" % (record_id, self.get_default_model_name()))

    def test_app_request_invalid_scope(self):
        response, data = self.send_request(
            method="POST",
            url="/api/oauth2/token",
            is_return_raw_response=True,
            data={"client_id": self.app.client_id, "client_secret": self.app.client_secret},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        self.assertEqual(response.status_code, 200)
        _logger.info(f"data: {data}")
        access_token = data["access_token"]
        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {access_token}"}

        # Create a test partner using the API with the OAuth2 token
        search_response = self.send_request(
            "GET",
            self.api.route,
            headers=headers,
        )
        self.assertTrue(len(search_response["result"]["records"]) > 0)
        record_id = search_response["result"]["records"][0]["id"]

        # Not allow to delete, because scope_delete is False
        delete_response, delete_data = self.send_request("DELETE", self.api.route + f"/{record_id}", headers=headers, is_return_raw_response=True)
        self.assertEqual(delete_response.status_code, 200)
        self.assertIn("error", delete_data)

    def test_app_token_cleanup_cron(self):
        # Create expired token
        expired_token = self.env["secure.api.app.token"].create(
            {
                "name": "tok_expired",
                "app_id": self.app.id,
                "expire_date": fields.Datetime.now() - datetime.timedelta(minutes=2),
            }
        )
        # Run cron
        self.env["secure.api.app.token"]._cron_delete_old_access_token()
        # Token should be deleted
        self.assertFalse(self.env["secure.api.app.token"].search([("name", "=", "tok_expired")]))

    def test_app_disabled_does_not_generate_token(self):
        """Test that a disabled client app does not generate a new access token."""
        # Ensure the app is initially enabled
        self.assertEqual(self.app.state, "enabled")

        # Disable the app
        self.app.btn_disable_app()
        self.assertEqual(self.app.state, "disabled")

        # Attempt to get an access token with the disabled app
        response = self.send_request(
            method="POST",
            url="/api/oauth2/token",
            is_return_raw_response=True,
            is_only_return_reponse=True,
            data={"client_id": self.app.client_id, "client_secret": self.app.client_secret},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

        # The request should fail (not return 200 with access_token)
        self.assertNotEqual(response.status_code, 200, "Disabled app should not return HTTP 200")

    def test_app_api_access_without_token(self):
        """Test that accessing OAuth2-protected API without token fails."""
        # Try to access the API without any Authorization header
        response, data = self.send_request(
            method="GET",
            url=self.api.route,
            is_return_raw_response=True,
            headers={"Content-Type": "application/json"},
        )
        # Should fail: either status != 200 or status == 200 with error in response
        access_denied = response.status_code != 200 or (response.status_code == 200 and "error" in data)
        self.assertTrue(access_denied, "API access without OAuth2 token should be denied")


@tagged("secure_api_jwt")
@unittest.skipIf(not JWT_AVAILABLE, "PyJWT library is not installed. Skipping JWT tests.")
class TestSecureApiJWT(TestSecureApiCommon):
    """Test cases for JWT Authentication feature."""

    def setUp(self):
        super().setUp()
        self.api = self.create_api(api_action="rest", mode="prod", auth="user")
        # Create a JWT-based 3rd party app
        self.jwt_app = self.env["secure.api.app"].create(
            {
                "name": "Test JWT App",
                "auth_type": "jwt",
                "mode": "test",
                "scope_create": True,
                "scope_read": True,
                "scope_update": False,
                "scope_delete": False,
                "scope_search": True,
                "scope_rpc": False,
                "expire_minute": 1,  # 1 minute expiry for testing
                "api_ids": [(6, 0, [self.api.id])],
            }
        )

    def test_jwt_app_fields_generated(self):
        """Test that JWT-specific fields are generated on creation."""
        self.assertTrue(self.jwt_app.jwt_secret)
        self.assertEqual(self.jwt_app.jwt_algorithm, "HS256")
        self.assertEqual(self.jwt_app.auth_type, "jwt")

    def test_jwt_token_generation(self):
        """Test that JWT token can be generated for JWT app."""
        token = self.jwt_app.generate_jwt_token()
        self.assertTrue(token)
        # Verify the token can be decoded
        decoded = jwt.decode(token, self.jwt_app.jwt_secret, algorithms=[self.jwt_app.jwt_algorithm])
        self.assertEqual(decoded["app_id"], self.jwt_app.id)
        self.assertEqual(decoded["client_id"], self.jwt_app.client_id)
        self.assertEqual(decoded["user_id"], self.jwt_app.security_user_id.id)

    def test_jwt_token_validation(self):
        """Test JWT token validation method."""
        token = self.jwt_app.generate_jwt_token()
        # Validate the token
        validated_app = self.env["secure.api.app"].validate_jwt_token(token)
        self.assertEqual(validated_app.id, self.jwt_app.id)

    def test_jwt_token_endpoint(self):
        """Test the /api/jwt/token endpoint."""
        response, data = self.send_request(
            method="POST",
            url="/api/jwt/token",
            is_return_raw_response=True,
            json_data={"client_id": self.jwt_app.client_id, "client_secret": self.jwt_app.client_secret},
            headers={"Content-Type": "application/json"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("access_token", data)
        self.assertEqual(data["token_type"], "Bearer")
        self.assertIn("expires_in", data)
        self.assertIn("scope", data)

    def test_jwt_token_api_access(self):
        """Test that JWT token can be used to access API endpoints."""
        # Get JWT token
        response, data = self.send_request(
            method="POST",
            url="/api/jwt/token",
            is_return_raw_response=True,
            json_data={"client_id": self.jwt_app.client_id, "client_secret": self.jwt_app.client_secret},
            headers={"Content-Type": "application/json"},
        )
        self.assertEqual(response.status_code, 200)
        access_token = data["access_token"]
        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {access_token}"}

        # Use the token to access the API (search)
        search_response = self.send_request("GET", self.api.route, headers=headers)
        self.assertIn("result", search_response)

    def test_jwt_api_access_without_token(self):
        """Test that accessing JWT-protected API without token fails."""
        # Try to access the API without any Authorization header
        response, data = self.send_request(
            method="GET",
            url=self.api.route,
            is_return_raw_response=True,
            headers={"Content-Type": "application/json"},
        )
        # Should fail: either status != 200 or status == 200 with error in response
        access_denied = response.status_code != 200 or (response.status_code == 200 and "error" in data)
        self.assertTrue(access_denied, "API access without JWT token should be denied")

    def test_jwt_disabled_app_no_token(self):
        """Test that a disabled JWT app does not generate a token."""
        self.jwt_app.btn_disable_app()
        self.assertEqual(self.jwt_app.state, "disabled")

        response = self.send_request(
            method="POST",
            url="/api/jwt/token",
            is_return_raw_response=True,
            is_only_return_reponse=True,
            json_data={"client_id": self.jwt_app.client_id, "client_secret": self.jwt_app.client_secret},
            headers={"Content-Type": "application/json"},
        )
        self.assertNotEqual(response.status_code, 200, "Disabled JWT app should not return HTTP 200")

    def test_jwt_request_invalid_scope(self):
        """Test that JWT app cannot perform actions outside of its allowed scopes."""
        response, data = self.send_request(
            method="POST",
            url="/api/jwt/token",
            is_return_raw_response=True,
            json_data={"client_id": self.jwt_app.client_id, "client_secret": self.jwt_app.client_secret},
            headers={"Content-Type": "application/json"},
        )
        self.assertEqual(response.status_code, 200)
        _logger.info(f"data: {data}")
        access_token = data["access_token"]
        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {access_token}"}

        # Search for existing records
        search_response = self.send_request(
            "GET",
            self.api.route,
            headers=headers,
        )
        self.assertTrue(len(search_response["result"]["records"]) > 0)
        record_id = search_response["result"]["records"][0]["id"]

        # Not allow to delete, because scope_delete is False
        delete_response, delete_data = self.send_request("DELETE", self.api.route + f"/{record_id}", headers=headers, is_return_raw_response=True)
        self.assertEqual(delete_response.status_code, 200)
        self.assertIn("error", delete_data)

    def test_jwt_test_mode_does_not_affect_real_data(self):
        """Test that JWT app in test mode does not affect real data."""
        response, data = self.send_request(
            method="POST",
            url="/api/jwt/token",
            is_return_raw_response=True,
            json_data={"client_id": self.jwt_app.client_id, "client_secret": self.jwt_app.client_secret},
            headers={"Content-Type": "application/json"},
        )
        self.assertEqual(response.status_code, 200)
        _logger.info(f"data: {data}")
        access_token = data["access_token"]
        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {access_token}"}

        # Create a test partner using the API with the JWT token
        response = self.send_request("POST", self.api.route, headers=headers, json_data={"name": "Test Partner via JWT"})

        # Extract the partner ID from the response
        result = response["result"][0] if isinstance(response["result"], list) and len(response["result"]) == 1 else response["result"]
        record_id = result["id"]
        record = self.env[self.get_default_model_name()].browse(record_id)
        self.assertFalse(record.exists(), "There should be no record (%d) on %s" % (record_id, self.get_default_model_name()))

    def test_jwt_token_missing_client_id_or_secret(self):
        """Test that missing client_id or client_secret returns status code 400."""
        # Test missing client_id
        response = self.send_request(
            method="POST",
            url="/api/jwt/token",
            is_return_raw_response=True,
            is_only_return_reponse=True,
            json_data={"client_secret": self.jwt_app.client_secret},
            headers={"Content-Type": "application/json"},
        )
        self.assertEqual(response.status_code, 400, "Missing client_id should return status code 400")

        # Test missing client_secret
        response = self.send_request(
            method="POST",
            url="/api/jwt/token",
            is_return_raw_response=True,
            is_only_return_reponse=True,
            json_data={"client_id": self.jwt_app.client_id},
            headers={"Content-Type": "application/json"},
        )
        self.assertEqual(response.status_code, 400, "Missing client_secret should return status code 400")

        # Test missing both
        response = self.send_request(
            method="POST",
            url="/api/jwt/token",
            is_return_raw_response=True,
            is_only_return_reponse=True,
            json_data={},
            headers={"Content-Type": "application/json"},
        )
        self.assertEqual(response.status_code, 400, "Missing both client_id and client_secret should return status code 400")

    def test_jwt_token_invalid_client_id_or_secret(self):
        """Test that invalid client_id or client_secret returns status code not equal to 200."""
        # Test invalid client_id
        response = self.send_request(
            method="POST",
            url="/api/jwt/token",
            is_return_raw_response=True,
            is_only_return_reponse=True,
            json_data={"client_id": "invalid_client_id", "client_secret": self.jwt_app.client_secret},
            headers={"Content-Type": "application/json"},
        )
        self.assertNotEqual(response.status_code, 200, "Invalid client_id should not return status code 200")

        # Test invalid client_secret
        response = self.send_request(
            method="POST",
            url="/api/jwt/token",
            is_return_raw_response=True,
            is_only_return_reponse=True,
            json_data={"client_id": self.jwt_app.client_id, "client_secret": "invalid_client_secret"},
            headers={"Content-Type": "application/json"},
        )
        self.assertNotEqual(response.status_code, 200, "Invalid client_secret should not return status code 200")

        # Test both invalid
        response = self.send_request(
            method="POST",
            url="/api/jwt/token",
            is_return_raw_response=True,
            is_only_return_reponse=True,
            json_data={"client_id": "invalid_client_id", "client_secret": "invalid_client_secret"},
            headers={"Content-Type": "application/json"},
        )
        self.assertNotEqual(response.status_code, 200, "Invalid client_id and client_secret should not return status code 200")
