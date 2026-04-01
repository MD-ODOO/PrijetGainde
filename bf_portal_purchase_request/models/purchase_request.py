from odoo import _, api, fields, models


class PurchaseRequest(models.Model):
    _name = 'purchase.request'
    _inherit = ['purchase.request', 'portal.mixin']

    def _compute_access_url(self):
        super(PurchaseRequest, self)._compute_access_url()
        for purchase_request in self:
            purchase_request.access_url = '/my/purchase_requests/%s' % purchase_request.id

    def can_edit(self):
        self.ensure_one()
        return self.state == 'draft'

    def _get_report_base_filename(self):
        return "%s" % (self.name.replace('/', '_').replace('.', '-'))
