# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError
import logging

_logger = logging.getLogger(__name__)


class SecureAPITest(models.Model):
    _name = "secure.api.test"
    _description = "Secure API Test"

    name = fields.Char(string="Route")
    secure_api_id = fields.Many2one("secure.api", string="Secure API", required=True, ondelete="cascade")
    api_action = fields.Char(string="API Action")
    live_test_method = fields.Char("HTTP Method", default=False)
    live_test_id = fields.Char("<id>", default="1")
    live_test_ids = fields.Char("ids", default="1,2")
    live_test_model = fields.Char("<model>", default=False)
    live_test_data = fields.Char("data", default=False)
    live_test_domain = fields.Char("domain", default=False)
    live_test_offset = fields.Char("offset", default=False)
    live_test_limit = fields.Char("limit", default=False)
    live_test_order = fields.Char("order", default=False)
    status = fields.Char("Status")
    status_text = fields.Char("Status Text")
    curl_command = fields.Char("Curl Command")
    response = fields.Text("Response")

    live_test_computed_list_data = fields.Char("Data", compute="_compute_live_test_computed_list_data")

    @api.depends("live_test_data")
    def _compute_live_test_computed_list_data(self):
        for record in self:
            record.live_test_computed_list_data = str(record.live_test_data) if record.live_test_data else False
        pass

