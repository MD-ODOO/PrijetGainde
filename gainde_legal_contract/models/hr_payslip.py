import base64
from odoo import models, fields

class HrPayslip(models.Model):
    _name = 'hr.payslip'
    _inherit = ['hr.payslip', 'abstract.signable.document']

    document_ids = fields.Many2many(
        'ir.attachment',
        'hr_payslip_documents_rel',
        'payslip_id',
        'document_id',
        string="Bulletin Associé",
        help="Bulletins signés, justificatifs, avenants au contrat...",
        domain=[('mimetype', '=', 'application/pdf')],
        copy=False,
    )

    def _get_report_name(self):
        """ On indique au Mixin quel rapport utiliser pour la paie """
        return 'hr_payload.report_payslip'
