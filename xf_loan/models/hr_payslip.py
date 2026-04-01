from odoo import models, api, Command

class HrPayslip(models.Model):
    _inherit = 'hr.payslip'

    @api.depends('employee_id', 'contract_id', 'date_from', 'date_to', 'struct_id')
    def _compute_input_line_ids(self):
        super()._compute_input_line_ids()

        installment_model = self.env['hr.employee.loan.installment']
        input_type = self.env.ref('xf_loan.input_type_loan', raise_if_not_found=False)

        for slip in self:
            if not slip.employee_id or not slip.contract_id or not input_type:
                continue

            installments = installment_model._get_installments_for_payslip(
                slip.employee_id,
                slip.date_from,
                slip.date_to
            )

            if not installments:
                continue

            # ✅ Calcul simple et fiable
            amount = sum(installments.mapped('amount'))

            # ✅ Remplacement propre des lignes input
            slip.input_line_ids = [
                Command.clear(),
                Command.create({
                    'name': 'Prêt Employé',
                    'amount': amount,
                    'input_type_id': input_type.id,
                })
            ]

    def action_payslip_done(self):
        res = super().action_payslip_done()

        installment_model = self.env['hr.employee.loan.installment']

        for slip in self:
            installments = installment_model._get_installments_for_payslip(
                slip.employee_id,
                slip.date_from,
                slip.date_to
            )

            if not installments:
                continue

            # ✅ Montant total à déduire
            remaining_amount = sum(installments.mapped('amount'))

            for inst in installments:
                if remaining_amount <= 0:
                    break

                inst_amount = inst.amount

                if remaining_amount >= inst_amount:
                    # ✅ Paiement total
                    inst.action_paid(date_payment=slip.date_to)
                    inst.write({
                        'payslip_id': slip.id,
                        'is_deducted': True
                    })
                    remaining_amount -= inst_amount

                else:
                    # ✅ Paiement partiel CORRECT
                    ratio = remaining_amount / inst_amount

                    inst.write({
                        'paid_principal_amount': inst.principal_amount * ratio,
                        'paid_interest_amount': inst.interest_amount * ratio,
                        'date_payment': slip.date_to,
                        'payslip_id': slip.id,
                        'is_deducted': True
                    })

                    remaining_amount = 0

        return res