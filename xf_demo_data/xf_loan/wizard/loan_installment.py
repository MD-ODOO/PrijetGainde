from odoo import models, fields


class EmployeeLoanInstallmentWizard(models.TransientModel):
    _name = 'hr.employee.loan.installment.wizard'
    _description = 'Loan Installment Wizard'

    loan_installment_id = fields.Many2one(
        string='Employee Installment',
        comodel_name='hr.employee.loan.installment',
        required=True,
        ondelete='cascade',
    )
    date_payment = fields.Date(
        string='Payment Date',
    )

    def action_paid(self):
        self.loan_installment_id.action_paid(date_payment=self.date_payment)
