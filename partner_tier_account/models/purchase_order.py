from odoo import api, fields, models


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    is_brs_tax = fields.Boolean(
        string='BRS 5% détecté',
        compute='_compute_is_brs_tax',
        store=False,
    )

    @api.depends(
        'order_line.taxes_id',
        'order_line.taxes_id.amount',
        'order_line.taxes_id.tax_group_id',
        'order_line.taxes_id.tax_group_id.name',
        'order_line.taxes_id.name',
    )
    def _compute_is_brs_tax(self):
        for order in self:
            is_brs = False
            for line in order.order_line:
                taxes = line.taxes_id or self.env['account.tax']
                for tax in taxes:
                    if self._is_brs_tax(tax):
                        is_brs = True
                        break
                if is_brs:
                    break
            order.is_brs_tax = is_brs

    @api.onchange('partner_id', 'partner_id.cofi', 'company_id')
    def _onchange_gainde_refresh_line_taxes(self):
        for order in self:
            if order.order_line:
                order.order_line._gainde_onchange_default_tax_for_cofi()
                if hasattr(order.order_line, '_gainde_apply_tax_rules'):
                    order.order_line._gainde_apply_tax_rules()

    @staticmethod
    def _is_brs_tax(tax):
        if not tax:
            return False
        if tax.amount_type == 'percent' and abs(tax.amount - 5.0) < 0.0001:
            return True
        group_name = (tax.tax_group_id.name or '').lower()
        tax_name = (tax.name or '').lower()
        return 'brs' in group_name or 'brs' in tax_name


class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    @api.onchange(
        'product_id',
        'order_id',
        'company_id',
        'order_id.partner_id',
        'order_id.partner_id.cofi',
    )
    def _gainde_onchange_default_tax_for_cofi(self):
        for line in self:
            order = line.order_id
            partner = order.partner_id if order else False
            if not partner or 'cofi' not in partner._fields:
                continue
            cofi = (partner.cofi or '').strip()
            tax_18 = line._get_default_purchase_tax_18()
            if not cofi or cofi[0] != '2':
                if tax_18 and tax_18.id in line.taxes_id.ids:
                    new_tax_ids = [tax.id for tax in line.taxes_id if tax.id != tax_18.id]
                    line.taxes_id = [(6, 0, new_tax_ids)]
                continue
            if tax_18:
                line.taxes_id = tax_18

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        for line, vals in zip(lines, vals_list):
            # Respect manual taxes selected in the form payload.
            if 'taxes_id' in vals:
                continue
            line._gainde_apply_default_tax_for_cofi()
        return lines

    def write(self, vals):
        res = super().write(vals)
        if self.env.context.get('skip_gainde_default_tax'):
            return res
        # Recompute only when tax-driving fields change, and keep explicit user taxes.
        trigger_fields = {'product_id', 'company_id', 'order_id'}
        if 'taxes_id' not in vals and trigger_fields.intersection(vals.keys()):
            self._gainde_apply_default_tax_for_cofi()
        return res

    def _gainde_apply_default_tax_for_cofi(self):
        for line in self:
            order = line.order_id
            partner = order.partner_id if order else False
            if not partner or 'cofi' not in partner._fields:
                continue
            cofi = (partner.cofi or '').strip()
            tax_18 = line._get_default_purchase_tax_18()
            if not cofi or cofi[0] != '2':
                if tax_18 and tax_18.id in line.taxes_id.ids:
                    new_tax_ids = [tax.id for tax in line.taxes_id if tax.id != tax_18.id]
                    line.with_context(skip_gainde_default_tax=True).write({
                        'taxes_id': [(6, 0, new_tax_ids)],
                    })
                continue
            if line.taxes_id:
                continue
            if tax_18:
                line.with_context(skip_gainde_default_tax=True).write({
                    'taxes_id': [(6, 0, tax_18.ids)],
                })

    def _get_default_purchase_tax_18(self):
        company = self.company_id or self.order_id.company_id or self.env.company
        return self.env['account.tax'].search([
            ('type_tax_use', '=', 'purchase'),
            ('amount_type', '=', 'percent'),
            ('amount', '=', 18),
            ('company_id', '=', company.id),
            ('active', '=', True),
        ], limit=1)
