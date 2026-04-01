# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
import werkzeug
import werkzeug.exceptions
from odoo import api, models
from odoo import SUPERUSER_ID
from odoo.http import request, Response
from odoo.release import version_info  # (18, ...)

import logging

_logger = logging.getLogger(__name__)


class Http(models.AbstractModel):
    _inherit = "ir.http"

    @classmethod
    def _match(cls, path_info, key=None):
        try:
            return super()._match(path_info)
        except werkzeug.exceptions.NotFound:  # 404 not found
            try:
                # Always use request.env.cr / request.env.context (works in all
                # supported versions; request.cr and request.context were
                # deprecated in Odoo 17 and removed/aliased in 18).
                env = api.Environment(request.env.cr, SUPERUSER_ID, request.env.context)
                records = env["secure.api"].search([("state", "=", "published")])
                records.update_routing_map(routing_map=request.env["ir.http"].routing_map())
            except Exception:
                _logger.debug("secure_api: could not update routing map on 404", exc_info=True)
            return super()._match(path_info)
