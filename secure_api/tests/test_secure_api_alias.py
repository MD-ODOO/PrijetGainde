# -*- coding: utf-8 -*-
from odoo.tests import tagged
from odoo.addons.secure_api.tests.common import TestSecureApiCommon, generate_random_string

import logging

_logger = logging.getLogger(__name__)


@tagged("secure_api", "alias")
class TestSecureApiAlias(TestSecureApiCommon):
    """Test cases for the alias_field_ids feature that allows field name aliasing in API requests/responses."""

    def setUp(self):
        super(TestSecureApiAlias, self).setUp()
        # Create a test country for related model tests
        self.test_country = self.env.ref("base.us")
        # Create a parent partner for testing related model aliases
        self.parent_partner = self.env["res.partner"].create({
            "name": "Parent Partner for Alias Test",
            "email": "parent@aliasparent.com",
            "city": "Parent City",
        })

    # =====================
    # BASIC ALIAS TESTS
    # =====================

    def test_alias_single_field_in_response(self):
        """Test that a single field alias is applied in API response."""
        api = self.create_api(
            api_action="rest",
            model_ids=["base.model_res_partner"],
            alias_field_ids=[
                {"field_id": "name", "alias": "full_name"},
            ],
        )
        # Create a partner
        new_req = self.send_request("POST", api.route, json_data={"full_name": "Alias Test Partner"})
        self.assertTrue("result" in new_req, "Response should contain result")
        result = new_req["result"][0] if isinstance(new_req["result"], list) else new_req["result"]
        
        # Response should use alias "full_name" instead of "name"
        self.assertIn("full_name", result, "Response should contain aliased field 'full_name'")
        self.assertNotIn("name", result, "Response should not contain original field 'name'")
        self.assertEqual(result["full_name"], "Alias Test Partner")

    def test_alias_single_field_in_request(self):
        """Test that alias field names in request are converted to real field names."""
        api = self.create_api(
            api_action="rest",
            model_ids=["base.model_res_partner"],
            alias_field_ids=[
                {"field_id": "email", "alias": "email_address"},
            ],
        )
        # Create using alias in request
        new_req = self.send_request("POST", api.route, json_data={
            "name": "Email Alias Test",
            "email_address": "aliased@email.com"
        })
        record = self.assert_record_exists(record_data=new_req)
        # Verify the real field was populated
        self.assertEqual(record.email, "aliased@email.com", "Alias should map to real field 'email'")

    def test_alias_multiple_fields(self):
        """Test multiple field aliases on the same model."""
        api = self.create_api(
            api_action="rest",
            model_ids=["base.model_res_partner"],
            alias_field_ids=[
                {"field_id": "name", "alias": "partner_name"},
                {"field_id": "email", "alias": "contact_email"},
                {"field_id": "phone", "alias": "phone_number"},
            ],
        )
        # Create using all aliases
        new_req = self.send_request("POST", api.route, json_data={
            "partner_name": "Multi Alias Partner",
            "contact_email": "multi@alias.com",
            "phone_number": "555-1234"
        })
        record = self.assert_record_exists(record_data=new_req)
        
        # Verify all fields were mapped correctly
        self.assertEqual(record.name, "Multi Alias Partner")
        self.assertEqual(record.email, "multi@alias.com")
        self.assertEqual(record.phone, "555-1234")
        
        # Verify response uses aliases
        result = new_req["result"][0] if isinstance(new_req["result"], list) else new_req["result"]
        self.assertIn("partner_name", result)
        self.assertIn("contact_email", result)
        self.assertIn("phone_number", result)

    # =====================
    # UPDATE TESTS
    # =====================

    def test_alias_in_update_request(self):
        """Test that aliases work in PATCH/PUT update requests."""
        api = self.create_api(
            api_action="rest",
            model_ids=["base.model_res_partner"],
            alias_field_ids=[
                {"field_id": "city", "alias": "location"},
            ],
        )
        # Create a partner first
        create_req = self.send_request("POST", api.route, json_data={"name": "Update Alias Test"})
        record = self.assert_record_exists(record_data=create_req)
        
        # Update using alias
        update_req = self.send_request("PATCH", f"{api.route}/{record.id}", json_data={
            "location": "New York"
        })
        record.invalidate_recordset()
        self.assertEqual(record.city, "New York", "Alias 'location' should update real field 'city'")

    # =====================
    # SEARCH/DOMAIN TESTS
    # =====================

    def test_alias_in_search_domain(self):
        """Test that aliases work in search domain filters."""
        # Create test partners first
        self.env["res.partner"].create({"name": "SearchAlias Alpha", "city": "Boston"})
        self.env["res.partner"].create({"name": "SearchAlias Beta", "city": "Chicago"})
        
        api = self.create_api(
            api_action="rest",
            model_ids=["base.model_res_partner"],
            alias_field_ids=[
                {"field_id": "city", "alias": "location"},
                {"field_id": "name", "alias": "partner_name"},
            ],
        )
        # Search using alias in domain
        search_req = self.send_request(
            "GET",
            api.route,
            params={"domain": '[("location", "=", "Boston"), ("partner_name", "ilike", "SearchAlias")]'}
        )
        self.assertTrue("result" in search_req)
        results = search_req["result"]
        self.assertEqual(len(results), 1, "Should find exactly one partner in Boston")
        self.assertEqual(results[0]["partner_name"], "SearchAlias Alpha")

    # =====================
    # READ TESTS
    # =====================

    def test_alias_in_read_response(self):
        """Test that aliases are applied when reading a single record."""
        partner = self.env["res.partner"].create({
            "name": "Read Alias Test",
            "email": "read@alias.com",
            "street": "123 Main St"
        })
        
        api = self.create_api(
            api_action="rest",
            model_ids=["base.model_res_partner"],
            alias_field_ids=[
                {"field_id": "street", "alias": "address_line1"},
            ],
        )
        # Read the record
        read_req = self.send_request("GET", f"{api.route}/{partner.id}")
        result = read_req["result"][0] if isinstance(read_req["result"], list) else read_req["result"]
        
        self.assertIn("address_line1", result, "Response should use alias 'address_line1'")
        self.assertEqual(result["address_line1"], "123 Main St")

    # =====================
    # RELATED MODEL ALIAS TESTS
    # =====================

    def test_alias_related_model_many2one(self):
        """Test aliases for related model fields (Many2one - country_id)."""
        api = self.create_api(
            api_action="rest",
            model_ids=["base.model_res_partner"],
            alias_field_ids=[
                {"field_id": "name", "alias": "partner_name"},
                # Alias for related model (res.country)
                {"field_id": "name", "alias": "country_name", "model_ref": "base.model_res_country"},
            ],
        )
        # Create partner with country
        new_req = self.send_request("POST", api.route, json_data={
            "partner_name": "Related Model Alias Test",
            "country_id": self.test_country.id
        })
        record = self.assert_record_exists(record_data=new_req)
        self.assertEqual(record.country_id.id, self.test_country.id)

    def test_alias_related_model_in_response_expanded(self):
        """Test that related model aliases are applied in expanded response data."""
        # This tests when related model data is expanded in response (e.g., country_id: [id, {name: "..."}])
        partner = self.env["res.partner"].create({
            "name": "Expanded Related Test",
            "country_id": self.test_country.id,
        })

        api = self.create_api(
            api_action="rest",
            model_ids=["base.model_res_partner"],
            alias_field_ids=[
                # Alias for country's name field in the expanded response
                {"field_id": "name", "alias": "country_name", "model_ref": "base.model_res_country"},
                {"field_id": "code", "alias": "country_code", "model_ref": "base.model_res_country"},
            ],
        )
        read_req = self.send_request("GET", f"{api.route}/{partner.id}")
        self.assertTrue("result" in read_req)

    def test_alias_parent_partner_related_model(self):
        """Test aliases for parent_id (Many2one to same model)."""
        child_partner = self.env["res.partner"].create({
            "name": "Child Partner",
            "parent_id": self.parent_partner.id,
        })

        api = self.create_api(
            api_action="rest",
            model_ids=["base.model_res_partner"],
            alias_field_ids=[
                {"field_id": "name", "alias": "partner_name"},
                {"field_id": "parent_id", "alias": "parent_company"},
            ],
        )
        read_req = self.send_request("GET", f"{api.route}/{child_partner.id}")
        result = read_req["result"][0] if isinstance(read_req["result"], list) else read_req["result"]

        self.assertIn("parent_company", result, "Response should use alias 'parent_company' for parent_id")

    # =====================
    # MIXED REAL AND ALIAS NAMES
    # =====================

    def test_mixed_real_and_alias_names_in_request(self):
        """Test that a mix of real field names and aliases work in the same request."""
        api = self.create_api(
            api_action="rest",
            model_ids=["base.model_res_partner"],
            alias_field_ids=[
                {"field_id": "email", "alias": "contact_email"},
            ],
        )
        # Use real field "name" and aliased field "contact_email"
        new_req = self.send_request("POST", api.route, json_data={
            "name": "Mixed Names Test",  # real field name
            "contact_email": "mixed@test.com",  # aliased field
            "phone": "123-456-7890"  # real field name (no alias)
        })
        record = self.assert_record_exists(record_data=new_req)
        self.assertEqual(record.name, "Mixed Names Test")
        self.assertEqual(record.email, "mixed@test.com")
        self.assertEqual(record.phone, "123-456-7890")

    # =====================
    # NO ALIAS DEFINED (PASSTHROUGH)
    # =====================

    def test_no_alias_passthrough(self):
        """Test that fields without aliases pass through unchanged."""
        api = self.create_api(
            api_action="rest",
            model_ids=["base.model_res_partner"],
            alias_field_ids=[
                {"field_id": "name", "alias": "partner_name"},
                # email has no alias
            ],
        )
        new_req = self.send_request("POST", api.route, json_data={
            "partner_name": "Passthrough Test",
            "email": "passthrough@test.com"  # no alias, should work with real name
        })
        record = self.assert_record_exists(record_data=new_req)
        self.assertEqual(record.email, "passthrough@test.com")

        # Response should have alias for name but real field name for email
        result = new_req["result"][0] if isinstance(new_req["result"], list) else new_req["result"]
        self.assertIn("partner_name", result)
        self.assertIn("email", result)  # email uses real name since no alias defined

    # =====================
    # CREATE API ACTION
    # =====================

    def test_alias_create_action(self):
        """Test aliases with api_action='create'."""
        api = self.create_api(
            api_action="create",
            model_ids=["base.model_res_partner"],
            alias_field_ids=[
                {"field_id": "name", "alias": "full_name"},
                {"field_id": "email", "alias": "email_address"},
            ],
        )
        new_req = self.send_request("POST", api.route, json_data={
            "full_name": "Create Action Alias Test",
            "email_address": "create@action.com"
        })
        record = self.assert_record_exists(record_data=new_req)
        self.assertEqual(record.name, "Create Action Alias Test")
        self.assertEqual(record.email, "create@action.com")

    # =====================
    # SEARCH API ACTION
    # =====================

    def test_alias_search_action(self):
        """Test aliases with api_action='search'."""
        # Create test data
        self.env["res.partner"].create({"name": "SearchAction Alpha", "city": "Seattle"})

        api = self.create_api(
            api_action="search",
            model_ids=["base.model_res_partner"],
            alias_field_ids=[
                {"field_id": "name", "alias": "partner_name"},
                {"field_id": "city", "alias": "location"},
            ],
        )
        search_req = self.send_request(
            "GET",
            api.route,
            params={"domain": '[("location", "=", "Seattle"), ("partner_name", "ilike", "SearchAction")]'}
        )
        self.assertTrue("result" in search_req)
        results = search_req["result"]
        self.assertTrue(len(results) >= 1, "Should find at least one partner")
        # Response should use aliases
        self.assertIn("partner_name", results[0])
        self.assertIn("location", results[0])

