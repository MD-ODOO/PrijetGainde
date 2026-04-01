# -*- coding: utf-8 -*-

from odoo import models, fields, api


class EmployeeLoanRequest(models.Model):
    _name = 'hr.employee.loan.request'
    _inherit = ['hr.employee.loan.request', 'approval.route.document']

    use_approval_route = fields.Selection(
        string="Use Approval Route",
        related='company_id.use_approval_route_loan',
    )
    approval_route_id = fields.Many2one(
        readonly=True,
    )

    def action_submit(self):
        for record in self:
            if record.state == 'draft' and record.use_approval_route != 'no' and record.approval_route_id:
                # Generate approval workflow and send loan request to approve
                record.generate_approval_route()
                if record.next_approval_stage_id:
                    # If approval route was generated and there is next approver mark the sheet as submitted
                    super(EmployeeLoanRequest, record).action_submit()
                    # And send request to approve
                    record._action_send_to_approve()
                else:
                    # If there are no approvers, do default behaviour
                    super(EmployeeLoanRequest, record).action_submit()
            else:
                # Do default behaviour if approval route is not set
                # or approval functionality is disabled
                super(EmployeeLoanRequest, record).action_submit()

    @api.depends_context('uid')
    @api.depends('state', 'use_approval_route', 'approval_route_id', 'current_approval_stage_id')
    def _compute_can_approve(self):
        for record in self:
            if record.use_approval_route != 'no' and record.approval_route_id and record.is_under_approval:
                record.can_approve = record.is_current_approver
            else:
                super(EmployeeLoanRequest, record)._compute_can_approve()

    def action_approve(self):
        for record in self:
            if record.use_approval_route != 'no' and record.approval_route_id and record.is_under_approval:
                record._action_approve()
                if record._is_fully_approved():
                    super(EmployeeLoanRequest, record).action_approve()
            else:
                # Do default behaviour if approval route is not set
                return super(EmployeeLoanRequest, record).action_approve()

    def action_reject(self):
        for record in self:
            if record.use_approval_route != 'no' and record.approval_route_id and record.is_under_approval:
                record._action_reject()
                if record._is_fully_approved():
                    super(EmployeeLoanRequest, record).action_reject()
            else:
                # Do default behaviour if approval route is not set
                super(EmployeeLoanRequest, record).action_reject()

    def action_reset(self):
        """
        Clear approval stages and reset expense reports
        :return:
        """
        self._clear_approval_stages()
        return super(EmployeeLoanRequest, self).action_reset()
