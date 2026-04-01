from contextlib import contextmanager

from odoo import api, fields, models


class AccountMove(models.Model):
    _inherit = 'account.move'

    tier_account = fields.Char(
        string='Compte Tiers',
        related='partner_id.tier_account',
        readonly=True,
    )

    entry_sequence = fields.Char(
        string='Numéro de saisie',
        copy=False,
        readonly=True,
    )

    is_brs_tax = fields.Boolean(
        string='BRS 5% détecté',
        compute='_compute_is_brs_tax',
        store=False,
    )

    brs_withholding_adjusted = fields.Boolean(
        string='Écriture BRS ajustée',
        copy=False,
        readonly=True,
    )

    @api.model_create_multi
    def create(self, vals_list):
        seq = self.env['ir.sequence']
        for vals in vals_list:
            if vals.get('entry_sequence'):
                continue

            move_type = vals.get('move_type') or self.env.context.get('default_move_type') or 'entry'
            # Besoin: champ de séquence automatique sur les factures.
            if move_type == 'entry':
                continue

            sequence_date = vals.get('invoice_date') or vals.get('date')
            vals['entry_sequence'] = seq.next_by_code(
                'account.move.entry.sequence',
                sequence_date=sequence_date,
            )
        return super().create(vals_list)

    @api.depends(
        'invoice_line_ids.tax_ids',
        'invoice_line_ids.tax_ids.amount',
        'invoice_line_ids.tax_ids.tax_group_id',
        'invoice_line_ids.tax_ids.tax_group_id.name',
        'invoice_line_ids.tax_ids.name',
    )
    def _compute_is_brs_tax(self):
        for move in self:
            is_brs = False
            for line in move.invoice_line_ids:
                taxes = line.tax_ids
                for tax in taxes:
                    if self._is_brs_tax(tax):
                        is_brs = True
                        break
                if is_brs:
                    break
            move.is_brs_tax = is_brs

    @api.depends_context('lang')
    @api.depends(
        'invoice_line_ids.currency_rate',
        'invoice_line_ids.tax_base_amount',
        'invoice_line_ids.tax_line_id',
        'invoice_line_ids.price_total',
        'invoice_line_ids.price_subtotal',
        'invoice_payment_term_id',
        'partner_id',
        'currency_id',
    )
    def _compute_tax_totals(self):
        super()._compute_tax_totals()
        for move in self:
            if not move.is_invoice(include_receipts=True) or move.move_type != 'in_invoice':
                continue
            partner = move.partner_id
            if not partner or 'cofi' not in partner._fields:
                continue
            cofi = (partner.cofi or '').strip()
            if not cofi or cofi[0] != '1':
                continue
            if not move.tax_totals:
                continue
            tax_lines = move.line_ids.filtered(
                lambda line: line.tax_line_id and self._is_brs_withholding_tax(line.tax_line_id)
            )
            if not tax_lines:
                continue

            tax_amount_currency = abs(sum(tax_lines.mapped('amount_currency')))
            tax_amount = abs(sum(tax_lines.mapped('balance')))
            total_amount_currency = move.amount_total
            total_amount = abs(move.amount_total_signed)

            net_amount_currency = abs(move.amount_total)
            net_amount = net_amount_currency
            gross_amount_currency = net_amount_currency + tax_amount_currency
            gross_amount = net_amount + tax_amount

            move.tax_totals['base_amount_currency'] = gross_amount_currency
            move.tax_totals['base_amount'] = gross_amount
            move.tax_totals['tax_amount_currency'] = tax_amount_currency
            move.tax_totals['tax_amount'] = tax_amount
            move.tax_totals['total_amount_currency'] = total_amount_currency
            move.tax_totals['total_amount'] = total_amount

            for subtotal in move.tax_totals.get('subtotals', []):
                subtotal['base_amount_currency'] = gross_amount_currency
                subtotal['base_amount'] = gross_amount
                subtotal['tax_amount_currency'] = tax_amount_currency
                subtotal['tax_amount'] = tax_amount
                for group in subtotal.get('tax_groups', []):
                    group['tax_amount_currency'] = abs(group.get('tax_amount_currency', 0.0))
                    group['tax_amount'] = abs(group.get('tax_amount', 0.0))
                    group['base_amount_currency'] = gross_amount_currency
                    group['base_amount'] = gross_amount
                    group['display_base_amount_currency'] = gross_amount_currency
                    group['display_base_amount'] = gross_amount

    @api.depends(
        'line_ids.matched_debit_ids.debit_move_id.move_id.origin_payment_id.is_matched',
        'line_ids.matched_debit_ids.debit_move_id.move_id.line_ids.amount_residual',
        'line_ids.matched_debit_ids.debit_move_id.move_id.line_ids.amount_residual_currency',
        'line_ids.matched_credit_ids.credit_move_id.move_id.origin_payment_id.is_matched',
        'line_ids.matched_credit_ids.credit_move_id.move_id.line_ids.amount_residual',
        'line_ids.matched_credit_ids.credit_move_id.move_id.line_ids.amount_residual_currency',
        'line_ids.balance',
        'line_ids.currency_id',
        'line_ids.amount_currency',
        'line_ids.amount_residual',
        'line_ids.amount_residual_currency',
        'line_ids.payment_id.state',
        'line_ids.full_reconcile_id',
        'state',
    )
    def _compute_amount(self):
        super()._compute_amount()
        for move in self:
            if not move.is_invoice(True) or move.move_type != 'in_invoice':
                continue
            partner = move.partner_id
            if not partner or 'cofi' not in partner._fields:
                continue
            cofi = (partner.cofi or '').strip()
            if not cofi or cofi[0] != '1':
                continue
            tax_lines = move.line_ids.filtered(
                lambda line: line.tax_line_id and self._is_brs_withholding_tax(line.tax_line_id)
            )
            if not tax_lines:
                continue

            tax_amount = abs(move.amount_tax)
            gross_amount = move.amount_total + tax_amount

            move.amount_tax = tax_amount
            move.amount_untaxed = gross_amount

            if move.is_inbound(include_receipts=True):
                move.amount_tax_signed = -tax_amount
                move.amount_untaxed_signed = -gross_amount
                move.amount_untaxed_in_currency_signed = -gross_amount
            else:
                move.amount_tax_signed = tax_amount
                move.amount_untaxed_signed = gross_amount
                move.amount_untaxed_in_currency_signed = gross_amount

    def _post(self, soft=True):
        res = super()._post(soft=soft)
        self.with_context(
            allow_posted_brs_adjustment=True,
            check_move_validity=False,
        )._apply_brs_withholding_entry_adjustment()
        return res

    def action_post(self):
        return super().action_post()

    def write(self, vals):
        res = super().write(vals)
        if self.env.context.get('skip_brs_adjustment'):
            return res

        draft_moves = self.filtered(
            lambda move: move.state == 'draft'
            and move.move_type == 'in_invoice'
        )
        if draft_moves:
            draft_moves.with_context(skip_brs_adjustment=True)._apply_brs_withholding_entry_adjustment()
        return res

    @contextmanager
    @api.model
    def _sync_dynamic_lines(self, container):
        with super()._sync_dynamic_lines(container):
            yield
        if self.env.context.get('skip_brs_adjustment'):
            return
        moves = container.get('records', self)
        moves = moves.filtered(
            lambda move: move.state == 'draft'
            and move.move_type == 'in_invoice'
        )
        if moves:
            moves.with_context(skip_brs_adjustment=True)._apply_brs_withholding_entry_adjustment()

    def _apply_brs_withholding_entry_adjustment(self):
        for move in self:
            if move.state != 'draft' and not self.env.context.get('allow_posted_brs_adjustment'):
                continue
            if move.move_type != 'in_invoice':
                continue

            partner = move.partner_id
            if not partner or 'cofi' not in partner._fields:
                continue
            cofi = (partner.cofi or '').strip()
            if not cofi or cofi[0] != '1':
                continue

            tax_lines = move.line_ids.filtered(
                lambda line: line.tax_line_id and self._is_brs_withholding_tax(line.tax_line_id)
            )
            if not tax_lines:
                continue

            payable_lines = move.line_ids.filtered(
                lambda line: self._is_payable_account(line.account_id) and not line.display_type
            )
            if not payable_lines:
                continue

            payable_line = max(payable_lines, key=lambda l: abs(l.balance))

            # Base lignes (produits) = brut (net + retenue BRS)
            base_lines = move.invoice_line_ids.filtered(lambda line: not line.display_type)
            net_total = abs(move.amount_total)

            # Lignes taxes = au crédit
            tax_total = 0.0
            for line in tax_lines:
                tax_amount = abs(line.balance) or abs(line.amount_currency) or 0.0
                tax_total += tax_amount
                line.with_context(check_move_validity=False).write({
                    'balance': -tax_amount,
                    'amount_currency': -(abs(line.amount_currency) or tax_amount),
                })

            # Base au débit (montant brut), taxe au crédit, payable = base - taxe.
            base_balances = []
            gross_total = net_total + tax_total
            for line in base_lines:
                expected = line.price_subtotal
                if net_total:
                    expected = (line.price_subtotal / net_total) * gross_total
                else:
                    expected = gross_total
                base_balances.append(expected)
                line.with_context(check_move_validity=False).write({
                    'balance': expected,
                    'amount_currency': expected,
                })

            expected_payable_balance = -net_total
            payable_vals = {
                'balance': expected_payable_balance,
                'amount_currency': expected_payable_balance,
            }
            payable_line.with_context(check_move_validity=False).write(payable_vals)
            move.with_context(check_move_validity=False).brs_withholding_adjusted = True

    @staticmethod
    def _is_payable_account(account):
        if not account:
            return False
        account_type = getattr(account, 'account_type', False)
        if account_type:
            return account_type == 'liability_payable'
        internal_type = getattr(account, 'internal_type', False)
        if internal_type:
            return internal_type == 'payable'
        internal_group = getattr(account, 'internal_group', False)
        return internal_group == 'liability'

    @staticmethod
    def _is_brs_withholding_tax(tax):
        if not tax:
            return False
        name = (tax.name or '').lower().replace(' ', '')
        group_name = (tax.tax_group_id.name or '').lower()
        if 'brs' in group_name or 'brs' in name:
            return True
        if tax.amount_type == 'percent' and abs(tax.amount - 5.0) < 0.0001:
            return True
        return '5%t' in name or '5%s' in name

    @staticmethod
    def _is_brs_tax(tax):
        if not tax:
            return False
        if tax.amount_type == 'percent' and abs(tax.amount - 5.0) < 0.0001:
            return True
        group_name = (tax.tax_group_id.name or '').lower()
        tax_name = (tax.name or '').lower()
        return 'brs' in group_name or 'brs' in tax_name
