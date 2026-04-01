# -*- coding: utf-8 -*-
from odoo.addons.xf_approval_route_base.models import selection

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class AccountPayment(models.Model):
    _name = 'account.payment'
    _inherit = ['account.payment', 'approval.route.document']

    _move_id_validate_states = ('draft', 'canceled', 'to approve')

    state = fields.Selection(
        selection_add=[
            ('to approve', 'To Approve'),
            ('in_process',),
        ],
        ondelete={
            'to approve': 'set default',
        }
    )

    use_approval_route = fields.Selection(
        string="Use Approval Route",
        selection=selection.USE_APPROVAL_ROUTE,
        compute='_compute_use_approval_route',
    )
    approval_route_id = fields.Many2one(
        readonly=True,
    )

    @api.depends('partner_type', 'journal_id')
    def _compute_use_approval_route(self):
        for payment in self:
            use_approval_route = 'no'
            if payment.partner_type == 'supplier':
                use_approval_route = payment.company_id.use_approval_route_supplier_payment
            if payment.partner_type == 'customer':
                use_approval_route = payment.company_id.use_approval_route_customer_payment
            payment.use_approval_route = use_approval_route

    def _track_subtype(self, init_values):
        self.ensure_one()
        if init_values.get('state') == 'to approve':
            if self.state == 'in_process':
                return self.env.ref('xf_approval_route_payment.mt_payment_approved')
            if self.state == 'canceled':
                return self.env.ref('xf_approval_route_payment.mt_payment_cancelled')
            if self.state == 'rejected':
                return self.env.ref('xf_approval_route_payment.mt_payment_rejected')
        return super(AccountPayment, self)._track_subtype(init_values)

    @api.constrains('state', 'move_id')
    def _check_move_id(self):
        for payment in self:
            if (
                    payment.state not in self._move_id_validate_states
                    and not payment.move_id
                    and payment.outstanding_account_id
            ):
                raise ValidationError(_("A payment with an outstanding account cannot be confirmed without having a journal entry."))

    def action_cancel(self):
        self._clear_approval_stages()
        super(AccountPayment, self).action_cancel()

    def action_post(self):
        for payment in self:
            if payment.state == 'draft' and payment.use_approval_route != 'no' and payment.approval_route_id:
                # Generate approval workflow and send payment to approve
                payment.generate_approval_route()
                if payment.next_approval_stage_id:
                    # If approval route was generated and there is next approver,
                    # mark the payment as 'to approve'
                    payment.write({'state': 'to approve'})
                    # And send request to approve
                    payment._action_send_to_approve()
                else:
                    # If there are no approvers, do default behaviour
                    super(AccountPayment, payment).action_post()
                    payment._mark_as_in_process()
            else:
                # Do default behaviour, if approval route is not set
                # or approval functionality is disabled
                super(AccountPayment, payment).action_post()
                payment._mark_as_in_process()

    def action_approve(self):
        for payment in self:
            if payment.current_approval_stage_id:
                payment._action_approve()
                if payment._is_fully_approved():
                    # If fully approved, do default behaviour
                    super(AccountPayment, payment).action_post()
                    payment._mark_as_in_process()
            else:
                # Do default behaviour if approval route is not set
                super(AccountPayment, payment).action_post()
                payment._mark_as_in_process()

    def _mark_as_in_process(self):
        """
        This is a small turnaround to be mark a payment as "in_process"
        as default action_post filters payments by state, and we don't want duplicate the method to inherit it
        :return:
        """
        self.filtered(lambda pay: pay.state in {False, 'draft', 'to approve'}).write({'state': 'in_process'})

    def action_draft(self):
        """
        Clear approval stages and reset PO
        :return:
        """
        self._clear_approval_stages()
        return super(AccountPayment, self).action_draft()

    def _compute_show_reset_to_draft_button(self):
        super()._compute_show_reset_to_draft_button()
        for payment in self:
            if payment.state == 'rejected':
                payment.show_reset_to_draft_button = True


class AccountPaymentRegister(models.TransientModel):
    _inherit = 'account.payment.register'

    use_approval_route = fields.Selection(
        string="Use Approval Route",
        selection=selection.USE_APPROVAL_ROUTE,
        compute='_compute_use_approval_route',
    )
    approval_route_id = fields.Many2one(
        string='Approval Route',
        comodel_name='approval.route',
        domain=lambda self: [('model', '=', 'account.payment')]
    )

    @api.depends('partner_type', 'journal_id')
    def _compute_use_approval_route(self):
        for payment in self:
            use_approval_route = 'no'
            if payment.partner_type == 'supplier':
                use_approval_route = payment.company_id.use_approval_route_supplier_payment
            if payment.partner_type == 'customer':
                use_approval_route = payment.company_id.use_approval_route_customer_payment
            payment.use_approval_route = use_approval_route

    def _create_payment_vals_from_wizard(self, batch_result):
        payment_vals = super(AccountPaymentRegister, self)._create_payment_vals_from_wizard(batch_result)
        if self.approval_route_id:
            payment_vals['approval_route_id'] = self.approval_route_id.id
        return payment_vals
