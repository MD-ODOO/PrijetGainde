from odoo import models, api, fields, _
from odoo.tools import date_utils

class AccountMove(models.Model):
    _inherit = "account.move"

    treasury_payment_ids = fields.One2many("treasury.payment", "invoice_id", string="Décaissements")
    treasury_payment_priority = fields.Selection(
        [("0", "Basse"), ("1", "Normale"), ("2", "Haute"), ("3", "Urgente")],
        compute="_compute_treasury_payment_info",
        string="Priorité trésorerie",
        store=False,
    )
    treasury_planned_payment_date = fields.Date(
        compute="_compute_treasury_payment_info",
        string="Date prévue trésorerie",
        store=False,
    )
    treasury_payment_channel = fields.Selection(
        [("transfer", "Virement"), ("cheque", "Chèque"), ("cash", "Espèces")],
        compute="_compute_treasury_payment_info",
        string="Mode trésorerie",
        store=False,
    )
    vendor_due_days = fields.Integer(
        string="Jours avant échéance",
        compute="_compute_vendor_due_days",
        store=False,
    )
    vendor_is_overdue = fields.Boolean(
        string="En retard",
        compute="_compute_vendor_due_days",
        store=False,
    )
    vendor_due_display = fields.Char(
        string="Délai de règlement",
        compute="_compute_vendor_due_days",
        store=False,
    )
    vendor_due_color = fields.Integer(
        string="Couleur délai",
        compute="_compute_vendor_due_days",
        store=False,
    )

    def action_post(self):
        """Post vendor bills and auto-create treasury payment records so all confirmed bills appear in the treasury view."""
        res = super().action_post()

        bills = self.filtered(
            lambda m: m.move_type == "in_invoice"
            and m.state == "posted"
            and m.payment_state != "paid"
        )
        TreasuryPayment = self.env["treasury.payment"]
        for bill in bills:
            if TreasuryPayment.search_count([("invoice_id", "=", bill.id)]):
                continue  # already synchronized
            TreasuryPayment.create({
                "invoice_id": bill.id,
                "partner_id": bill.partner_id.id,
                "currency_id": bill.currency_id.id,
                "amount_currency": bill.amount_residual or bill.amount_total,
                "payment_type": "supplier",
                "payment_channel": "transfer",
                "company_id": bill.company_id.id,
                "payment_date": bill.invoice_date_due or bill.invoice_date or fields.Date.context_today(self),
                "state": "draft",
            })
        return res
    vendor_due_soon = fields.Boolean(
        string="Échéance proche",
        compute="_compute_vendor_due_days",
        store=False,
    )

    def _treasury_get_auto_payment_term(self, amount):
        if amount >= 500000:
            term = self.env.ref("treasury_management.payment_term_treasury_60", raise_if_not_found=False)
            if term:
                return term
            return self.env["account.payment.term"].search([
                ("name", "=", "60 jours")
            ], limit=1)
        term = self.env.ref("treasury_management.payment_term_treasury_50", raise_if_not_found=False)
        if term:
            return term
        return self.env["account.payment.term"].search([
            ("name", "=", "30 jours")
        ], limit=1)

    def _treasury_apply_payment_term(self):
        if self.env.context.get("treasury_skip_auto_term"):
            return
        for move in self:
            if move.move_type not in ("in_invoice", "out_invoice"):
                continue
            term = move._treasury_get_auto_payment_term(move.amount_total or 0.0)
            if term and move.invoice_payment_term_id != term:
                move.with_context(treasury_skip_auto_term=True).write({
                    "invoice_payment_term_id": term.id,
                })

    @api.onchange("invoice_line_ids", "amount_total", "currency_id")
    def _onchange_treasury_payment_term(self):
        for move in self:
            if move.move_type not in ("in_invoice", "out_invoice"):
                continue
            term = move._treasury_get_auto_payment_term(move.amount_total or 0.0)
            if term:
                move.invoice_payment_term_id = term

    def action_send_to_treasury(self):
        for m in self:
            if m.move_type == 'in_invoice':
                self.env['treasury.payment'].create({
                    'payment_type': 'supplier',
                    'amount': m.amount_total,
                    'amount_currency': m.amount_total,
                    'partner_id': m.partner_id.id,
                    'invoice_id': m.id,
                    'currency_id': m.currency_id.id,
                    'payment_date': m.invoice_date_due or m.invoice_date,
                })

    def action_schedule_treasury_payment(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": "treasury.payment.schedule.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_invoice_id": self.id,
                "default_partner_id": self.partner_id.id,
                "default_planned_payment_date": self.invoice_date_due or self.invoice_date,
            },
        }

    @api.depends("treasury_payment_ids", "treasury_payment_ids.priority", "treasury_payment_ids.planned_payment_date", "treasury_payment_ids.payment_channel")
    def _compute_treasury_payment_info(self):
        for move in self:
            payment = move.treasury_payment_ids.sorted(lambda p: p.planned_payment_date or fields.Date.context_today(self))[:1]
            move.treasury_payment_priority = payment.priority if payment else False
            move.treasury_planned_payment_date = payment.planned_payment_date if payment else False
            move.treasury_payment_channel = payment.payment_channel if payment else False

    @api.depends("invoice_date_due", "payment_state")
    def _compute_vendor_due_days(self):
        today = fields.Date.context_today(self)
        for move in self:
            if move.move_type != "in_invoice" or not move.invoice_date_due:
                move.vendor_due_days = 0
                move.vendor_is_overdue = False
                move.vendor_due_soon = False
                move.vendor_due_display = _("Aucune échéance")
                move.vendor_due_color = 0
                continue
            delta = (move.invoice_date_due - today).days
            move.vendor_due_days = delta
            move.vendor_is_overdue = delta < 0 and move.payment_state != "paid"
            move.vendor_due_soon = 0 <= delta <= 7 and move.payment_state != "paid"
            if move.payment_state == "paid":
                move.vendor_due_display = _("Payée")
                move.vendor_due_color = 7
            elif delta < 0:
                move.vendor_due_display = _("Retard de %s j") % abs(delta)
                move.vendor_due_color = 1
            elif delta == 0:
                move.vendor_due_display = _("Aujourd'hui")
                move.vendor_due_color = 3
            elif delta <= 7:
                move.vendor_due_display = _("Dans %s j") % delta
                move.vendor_due_color = 2
            elif delta <= 30:
                move.vendor_due_display = _("Dans %s j") % delta
                move.vendor_due_color = 4
            else:
                move.vendor_due_display = _("Dans %s j") % delta
                move.vendor_due_color = 6

    @api.model
    def _cron_treasury_invoice_reminders(self):
        today = fields.Date.context_today(self)
        # Customer invoices overdue
        customer_invoices = self.search([
            ("move_type", "=", "out_invoice"),
            ("state", "=", "posted"),
            ("payment_state", "!=", "paid"),
            ("invoice_date_due", "<", today),
        ])
        activity_type = self.env.ref("mail.mail_activity_data_todo")
        for inv in customer_invoices:
            user = inv.invoice_user_id or inv.user_id or self.env.user
            inv.activity_schedule(
                activity_type.id,
                user_id=user.id,
                summary="Relance facture client",
                note="Facture client en retard. Préparer une relance.",
            )

        # Vendor bills overdue
        vendor_bills = self.search([
            ("move_type", "=", "in_invoice"),
            ("state", "=", "posted"),
            ("payment_state", "!=", "paid"),
            ("invoice_date_due", "<", today),
        ])
        for bill in vendor_bills:
            user = bill.invoice_user_id or bill.user_id or self.env.user
            bill.activity_schedule(
                activity_type.id,
                user_id=user.id,
                summary="Paiement fournisseur en retard",
                note="Facture fournisseur en retard. Vérifier le règlement.",
            )

        # Subscription reminders if module exists
        Subscription = self.env.get("sale.subscription")
        if Subscription:
            end_date = date_utils.add(today, days=30)
            subs = Subscription.search([
                ("date_end", "!=", False),
                ("date_end", ">=", today),
                ("date_end", "<=", end_date),
            ])
            for sub in subs:
                user = sub.user_id or self.env.user
                sub.activity_schedule(
                    activity_type.id,
                    user_id=user.id,
                    summary="Relance abonnement",
                    note="Abonnement arrive à échéance dans 30 jours.",
                )

    def create(self, vals_list):
        moves = super().create(vals_list)
        moves._treasury_apply_payment_term()
        return moves

    def write(self, vals):
        res = super().write(vals)
        if any(k in vals for k in ["invoice_line_ids", "line_ids", "amount_total", "currency_id"]):
            self._treasury_apply_payment_term()
        return res
