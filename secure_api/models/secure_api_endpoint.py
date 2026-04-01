# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools import config
import logging

_logger = logging.getLogger(__name__)


class SecureAPIEndpoint(models.Model):
    _name = "secure.api.endpoint"
    _description = "Secure API Endpoint"

    name = fields.Char(string="Name", required=False)
    http_method_id = fields.Many2one("secure.api.method", string="HTTP Method")
    route = fields.Char(string="Endpoint")
    data = fields.Char(string="Sample Data")
    is_bulk_operation = fields.Boolean(string="Bulk")
    secure_api_id = fields.Many2one("secure.api", string="API")
    api_action = fields.Char("Action")
    state = fields.Selection([("active", "Active"), ("inactive", "Inactive")], string="Status", default="active", required=True)

    curl = fields.Char(string="Curl", compute="_compute_curl")

    def toggle_active(self):
        """Toggle the endpoint state between active and inactive"""
        for record in self:
            record.secure_api_id.endpoint_ids.filtered(lambda x: x.http_method_id.id == record.http_method_id.id and x.route == record.route).update(
                {"state": "inactive" if record.state == "active" else "active"}
            )

    def action_activate(self):
        """Set the endpoint state to active"""
        for record in self:
            record.secure_api_id.endpoint_ids.filtered(lambda x: x.http_method_id.id == record.http_method_id.id and x.route == record.route).update({"state": "active"})

    def action_deactivate(self):
        """Set the endpoint state to inactive"""
        for record in self:
            record.secure_api_id.endpoint_ids.filtered(lambda x: x.http_method_id.id == record.http_method_id.id and x.route == record.route).update({"state": "inactive"})

    @api.depends("http_method_id", "route", "data")
    def _compute_curl(self):
        for record in self:
            if record.http_method_id and record.route:
                base_url = self.env["ir.config_parameter"].sudo().get_param("web.base.url")
                if record.data:
                    if record.http_method_id.name.lower == "get":  # GET with query string
                        gen_curl = 'curl -X %(http_method)s -H "Content-Type: application/json" %(base_url)s%(route)s?%(data)s' % {
                            "http_method": record.http_method_id.name,
                            "base_url": base_url,
                            "route": record.route,
                            "data": record.data,
                        }
                    else:
                        gen_curl = "curl -X %(http_method)s -H \"Content-Type: application/json\" -d '%(data)s' %(base_url)s%(route)s" % {
                            "http_method": record.http_method_id.name,
                            "base_url": base_url,
                            "route": record.route,
                            "data": record.data,
                        }
                    pass
                else:
                    gen_curl = 'curl -X %(http_method)s -H "Content-Type: application/json" %(base_url)s%(route)s' % {
                        "http_method": record.http_method_id.name,
                        "base_url": base_url,
                        "route": record.route,
                    }
                record.curl = gen_curl
                pass
            else:
                record.curl = False
        pass

