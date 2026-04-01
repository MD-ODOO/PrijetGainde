# -*- coding: utf-8 -*-
from odoo import models, fields, api, _


class SaleOrder(models.Model):
    _name = 'sale.order'
    _inherit = ['sale.order', 'approval.route.document']

    use_approval_route = fields.Selection(
        string="Use Approval Route",
        related='company_id.use_approval_route_sale',
    )
    approval_route_id = fields.Many2one(
        readonly=True,
    )
    state = fields.Selection(
        selection_add=[
            ('to approve', 'To Approve'),
            ('sale',),
        ],
        ondelete={
            'to approve': 'set default',
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

    @api.depends('order_line.product_id')
    def _compute_all_used_products(self):
        for order in self:
            order.all_used_products = order.order_line.mapped('product_id')

    @api.depends('order_line.analytic_distribution')
    def _compute_all_used_analytic_accounts(self):
        for order in self:
            analytic_account_ids = []
            for line in order.order_line:
                if line.analytic_distribution:
                    aa_keys = line.analytic_distribution.keys()
                    for aa_key in aa_keys:
                        aa_ids = aa_key.split(',')
                        analytic_account_ids += list(map(int, aa_ids))
            order.all_used_analytic_accounts = list(set(analytic_account_ids))

    def _track_subtype(self, init_values):
        self.ensure_one()
        if init_values.get('state') == 'to approve' and self.state == 'cancel':
            return self.env.ref('xf_approval_route_sale.mt_order_cancelled')
        return super(SaleOrder, self)._track_subtype(init_values)

    def button_approve(self):
        for order in self:
            if order.current_approval_stage_id:
                order._action_approve()
                if order._is_fully_approved():
                    super(SaleOrder, order).action_confirm()
            else:
                # Do default behaviour if approval route is not set
                super(SaleOrder, order).action_confirm()
        return {}

    def action_confirm(self):
        for order in self:
            if order.state in ('draft', 'sent') and order.use_approval_route != 'no' and order.approval_route_id:
                # Generate approval workflow and send SO to approve
                order.generate_approval_route()
                if order.next_approval_stage_id:
                    # If approval route was generated and there is next approver mark the order "to approve"
                    order.write({'state': 'to approve'})
                    # And send request to approve
                    order._action_send_to_approve()
                else:
                    # If there are no approvers, do default behaviour and move SO to the "Sale Order" state
                    super(SaleOrder, order).action_confirm()
            else:
                # Do default behaviour if approval route is not set
                # or approval functionality is disabled
                super(SaleOrder, order).action_confirm()
        return True

    def action_draft(self):
        """
        Clear approval stages and reset SO
        :return:
        """
        self._clear_approval_stages()
        return super(SaleOrder, self).action_draft()

    def _confirmation_error_message(self):
        """ Return whether order can be confirmed or not if not then return error message. """
        self.ensure_one()
        if self.state not in {'draft', 'sent', 'to approve'}:
            return _("Some orders are not in a state requiring confirmation.")
        if any(
                not line.display_type
                and not line.is_downpayment
                and not line.product_id
                for line in self.order_line
        ):
            return _("A line on these orders missing a product, you cannot confirm it.")

        return False
