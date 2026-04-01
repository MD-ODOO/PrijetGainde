# from odoo import models, api, Command

# class HrPayslip(models.Model):
#     _inherit = 'hr.payslip'

#     @api.depends('employee_id', 'contract_id', 'date_from', 'date_to', 'struct_id')
#     def _compute_input_line_ids(self):
#         super()._compute_input_line_ids()

#         installment_model = self.env['hr.employee.loan.installment']
#         input_type = self.env.ref('xf_loan.input_type_employee_loan', raise_if_not_found=False)

#         for slip in self:
#             if not slip.employee_id or not slip.contract_id or not input_type:
#                 continue

#             installments = installment_model._get_installments_for_payslip(
#                 slip.employee_id,
#                 slip.date_from,
#                 slip.date_to
#             )

#             if not installments:
#                 continue

#             # ✅ CORRECTION ICI
#             amount = installments[:1]._compute_loan_deduction_amount(slip, installments)

#             # supprimer anciennes lignes LOAN
#             existing = slip.input_line_ids.filtered(
#                 lambda l: l.input_type_id.id == input_type.id
#             )

#             commands = [Command.unlink(line.id) for line in existing]

#             # ajouter nouvelle ligne
#             commands.append(Command.create({
#                 'name': 'Loan Deduction',
#                 'amount': amount,
#                 'input_type_id': input_type.id,
#             }))

#             slip.input_line_ids = commands

#     def action_payslip_done(self):
#         res = super().action_payslip_done()

#         installment_model = self.env['hr.employee.loan.installment']

#         for slip in self:
#             installments = installment_model._get_installments_for_payslip(
#                 slip.employee_id,
#                 slip.date_from,
#                 slip.date_to
#             )

#             if not installments:
#                 continue

#             remaining_amount = installments[:1]._compute_loan_deduction_amount(slip, installments)

#             for inst in installments:
#                 if remaining_amount <= 0:
#                     break

#                 inst_amount = inst.amount

#                 if remaining_amount >= inst_amount:
#                     inst.action_paid(date_payment=slip.date_to)
#                     inst.write({
#                         'payslip_id': slip.id,
#                         'is_deducted': True
#                     })
#                     remaining_amount -= inst_amount
#                 else:
#                     # paiement partiel
#                     inst.write({
#                         'paid_principal_amount': remaining_amount,
#                         'date_payment': slip.date_to,
#                         'payslip_id': slip.id,
#                         'is_deducted': True
#                     })
#                     remaining_amount = 0

#         return res
