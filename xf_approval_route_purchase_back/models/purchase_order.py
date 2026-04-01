# -*- coding: utf-8 -*-
from odoo import models, fields, api


class PurchaseOrder(models.Model):
    _name = 'purchase.order'
    _inherit = ['purchase.order', 'approval.route.document']

    use_approval_route = fields.Selection(
        string="Use Approval Route",
        related='company_id.use_approval_route_purchase',
    )
    approval_route_id = fields.Many2one(
        readonly=True,
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

    def button_approve(self, force=False):
        for order in self:
            do_super_approve = True
            if order.state in ('draft', 'sent') and order.approval_route_id:
                # Generate approval route and send PO to approve
                order.generate_approval_route()
                if order.next_approval_stage_id:
                    do_super_approve = False
                    # If approval route is generated and there is next approver mark the order "to approve"
                    order.write({'state': 'to approve'})
                    # And send request to approve
                    order._action_send_to_approve()
            elif order.current_approval_stage_id:
                order._action_approve()
                do_super_approve = order._is_fully_approved()
            if do_super_approve:
                super(PurchaseOrder, order).button_approve(force)
        return {}

    def _approval_allowed(self):
        return True

    def button_draft(self):
        """
        Clear approval stages and reset PO
        :return:
        """
        self._clear_approval_stages()
        return super(PurchaseOrder, self).button_draft()
