# -*- coding: utf-8 -*-
from odoo.tests import tagged
from odoo.addons.secure_api.tests.common import TestSecureApiCommon, generate_random_string
from odoo.addons.secure_api.controllers.hashids import Hashids

import logging

_logger = logging.getLogger(__name__)


@tagged("secure_api", "secure_record_id")
class TestSecureRecordIdDecode(TestSecureApiCommon):
    """Test cases for secure record ID decoding in POST, PATCH, DELETE methods.
    
    Verifies that:
    - Relation fields (many2one, many2many, one2many) are properly decoded from obfuscated IDs
    - Primitive fields (string, integer, boolean, etc.) are NOT decoded
    - Invalid IDs that cannot be decoded return an error
    """

    def setUp(self):
        super(TestSecureRecordIdDecode, self).setUp()
        # Create a parent partner for relation field tests
        self.parent_partner = self.env["res.partner"].create({
            "name": "Parent Partner for Decode Test",
            "email": "parent.decode@example.com",
        })
        # Create a category for many2many relation tests
        self.category = self.env["res.partner.category"].create({
            "name": "Test Category for Decode",
        })
        # Create a child partner for one2many tests
        self.child_partner = self.env["res.partner"].create({
            "name": "Child Partner for Decode Test",
            "email": "child.decode@example.com",
            "parent_id": self.parent_partner.id,
        })

    def _get_hash_manager(self, api):
        """Get the hash manager for encoding/decoding IDs."""
        salt = api.hashids_salt or self.env["ir.config_parameter"].sudo().get_param("secure_api.hashids_salt")
        min_length = api.hashids_min_length or int(self.env["ir.config_parameter"].sudo().get_param("secure_api.hashids_min_length", 5))
        return Hashids(salt=salt, min_length=min_length)

    # =====================
    # POST Method Tests
    # =====================

    def test_post_decode_many2one_relation_field(self):
        """Test POST: many2one relation field (parent_id) is decoded from obfuscated ID."""
        api = self.create_api(api_action="rest", is_secure_record_id=True)
        hash_manager = self._get_hash_manager(api)

        # Encode the parent_id
        encoded_parent_id = hash_manager.encode(self.parent_partner.id)

        # POST with encoded parent_id
        response = self.send_request(
            method="POST",
            url=api.route,
            json_data={
                "name": "Child with Encoded Parent",
                "parent_id": encoded_parent_id,  # Encoded many2one relation
            },
        )

        self.assertTrue("result" in response)
        created_id = response["result"]["id"]
        # Decode the created record ID to get actual ID
        decoded_id = hash_manager.decode(created_id)[0]
        created_record = self.env["res.partner"].browse(decoded_id)

        # Verify the parent_id was correctly decoded and saved
        self.assertEqual(created_record.parent_id.id, self.parent_partner.id,
            "many2one field parent_id should be decoded from obfuscated ID")

    def test_post_decode_many2many_relation_field(self):
        """Test POST: many2many relation field (category_id) is decoded from obfuscated IDs."""
        api = self.create_api(api_action="rest", is_secure_record_id=True)
        hash_manager = self._get_hash_manager(api)

        # Encode the category ID
        encoded_category_id = hash_manager.encode(self.category.id)

        # POST with encoded category_id using command (6, 0, [ids])
        response = self.send_request(
            method="POST",
            url=api.route,
            json_data={
                "name": "Partner with Encoded Category",
                "category_id": [[6, 0, [encoded_category_id]]],  # Encoded many2many relation
            },
        )

        self.assertTrue("result" in response)
        created_id = response["result"]["id"]
        decoded_id = hash_manager.decode(created_id)[0]
        created_record = self.env["res.partner"].browse(decoded_id)

        # Verify the category_id was correctly decoded and saved
        self.assertIn(self.category.id, created_record.category_id.ids,
            "many2many field category_id should be decoded from obfuscated IDs")

    def test_post_primitive_fields_not_decoded(self):
        """Test POST: primitive fields (string, integer, boolean) are NOT decoded."""
        api = self.create_api(api_action="rest", is_secure_record_id=True)
        hash_manager = self._get_hash_manager(api)

        # Use values that look like they could be encoded IDs but are actually primitive data
        test_name = "Partner ABC123"
        test_phone = "1234567890"
        test_ref = "REF-XYZ789"

        response = self.send_request(
            method="POST",
            url=api.route,
            json_data={
                "name": test_name,
                "phone": test_phone,
                "ref": test_ref,
            },
        )

        self.assertTrue("result" in response)
        created_id = response["result"]["id"]
        decoded_id = hash_manager.decode(created_id)[0]
        created_record = self.env["res.partner"].browse(decoded_id)

        # Verify primitive fields are stored as-is, not decoded
        self.assertEqual(created_record.name, test_name,
            "Primitive string field 'name' should NOT be decoded")
        self.assertEqual(created_record.phone, test_phone,
            "Primitive string field 'phone' should NOT be decoded")
        self.assertEqual(created_record.ref, test_ref,
            "Primitive string field 'ref' should NOT be decoded")

    def test_post_invalid_relation_id_returns_error(self):
        """Test POST: invalid obfuscated ID in relation field returns error."""
        api = self.create_api(api_action="rest", is_secure_record_id=True)

        # Use an invalid encoded ID that cannot be decoded
        invalid_encoded_id = "INVALID_ID_XYZ123"

        response, response_data = self.send_request(
            method="POST",
            url=api.route,
            json_data={
                "name": "Partner with Invalid Parent",
                "parent_id": invalid_encoded_id,  # Invalid encoded ID
            },
            is_return_raw_response=True,
        )

        # Should return error (non-200 status or error in response)
        self.assertTrue(
            response.status_code != 200 or "error" in response_data,
            "Invalid obfuscated ID in relation field should return an error"
        )
        _logger.info(f"Invalid ID error response status: {response.status_code}")

    # =====================
    # PATCH Method Tests
    # =====================

    def test_patch_decode_many2one_relation_field(self):
        """Test PATCH: many2one relation field (parent_id) is decoded from obfuscated ID."""
        api = self.create_api(api_action="rest", is_secure_record_id=True)
        hash_manager = self._get_hash_manager(api)

        # Create a partner first
        test_partner = self.env["res.partner"].create({"name": "Partner to Update"})
        encoded_partner_id = hash_manager.encode(test_partner.id)
        encoded_parent_id = hash_manager.encode(self.parent_partner.id)

        # PATCH with encoded parent_id
        response = self.send_request(
            method="PATCH",
            url=f"{api.route}/{encoded_partner_id}",
            json_data={
                "parent_id": encoded_parent_id,  # Encoded many2one relation
            },
        )

        self.assertTrue("result" in response)
        if hasattr(self.env, "invalidate_all"):
            self.env.invalidate_all()
        else:
            test_partner.invalidate_cache()

        # Verify the parent_id was correctly decoded and updated
        self.assertEqual(test_partner.parent_id.id, self.parent_partner.id,
            "PATCH: many2one field parent_id should be decoded from obfuscated ID")

    def test_patch_decode_many2many_relation_field(self):
        """Test PATCH: many2many relation field (category_id) is decoded from obfuscated IDs."""
        api = self.create_api(api_action="rest", is_secure_record_id=True)
        hash_manager = self._get_hash_manager(api)

        # Create a partner first
        test_partner = self.env["res.partner"].create({"name": "Partner to Update M2M"})
        encoded_partner_id = hash_manager.encode(test_partner.id)
        encoded_category_id = hash_manager.encode(self.category.id)

        # PATCH with encoded category_id using command (6, 0, [ids])
        response = self.send_request(
            method="PATCH",
            url=f"{api.route}/{encoded_partner_id}",
            json_data={
                "category_id": [[6, 0, [encoded_category_id]]],  # Encoded many2many relation
            },
        )

        self.assertTrue("result" in response)
        if hasattr(self.env, "invalidate_all"):
            self.env.invalidate_all()
        else:
            test_partner.invalidate_cache()

        # Verify the category_id was correctly decoded and updated
        self.assertIn(self.category.id, test_partner.category_id.ids,
            "PATCH: many2many field category_id should be decoded from obfuscated IDs")

    def test_patch_primitive_fields_not_decoded(self):
        """Test PATCH: primitive fields (string, integer, boolean) are NOT decoded."""
        api = self.create_api(api_action="rest", is_secure_record_id=True)
        hash_manager = self._get_hash_manager(api)

        # Create a partner first
        test_partner = self.env["res.partner"].create({"name": "Partner to Update Primitives"})
        encoded_partner_id = hash_manager.encode(test_partner.id)

        test_name = "Updated Name XYZ789"
        test_phone = "9876543210"
        test_ref = "REF-UPDATED-ABC"

        # PATCH with primitive fields
        response = self.send_request(
            method="PATCH",
            url=f"{api.route}/{encoded_partner_id}",
            json_data={
                "name": test_name,
                "phone": test_phone,
                "ref": test_ref,
            },
        )

        self.assertTrue("result" in response)
        if hasattr(self.env, "invalidate_all"):
            self.env.invalidate_all()
        else:
            test_partner.invalidate_cache()

        # Verify primitive fields are stored as-is, not decoded
        self.assertEqual(test_partner.name, test_name,
            "PATCH: Primitive string field 'name' should NOT be decoded")
        self.assertEqual(test_partner.phone, test_phone,
            "PATCH: Primitive string field 'phone' should NOT be decoded")
        self.assertEqual(test_partner.ref, test_ref,
            "PATCH: Primitive string field 'ref' should NOT be decoded")

    def test_patch_invalid_relation_id_returns_error(self):
        """Test PATCH: invalid obfuscated ID in relation field returns error."""
        api = self.create_api(api_action="rest", is_secure_record_id=True)
        hash_manager = self._get_hash_manager(api)

        # Create a partner first
        test_partner = self.env["res.partner"].create({"name": "Partner for Invalid Update"})
        encoded_partner_id = hash_manager.encode(test_partner.id)

        # Use an invalid encoded ID that cannot be decoded
        invalid_encoded_id = "INVALID_ID_XYZ123"

        response, response_data = self.send_request(
            method="PATCH",
            url=f"{api.route}/{encoded_partner_id}",
            json_data={
                "parent_id": invalid_encoded_id,  # Invalid encoded ID
            },
            is_return_raw_response=True,
        )

        # Should return error (non-200 status or error in response)
        self.assertTrue(
            response.status_code != 200 or "error" in response_data,
            "PATCH: Invalid obfuscated ID in relation field should return an error"
        )
        _logger.info(f"PATCH invalid ID error response status: {response.status_code}")

    def test_patch_invalid_url_id_returns_error(self):
        """Test PATCH: invalid obfuscated ID in URL returns error."""
        api = self.create_api(api_action="rest", is_secure_record_id=True)

        # Use an invalid encoded ID in the URL
        invalid_url_id = "INVALID_URL_ID_123"

        response, response_data = self.send_request(
            method="PATCH",
            url=f"{api.route}/{invalid_url_id}",
            json_data={"name": "Updated Name"},
            is_return_raw_response=True,
        )

        # Should return error (404 or error in response)
        self.assertTrue(
            response.status_code == 404 or "error" in response_data,
            "PATCH: Invalid obfuscated ID in URL should return 404 or error"
        )
        _logger.info(f"PATCH invalid URL ID error response status: {response.status_code}")

    # =====================
    # DELETE Method Tests
    # =====================

    def test_delete_with_valid_encoded_id(self):
        """Test DELETE: valid obfuscated ID in URL is properly decoded."""
        api = self.create_api(api_action="rest", is_secure_record_id=True)
        hash_manager = self._get_hash_manager(api)

        # Create a partner to delete
        test_partner = self.env["res.partner"].create({"name": "Partner to Delete"})
        partner_id = test_partner.id
        encoded_partner_id = hash_manager.encode(partner_id)

        # DELETE with encoded ID
        response = self.send_request(
            method="DELETE",
            url=f"{api.route}/{encoded_partner_id}",
        )

        self.assertTrue("result" in response)
        self.assertIn(encoded_partner_id, response["result"],
            "DELETE: should return the deleted encoded ID")

        # Verify the record was actually deleted
        deleted_record = self.env["res.partner"].browse(partner_id)
        self.assertFalse(deleted_record.exists(),
            "DELETE: Record should be deleted from database")

    def test_delete_invalid_url_id_returns_error(self):
        """Test DELETE: invalid obfuscated ID in URL returns error."""
        api = self.create_api(api_action="rest", is_secure_record_id=True)

        # Use an invalid encoded ID in the URL
        invalid_url_id = "INVALID_DELETE_ID_123"

        response, response_data = self.send_request(
            method="DELETE",
            url=f"{api.route}/{invalid_url_id}",
            is_return_raw_response=True,
        )

        # Should return error (404 or error in response)
        self.assertTrue(
            response.status_code == 404 or "error" in response_data,
            "DELETE: Invalid obfuscated ID in URL should return 404 or error"
        )
        _logger.info(f"DELETE invalid URL ID error response status: {response.status_code}")

    def test_delete_bulk_with_encoded_ids(self):
        """Test DELETE bulk: multiple obfuscated IDs are properly decoded."""
        api = self.create_api(api_action="rest", is_secure_record_id=True, is_allow_multi=True)
        hash_manager = self._get_hash_manager(api)

        # Create partners to delete
        partner1 = self.env["res.partner"].create({"name": "Bulk Delete Partner 1"})
        partner2 = self.env["res.partner"].create({"name": "Bulk Delete Partner 2"})

        encoded_id1 = hash_manager.encode(partner1.id)
        encoded_id2 = hash_manager.encode(partner2.id)

        # DELETE bulk with encoded IDs
        response = self.send_request(
            method="DELETE",
            url=f"{api.route}",
            json_data={"ids": [encoded_id1, encoded_id2]},
        )

        self.assertTrue("result" in response)

        # Verify the records were actually deleted
        deleted_records = self.env["res.partner"].browse([partner1.id, partner2.id])
        self.assertFalse(deleted_records.exists(),
            "DELETE bulk: Records should be deleted from database")

    def test_delete_bulk_with_invalid_id_returns_error(self):
        """Test DELETE bulk: invalid obfuscated ID in list returns error."""
        api = self.create_api(api_action="rest", is_secure_record_id=True, is_allow_multi=True)
        hash_manager = self._get_hash_manager(api)

        # Create a valid partner
        partner1 = self.env["res.partner"].create({"name": "Bulk Delete Valid Partner"})
        encoded_id1 = hash_manager.encode(partner1.id)

        # Mix valid and invalid IDs
        invalid_id = "INVALID_BULK_ID_XYZ"

        response, response_data = self.send_request(
            method="DELETE",
            url=f"{api.route}",
            json_data={"ids": [encoded_id1, invalid_id]},
            is_return_raw_response=True,
        )

        # Should return error (non-200 status or error in response)
        self.assertTrue(
            response.status_code != 200 or "error" in response_data,
            "DELETE bulk: Invalid obfuscated ID in list should return an error"
        )
        _logger.info(f"DELETE bulk invalid ID error response status: {response.status_code}")

