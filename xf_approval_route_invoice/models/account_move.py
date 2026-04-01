# -*- coding: utf-8 -*-
from odoo.exceptions import UserError

from odoo import models, fields, api, _
from odoo.addons.xf_approval_route_base.models import selection


class Invoice(models.Model):
    _name = 'account.move'
    _inherit = ['account.move', 'approval.route.document']

    use_approval_route = fields.Selection(
        string="Use Approval Route",
        selection=selection.USE_APPROVAL_ROUTE,
        compute='_compute_use_approval_route',
    )
    approval_route_id = fields.Many2one(
        readonly=True,
    )
    state = fields.Selection(
        selection_add=[
            ('to approve', 'To Approve'),
            ('rejected', 'Rejected'),
            ('posted',),
        ],
        ondelete={
            'to approve': 'set default',
            'rejected': 'set default',
        }
    )
    all_used_products = fields.Many2many(
        string='All Used Products',
        comodel_name='product.product',
        compute='_compute_all_used_products',
    )
    all_used_analytic_accounts = fields.Many2many(
        string='All Used Analytic Accounts',
        comodel_name='account.analytic.account',
        compute='_compute_all_used_analytic_accounts',
    )

    @api.depends('move_type', 'company_id')
    def _compute_use_approval_route(self):
        for move in self:
            use_approval_route = 'no'
            if move.move_type in ('out_invoice', 'out_refund'):
                use_approval_route = move.company_id.use_approval_route_customer_invoice
            if move.move_type in ('in_invoice', 'in_refund'):
                use_approval_route = move.company_id.use_approval_route_vendor_bill
            move.use_approval_route = use_approval_route

    @api.depends('line_ids.product_id')
    def _compute_all_used_products(self):
        for move in self:
            move.all_used_products = move.line_ids.mapped('product_id')

    @api.depends('line_ids.analytic_distribution')
    def _compute_all_used_analytic_accounts(self):
        for move in self:
            analytic_account_ids = []
            for line in move.line_ids:
                if line.analytic_distribution:
                    aa_keys = line.analytic_distribution.keys()
                    for aa_key in aa_keys:
                        aa_ids = aa_key.split(',')
                        analytic_account_ids += list(map(int, aa_ids))
            move.all_used_analytic_accounts = list(set(analytic_account_ids))

    def _track_subtype(self, init_values):
        self.ensure_one()
        if init_values.get('state') == 'to approve':
            if self.state == 'posted':
                return self.env.ref('xf_approval_route_invoice.mt_invoice_approved_and_posted')
            if self.state == 'cancel':
                return self.env.ref('xf_approval_route_invoice.mt_invoice_cancelled')
            if self.state == 'rejected':
                return self.env.ref('xf_approval_route_invoice.mt_invoice_rejected')
        return super(Invoice, self)._track_subtype(init_values)

    def button_approve_invoice(self):
        for move in self:
            if move.current_approval_stage_id:
                move._action_approve()
                if move._is_fully_approved():
                    super(Invoice, move).action_post()
            else:
                # Do default behaviour if approval route is not set
                super(Invoice, move).action_post()
        return {}

    def button_reject_invoice(self):
        for move in self:
            if move.current_approval_stage_id:
                move._action_reject()
                move.write({'state': 'rejected'})

    def action_post(self):
        for move in self:
            if move.state == 'draft' and move.use_approval_route != 'no' and move.approval_route_id:
                # Generate approval workflow and send invoice to approve
                move.generate_approval_route()
                if move.next_approval_stage_id:
                    # If approval route was generated and there is next approver mark the invoice "to approve"
                    move.write({'state': 'to approve'})
                    # And send request to approve
                    move._action_send_to_approve()
                else:
                    # If there are no approvers, do default behaviour and move invoice to the "Posted" state
                    super(Invoice, move).action_post()
            else:
                # Do default behaviour if approval route is not set
                # or approval functionality is disabled
                super(Invoice, move).action_post()
        return True

    def button_draft(self):
        """
        Clear approval stages and reset invoice
        :return:
        """
        self._clear_approval_stages()
        return super(Invoice, self).button_draft()

    def button_cancel(self):
        # Shortcut to move from posted to cancelled directly. This is useful for E-invoices that must not be changed
        # when sent to the government.
        moves_to_reset_draft = self.filtered(lambda x: x.state == 'posted')
        if moves_to_reset_draft:
            moves_to_reset_draft.button_draft()

        if any(move.state not in ('draft', 'to approve', 'rejected') for move in self):
            raise UserError(_("Only draft journal entries can be cancelled."))

        self.write({'auto_post': 'no', 'state': 'cancel'})

    def _can_be_confirmed(self):
        self.ensure_one()
        return self.state in {'draft', 'sent', 'to approve'}
