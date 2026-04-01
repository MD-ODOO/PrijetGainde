# -*- coding: utf-8 -*-
import random
import string
from odoo import api, fields, models

import logging

_logger = logging.getLogger(__name__)


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    default_auth = fields.Selection(
        [
            ("none", "Public"),
            ("user", "User"),
        ],
        string="Default Authentication",
        default="none",
        default_model="secure.api",
    )
    default_cors = fields.Char("Default CORS", default="*", default_model="secure.api")
    default_is_secure_record_id = fields.Boolean("Default Hide Record Id", default=False, default_model="secure.api")
    default_listing_limit = fields.Integer("Default Listing Limit", default=10, help="Default number of results per page", default_model="secure.api")
    default_is_allow_multi = fields.Boolean(
        "Default Bulk Operation",
        default=False,
        help="Allow the action affects on multiple records with one API request (create, read, update, delete, rpc)",
        default_model="secure.api",
    )
    hashids_salt = fields.Char(
        "Default Hashids Salt",
        config_parameter="secure_api.hashids_salt",
        default=lambda self: "".join(random.choices(string.ascii_uppercase + string.digits, k=9)),
        required=True,
        help="Default salt used for generating obfuscated IDs",
    )
    hashids_min_length = fields.Integer(
        "Default Hashids Min Length",
        config_parameter="secure_api.hashids_min_length",
        default=5,
        required=True,
        help="Default minimum length for obfuscated IDs",
    )
    is_disable_xml_rpc = fields.Boolean("Disable XML-RPC", config_parameter="secure_api.is_disable_xml_rpc", default=False)
    is_expose_api_on_view = fields.Boolean("Expose API Button", config_parameter="secure_api.is_expose_api_on_view", default=False)
    expose_api_route_prefix = fields.Char("Route Prefix", config_parameter="secure_api.expose_api_route_prefix")

    @api.model
    def _init_random_hashids_salt(self):
        # Only initialize salt if it doesn't already exist
        existing_salt = self.env["ir.config_parameter"].sudo().get_param("secure_api.hashids_salt")
        if not existing_salt:
            salt = "".join(random.choices(string.ascii_uppercase + string.digits, k=9))
            _logger.info(f"Initialized random hashids salt: {salt}")
            self.env["ir.config_parameter"].sudo().set_param("secure_api.hashids_salt", salt)
