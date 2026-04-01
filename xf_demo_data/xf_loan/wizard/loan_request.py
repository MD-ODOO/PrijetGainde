from markupsafe import Markup

from odoo import models, fields, _


class EmployeeLoanRequestWizard(models.TransientModel):
    _name = 'hr.employee.loan.request.wizard'
    _description = 'Loan Request Wizard'

    loan_request_id = fields.Many2one(
        string='Employee Loan Request',
        comodel_name='hr.employee.loan.request',
        required=True,
        ondelete='cascade',
    )
    comments = fields.Text(
        string='Comments',
        required=True,
    )

    def action_reject(self):
        message = Markup(_("""<div><strong>Reject Reason</strong>: <span class="text-info">%s</span></div>""") % self.comments)
        self.loan_request_id.with_context(mail_reason_body=message).action_reject()
