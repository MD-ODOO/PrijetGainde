from odoo import models, fields


class SaleOrder(models.Model):
    _name = 'sale.order'
    _inherit = ['sale.order', 'abstract.signable.document']


    def _get_report_name(self):
        """ On indique au Mixin quel rapport utiliser pour les ventes """
        return 'sale.report_saleorder'

class PurchaseOrder(models.Model):
    _name = 'purchase.order'
    _inherit = ['purchase.order', 'abstract.signable.document']


    def _get_report_name(self):
        """ On indique au Mixin quel rapport utiliser pour les achats """
        return 'purchase.report_purchaseorder'

# class HrContract(models.Model):
#     _name = 'hr.contract'
#     _inherit = ['hr.contract', 'abstract.signable.document']

# class ProjectProject(models.Model):
#     _inherit = ['project.project', 'abstract.signable.document']
#
# class StockPicking(models.Model):
#     _inherit = ['stock.picking', 'abstract.signable.document']
