# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import AccessError


class HrExpenseSheet(models.Model):
    _name = 'hr.expense.sheet'
    _inherit = ['hr.expense.sheet', 'approval.route.document']

    use_approval_route = fields.Selection(
        string="Use Approval Route",
        related='company_id.use_approval_route_expense',
    )
    approval_route_id = fields.Many2one(
        readonly=True,
    )
    all_used_analytic_accounts = fields.Many2many(
        string='All Used Analytic Accounts',
        comodel_name='account.analytic.account',
        compute='_compute_all_used_analytic_accounts',
    )

    @api.depends('expense_line_ids.analytic_distribution')
    def _compute_all_used_analytic_accounts(self):
        for sheet in self:
            analytic_account_ids = []
            for line in sheet.expense_line_ids:
                if line.analytic_distribution:
                    aa_keys = line.analytic_distribution.keys()
                    for aa_key in aa_keys:
                        aa_ids = aa_key.split(',')
                        analytic_account_ids += list(map(int, aa_ids))
            sheet.all_used_analytic_accounts = list(set(analytic_account_ids))

    def action_submit_sheet(self):
        for sheet in self:
            if sheet.state == 'draft' and sheet.use_approval_route != 'no' and sheet.approval_route_id:
                # Generate approval workflow and send expense sheet to approve
                sheet.generate_approval_route()
                if sheet.next_approval_stage_id:
                    # If approval route was generated and there is next approver mark the sheet as submitted
                    sheet.write({'state': 'submit'})
                    # And send request to approve
                    sheet._action_send_to_approve()
                else:
                    # If there are no approvers, do default behaviour
                    super(HrExpenseSheet, sheet).action_submit_sheet()
            else:
                # Do default behaviour if approval route is not set
                # or approval functionality is disabled
                super(HrExpenseSheet, sheet).action_submit_sheet()

    @api.depends_context('uid')
    @api.depends('employee_id', 'approval_route_id', 'current_approval_stage_id')
    def _compute_can_approve(self):
        for sheet in self:
            if sheet.use_approval_route != 'no' and sheet.approval_route_id and sheet.is_under_approval:
                approvers = sheet.current_approval_stage_id.user_ids
                names = approvers.mapped('name')
                reason = _('This %s must be approved/refused by %s') % (self._description, ' or '.join(names))
                sheet.can_approve = sheet.is_current_approver
                sheet.cannot_approve_reason = reason
            else:
                super(HrExpenseSheet, sheet)._compute_can_approve()

    def _check_can_approve(self):
        if self.use_approval_route != 'no' and self.approval_route_id and self.is_under_approval:
            # If dynamic approval workflow is enabled
            if not self._is_fully_approved():
                approvers = self.current_approval_stage_id.user_ids
                names = approvers.mapped('name')
                # Check is the current user is approver for the current stage
                if self.env.user not in approvers and not self.env.is_superuser():
                    raise AccessError(_('This %s must be approved by %s') % (self._description, ' or '.join(names)))
        else:
            return super(HrExpenseSheet, self)._check_can_approve()

    def action_approve_expense_sheets(self):
        if self.use_approval_route != 'no' and self.approval_route_id and self.is_under_approval:
            self._action_approve()
            if self._is_fully_approved():
                return super(HrExpenseSheet, self).action_approve_expense_sheets()
        else:
            # Do default behaviour if approval route is not set
            return super(HrExpenseSheet, self).action_approve_expense_sheets()

    def action_reset_expense_sheets(self):
        """
        Clear approval stages and reset expense reports
        :return:
        """
        self._clear_approval_stages()
        return super(HrExpenseSheet, self).action_reset_expense_sheets()
