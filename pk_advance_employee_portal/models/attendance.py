from odoo import models, fields, api

class PortalAttendance(models.Model):
    _inherit = "hr.attendance"

    lunch_in = fields.Datetime("Lunch In", tracking=True)
    lunch_out = fields.Datetime("Lunch Out", tracking=True)
    lunch_hours = fields.Float("Total Lunch Hours", compute="_compute_lunch_hours", store=True)
    net_hours = fields.Float("Net Working Hours", compute="_compute_net_hours", store=True)

    @api.depends('lunch_in', 'lunch_out')
    def _compute_lunch_hours(self):
        for rec in self:
            if rec.lunch_in and rec.lunch_out:
                delta = rec.lunch_out - rec.lunch_in
                # store full-precision float hours (do NOT round here)
                rec.lunch_hours = delta.total_seconds() / 3600.0
            else:
                rec.lunch_hours = 0.0

    @api.depends('check_in', 'check_out', 'lunch_hours')
    def _compute_net_hours(self):
        for rec in self:
            if rec.check_in and rec.check_out:
                worked_seconds = (rec.check_out - rec.check_in).total_seconds()
                worked_hours = worked_seconds / 3600.0
                rec.net_hours = worked_hours - (rec.lunch_hours or 0.0)
            else:
                rec.net_hours = 0.0
