from odoo import models, fields, api


class ProjectMilestone(models.Model):
    _inherit = 'project.milestone'

    invoiced = fields.Boolean(string="Facturé", default=False, copy=False)
    percentage = fields.Float(string="% du total", default=0.0)
