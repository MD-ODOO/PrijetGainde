from odoo import models, fields

class AccountMove(models.Model):
    _name = 'account.move'

    _inherit = ['account.move', 'abstract.signable.document']

    document_ids = fields.Many2many(
        'ir.attachment',
        'account_move_documents_rel',
        'move_id',
        'document_id',
        string="Documents liés",
        help="Factures signées, bons de commande, preuves de paiement...",
        domain=[('mimetype', '=', 'application/pdf')],
        copy=False,
    )

    def _get_report_name(self):
        """ On indique au Mixin quel rapport utiliser pour les factures """
        return 'account.report_invoice_with_payments'

