# -*- coding: utf-8 -*-
from ast import literal_eval
from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError
import logging

_logger = logging.getLogger(__name__)


class SecureAPICategory(models.Model):
    _name = "secure.api.category"
    _order = "sequence"
    _description = "Secure API Category"

    name = fields.Char(string="Name", required=True)
    secure_api_ids = fields.One2many("secure.api", "category_id", string="APIs", copy=False)
    api_count = fields.Integer("Number of APIs", compute="_compute_api_count", store=True, compute_sudo=True)
    api_count_active = fields.Integer("Number of Active APIs", compute="_compute_api_count_others", store=False, compute_sudo=True)
    api_count_draft = fields.Integer("Number of Draft APIs", compute="_compute_api_count_others", store=False, compute_sudo=True)
    api_count_inactive = fields.Integer("Number of Inactive APIs", compute="_compute_api_count_others", store=False, compute_sudo=True)
    sequence = fields.Integer(help="Gives the sequence order when displaying a list of categories.")
    color = fields.Integer("Color")

    @api.depends("secure_api_ids")
    def _compute_api_count(self):
        for record in self:
            if record.secure_api_ids:
                record.api_count = len(record.secure_api_ids)
            else:
                record.api_count = 0
            pass

    @api.depends("secure_api_ids")
    def _compute_api_count_others(self):
        for record in self:
            if record.secure_api_ids:
                record.api_count_active = len(record.secure_api_ids.filtered(lambda x: x.state == "published"))
                record.api_count_draft = len(record.secure_api_ids.filtered(lambda x: x.state == "draft"))
                record.api_count_inactive = len(record.secure_api_ids.filtered(lambda x: x.state == "deactivated"))
            else:
                record.api_count_active = 0
                record.api_count_draft = 0
                record.api_count_inactive = 0
            pass

    def _get_action(self, action_xmlid):
        # action = self.env["ir.actions.actions"]._for_xml_id(action_xmlid)
        action = self.env.ref(action_xmlid, raise_if_not_found=True).read()[0]

        if self:
            action["display_name"] = self.display_name

        context = {
            "search_default_category_id": [self.id],
            "default_category_id": self.id,
        }

        action_context = literal_eval(action["context"])
        context = {**action_context, **context}
        action["context"] = context
        return action

    def get_action_secure_api_category_all(self):
        return self._get_action("secure_api.action_secure_api_category_all")

    def get_action_secure_api_category_published(self):
        return self._get_action("secure_api.action_secure_api_category_published")

    def get_action_secure_api_category_draft(self):
        return self._get_action("secure_api.action_secure_api_category_draft")

    def get_action_secure_api_category_inactive(self):
        return self._get_action("secure_api.action_secure_api_category_inactive")

