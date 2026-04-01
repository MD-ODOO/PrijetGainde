# -*- coding: utf-8 -*-

from odoo import models, fields, api

class PurchaseRequestLineReject(models.TransientModel):
    _name = 'purchase.request.line.reject'
    _description = 'Purchase Request Line Rejection Wizard'

    rejection_reason = fields.Text(string="Motif du rejet", required=True)

    def action_confirm_rejection(self):
        active_ids = self.env.context.get('active_ids', [])
        if active_ids:
            lines = self.env['purchase.request.line'].browse(active_ids)
            lines.write({'rejection_reason': self.rejection_reason})
            lines.action_reject_lines()
        return {'type': 'ir.actions.act_window_close'}
