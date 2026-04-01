# -*- coding: utf-8 -*-
from ast import literal_eval
from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError
import logging

_logger = logging.getLogger(__name__)


class IrModel(models.Model):
    _name = "ir.model"
    _inherit = "ir.model"

    secure_api_ids = fields.Many2many("secure.api", "secure_api_ir_model_rel", string="APIs")
    api_count = fields.Integer("Number of APIs", compute="_compute_api_count", store=True, compute_sudo=True)
    api_count_active = fields.Integer("Number of Active APIs", compute="_compute_api_count", store=True, compute_sudo=True)
    api_count_draft = fields.Integer("Number of Draft APIs", compute="_compute_api_count", store=True, compute_sudo=True)
    api_count_inactive = fields.Integer("Number of Inactive APIs", compute="_compute_api_count", store=True, compute_sudo=True)

    def name_get(self):
        result = []
        for model in self:
            name = "%s (%s)" % (model.name, model.model)
            result.append((model.id, name))
        return result

    @api.depends("secure_api_ids")
    def _compute_api_count(self):
        for record in self:
            # Use sudo() to bypass access checks: non-admin users cannot read
            # secure.api records (group_system only), but they should still be
            # able to see ir.model records without hitting an AccessError.
            api_ids = record.sudo().secure_api_ids
            if api_ids:
                record.api_count = len(api_ids)
                record.api_count_active = len(api_ids.filtered(lambda x: x.state == "published"))
                record.api_count_draft = len(api_ids.filtered(lambda x: x.state == "draft"))
                record.api_count_inactive = len(api_ids.filtered(lambda x: x.state == "deactivated"))
            else:
                record.api_count = 0
                record.api_count_active = 0
                record.api_count_draft = 0
                record.api_count_inactive = 0

    def _get_action(self, action_xmlid, additional_domain=[]):
        action = self.env.ref(action_xmlid, raise_if_not_found=True).read()[0]

        if self:
            action["display_name"] = self.display_name

        domain = [("model_ids.model", "in", [self.model])]
        context = {"default_model_ids": [self.id]}

        action_context = literal_eval(action["context"])
        context = {**action_context, **context}
        action["context"] = context
        action["domain"] = domain + additional_domain
        return action

    def get_action_secure_api_model_all(self):
        return self._get_action("secure_api.action_secure_api_model_common", additional_domain=[])

    def get_action_secure_api_model_published(self):
        return self._get_action("secure_api.action_secure_api_model_common", additional_domain=[("state", "=", "published")])

    def get_action_secure_api_model_draft(self):
        return self._get_action("secure_api.action_secure_api_model_common", additional_domain=[("state", "=", "draft")])

    def get_action_secure_api_model_inactive(self):
        return self._get_action("secure_api.action_secure_api_model_common", additional_domain=[("state", "=", "deactivated")])

