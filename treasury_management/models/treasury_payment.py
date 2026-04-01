from datetime import timedelta

from dateutil.relativedelta import relativedelta

from odoo import models, fields, api, _
from odoo.exceptions import UserError

class TreasuryPayment(models.Model):
    _name = "treasury.payment"
    _description = "Décaissement de trésorerie"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    name = fields.Char(default="Nouveau", readonly=True, tracking=True, string="Référence")
    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
        string="Société",
    )
    company_currency_id = fields.Many2one(
        "res.currency",
        related="company_id.currency_id",
        store=True,
        readonly=True,
    )
    currency_id = fields.Many2one(
        "res.currency",
        required=True,
        default=lambda self: self.env.company.currency_id,
        tracking=True,
        string="Devise",
    )
    payment_type = fields.Selection([
        ("salary","Salaire"),
        ("bonus","Prime"),
        ("supplier","Fournisseur"),
        ("tax","Impôts et taxes"),
        ("expense","Note de frais"),
        ("other","Autre")
    ], required=True, tracking=True, string="Type de paiement")
    amount_currency = fields.Monetary(
        currency_field="currency_id",
        required=True,
        tracking=True,
        string="Montant (devise)",
    )
    amount = fields.Monetary(
        currency_field="company_currency_id",
        compute="_compute_amount",
        inverse="_inverse_amount",
        store=True,
        tracking=True,
        string="Montant",
    )
    payment_date = fields.Date(default=fields.Date.context_today, tracking=True, string="Date de paiement")
    planned_payment_date = fields.Date(string="Date prévue", tracking=True)
    priority = fields.Selection(
        [("0", "Basse"), ("1", "Normale"), ("2", "Haute"), ("3", "Urgente")],
        default="1",
        tracking=True,
        string="Priorité",
    )
    urgency_reason = fields.Text(string="Motif d'urgence", tracking=True)
    state = fields.Selection([
        ("draft", "Non planifié"),
        ("planned", "Planifié"),
        ("paid", "Payé"),
        ("cancelled", "Annulé"),
    ], default="draft", tracking=True, string="État")
    category_id = fields.Many2one("treasury.category", string="Catégorie", tracking=True)

    state_color = fields.Char(compute="_compute_state_color", store=False)

    @api.depends('state')
    def _compute_state_color(self):
        for rec in self:
            if rec.state == 'draft':
                rec.state_color = 'grey'
            elif rec.state == 'planned':
                rec.state_color = 'blue'
            elif rec.state == 'paid':
                rec.state_color = 'green'
            elif rec.state in ('approved', 'to_cash'):
                rec.state_color = 'orange'  # legacy values during migration
            else:
                rec.state_color = 'grey'
    @api.depends("payment_type", "partner_id")
    def _compute_beneficiary_display(self):
        for rec in self:
            if rec.payment_type == "salary":
                rec.beneficiary_display = _("Salaires (données RH masquées)")
            else:
                rec.beneficiary_display = rec.partner_id.display_name or False
    payment_channel = fields.Selection(
        [("transfer", "Virement"), ("cheque", "Chèque"), ("cash", "Espèces")],
        string="Mode de paiement",
        tracking=True,
    )
    instructions = fields.Text(string="Directives", tracking=True)
    responsible_user_id = fields.Many2one(
        "res.users",
        string="Responsable",
        default=lambda self: self.env.user,
        tracking=True,
    )
    partner_id = fields.Many2one("res.partner", string="Partenaire", tracking=True)
    beneficiary_display = fields.Char(
        string="Bénéficiaire",
        compute="_compute_beneficiary_display",
        store=False,
    )
    employee_id = fields.Many2one("hr.employee", string="Employé", tracking=True)
    invoice_id = fields.Many2one(
        "account.move",
        string="Facture fournisseur",
        domain="[('move_type','=','in_invoice')]",
        tracking=True,
    )
    payslip_id = fields.Many2one(
        "hr.payslip",
        string="Bulletin de paie",
        tracking=True,
    )
    journal_id = fields.Many2one(
        "account.journal",
        string="Journal de paiement",
        tracking=True,
        domain="[]"
    )
    payroll_batch_id = fields.Many2one(
        "treasury.payroll.batch",
        string="Lot paie",
        readonly=True,
        tracking=True,
    )

    @api.onchange('payment_channel')
    def _onchange_payment_channel(self):
        domain = []
        allowed_types = []
        if self.payment_channel in ['transfer', 'cheque']:
            domain = [('type', '=', 'bank')]
            allowed_types = ['bank']
        elif self.payment_channel == 'cash':
            domain = [('type', '=', 'cash')]
            allowed_types = ['cash']
            if not self.journal_id:
                self.journal_id = self._get_default_cash_journal()

        # If a journal is already set but no longer fits the payment channel, clear it
        if self.journal_id and allowed_types and self.journal_id.type not in allowed_types:
            self.journal_id = False

        return {'domain': {'journal_id': domain}}
    payment_id = fields.Many2one("account.payment", string="Paiement", readonly=True, tracking=True)
    statement_line_id = fields.Many2one(
        "account.bank.statement.line",
        string="Ligne de relevé bancaire",
        tracking=True,
    )
    payment_delay_days = fields.Integer(
        string="Délai de paiement (jours)",
        compute="_compute_payment_delay_days",
        store=True,
    )
    is_overdue = fields.Boolean(string="En retard", compute="_compute_is_overdue", store=True)
    cash_required = fields.Boolean(
        string="Soumis à la caisse",
        compute="_compute_cash_required",
        store=True,
    )
    cash_queue = fields.Boolean(
        string="File caisse",
        compute="_compute_cash_queue",
        store=True,
    )

    @api.model
    def create(self, vals):
        if vals.get("name", "Nouveau") == "Nouveau":
            vals["name"] = self.env["ir.sequence"].next_by_code("treasury.payment")
        threshold = self._get_cash_threshold()
        if not vals.get("payment_channel") and (vals.get("amount") or 0.0) < threshold:
            vals["payment_channel"] = "cash"
        if vals.get("payment_channel") == "cash" and not vals.get("journal_id"):
            cash_journal = self._get_default_cash_journal()
            if cash_journal:
                vals["journal_id"] = cash_journal.id
        if "amount_currency" not in vals and "amount" in vals:
            currency = self.env["res.currency"].browse(vals.get("currency_id")) or self.env.company.currency_id
            company = self.env["res.company"].browse(vals.get("company_id")) or self.env.company
            date = vals.get("payment_date") or fields.Date.context_today(self)
            if currency == company.currency_id:
                vals["amount_currency"] = vals["amount"]
            else:
                vals["amount_currency"] = company.currency_id._convert(
                    vals["amount"], currency, company, date
                )
        return super().create(vals)

    def write(self, vals):
        res = super().write(vals)
        # Keep workflow coherent: adding a planned date moves draft -> planned unless state was set explicitly.
        if vals.get("planned_payment_date") and "state" not in vals:
            drafts = self.filtered(lambda p: p.state == "draft")
            if drafts:
                super(TreasuryPayment, drafts.with_context(treasury_skip_state_sync=True)).write({"state": "planned"})
        return res

    @api.depends("amount_currency", "currency_id", "company_id", "payment_date")
    def _compute_amount(self):
        for rec in self:
            if not rec.currency_id or not rec.company_currency_id:
                rec.amount = rec.amount_currency or 0.0
                continue
            if rec.currency_id == rec.company_currency_id:
                rec.amount = rec.amount_currency or 0.0
            else:
                rec.amount = rec.currency_id._convert(
                    rec.amount_currency or 0.0,
                    rec.company_currency_id,
                    rec.company_id,
                    rec.payment_date or fields.Date.context_today(rec),
                )

    def _inverse_amount(self):
        for rec in self:
            if not rec.currency_id or not rec.company_currency_id:
                rec.amount_currency = rec.amount
                continue
            if rec.currency_id == rec.company_currency_id:
                rec.amount_currency = rec.amount
            else:
                rec.amount_currency = rec.company_currency_id._convert(
                    rec.amount or 0.0,
                    rec.currency_id,
                    rec.company_id,
                    rec.payment_date or fields.Date.context_today(rec),
                )

    def action_cancel(self):
        for rec in self:
            if rec.state == "cancelled":
                continue
            # Annuler le paiement comptable associé le cas échéant
            payment = rec.payment_id
            if payment:
                if hasattr(payment, "action_draft"):
                    payment.action_draft()
                if hasattr(payment, "action_cancel"):
                    payment.action_cancel()
                rec.payment_id = False
            # Supprimer l'écriture de relevé si créée
            if rec.statement_line_id:
                rec.statement_line_id.unlink()
                rec.statement_line_id = False
            rec.state = "cancelled"

    @api.depends("invoice_id", "invoice_id.invoice_date_due", "payment_id", "payment_id.date", "payment_date")
    def _compute_payment_delay_days(self):
        for rec in self:
            due_date = rec.invoice_id.invoice_date_due or rec.invoice_id.invoice_date
            if not due_date:
                rec.payment_delay_days = 0
                continue
            paid_date = rec.payment_id.date or rec.payment_date or fields.Date.context_today(rec)
            rec.payment_delay_days = (paid_date - due_date).days

    @api.depends("amount")
    def _compute_cash_required(self):
        threshold = self._get_cash_threshold()
        for rec in self:
            rec.cash_required = rec.amount >= threshold

    @api.depends("amount", "payment_channel")
    def _compute_cash_queue(self):
        threshold = self._get_cash_threshold()
        for rec in self:
            rec.cash_queue = bool(
                rec.payment_channel == "cash" or (rec.amount and rec.amount < threshold)
            )

    @api.depends("state", "planned_payment_date")
    def _compute_is_overdue(self):
        today = fields.Date.context_today(self)
        for rec in self:
            rec.is_overdue = bool(
                rec.state not in ("paid",)
                and rec.planned_payment_date
                and rec.planned_payment_date < today
            )

    def _get_approval_threshold(self):
        param = self.env["ir.config_parameter"].sudo().get_param("treasury_management.approval_threshold", default="0")
        try:
            return float(param)
        except ValueError:
            return 0.0

    def _get_cash_threshold(self):
        param = self.env["ir.config_parameter"].sudo().get_param("treasury_management.cash_threshold", default="100000")
        try:
            return float(param)
        except ValueError:
            return 100000.0

    def _get_default_cash_journal(self):
        """Return first cash journal of the company to prefill caisse dépenses."""
        company = self.env.company
        return self.env["account.journal"].search(
            [("type", "=", "cash"), ("company_id", "=", company.id)],
            limit=1,
        )

    def action_process(self):
        for rec in self:
            if not self.env.user.has_group("treasury_management.group_treasury_df"):
                raise UserError("Vous n'avez pas les droits pour valider ce décaissement.")
            if rec.state not in ("planned", "draft"):
                continue
            if not rec.planned_payment_date:
                rec.planned_payment_date = rec.payment_date or fields.Date.context_today(self)
            rec.state = "planned"

    def action_open_plan_wizard(self):
        """Open a popup to plan one or several draft payments."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": "treasury.payment.plan.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_payment_ids": self.ids,
                "default_planned_payment_date": self.planned_payment_date or self.payment_date or fields.Date.context_today(self),
                "default_payment_channel": self.payment_channel or False,
                "default_journal_id": self.journal_id.id,
                "default_priority": self.priority or "1",
            },
        }

    def action_pay(self):
        for rec in self:
            if rec.planned_payment_date and rec.planned_payment_date > fields.Date.context_today(self):
                raise UserError("La date de règlement n'est pas encore arrivée. Le paiement est bloqué.")
            if rec.payroll_batch_id and rec.payroll_batch_id.batch_type == "42":
                rec.payroll_batch_id._create_payment_move(
                    rec.payment_date or fields.Date.context_today(self)
                )
                if rec.payroll_batch_id.state != "paid":
                    rec.payroll_batch_id.state = "paid"
                rec.state = "paid"
                continue
            if rec.payment_id:
                rec.state = "paid"
                continue
            if rec.state not in ("planned",):
                raise UserError("Le décaissement doit être planifié avant paiement.")
            if not rec.journal_id:
                if rec.payment_channel == "cash":
                    journal_id = self.env["ir.config_parameter"].sudo().get_param("treasury_management.cash_journal_id")
                    if journal_id:
                        rec.journal_id = int(journal_id)
                if not rec.journal_id:
                    raise UserError("Veuillez définir un journal de paiement.")
            if rec.invoice_id:
                if rec.invoice_id.payment_state == "paid":
                    rec.state = "paid"
                    continue
                payment_register = self.env["account.payment.register"].with_context(
                    active_model="account.move",
                    active_ids=rec.invoice_id.ids,
                ).create({
                    "amount": rec.amount,
                    "journal_id": rec.journal_id.id,
                })
                payments = payment_register.action_create_payments()
                if isinstance(payments, dict):
                    payment_ids = payments.get("res_id") and [payments["res_id"]] or []
                else:
                    payment_ids = payments.ids
                rec.payment_id = payment_ids and payment_ids[0] or False
            else:
                payment_method = rec.journal_id.outbound_payment_method_line_ids[:1]
                if not payment_method:
                    raise UserError("Aucun mode de paiement sortant n'est configuré sur ce journal.")
                payment = self.env["account.payment"].create({
                    "payment_type": "outbound",
                    "partner_type": "supplier",
                    "partner_id": rec.partner_id.id,
                    "amount": rec.amount,
                    "journal_id": rec.journal_id.id,
                    "payment_method_line_id": payment_method.id,
                })
                payment.action_post()
                rec.payment_id = payment.id
            rec.state = "paid"

    def action_view_payment(self):
        self.ensure_one()
        if self.payment_id:
            return {
                "type": "ir.actions.act_window",
                "res_model": "account.payment",
                "res_id": self.payment_id.id,
                "view_mode": "form",
            }
        return False

    def action_print_payment_voucher(self):
        """Imprime le bon de paiement pour les opérations passées en caisse dépenses."""
        self.ensure_one()
        if self.state != "paid":
            raise UserError(_("Le bon de paiement ne peut être imprimé que pour un décaissement payé."))
        is_cash_flow = (
            self.payment_channel == "cash"
            or (self.journal_id and self.journal_id.type == "cash")
            or self.cash_queue
        )
        if not is_cash_flow:
            raise UserError(_("Le bon de paiement est réservé aux paiements traités depuis la caisse dépenses."))
        return self.env.ref("treasury_management.treasury_payment_voucher_report").report_action(self)

    @api.onchange("invoice_id")
    def _onchange_invoice_id(self):
        for rec in self:
            if not rec.invoice_id:
                continue
            invoice = rec.invoice_id
            if invoice.move_type != "in_invoice":
                continue
            rec.partner_id = invoice.partner_id
            rec.currency_id = invoice.currency_id
            rec.amount_currency = invoice.amount_residual or invoice.amount_total
            rec.payment_type = "supplier"
            rec.payment_date = invoice.invoice_date_due or invoice.invoice_date
            rec.planned_payment_date = rec.payment_date

    @api.onchange("employee_id")
    def _onchange_employee_id(self):
        for rec in self:
            if rec.payment_type != "salary":
                continue
            partner = False
            employee = rec.employee_id
            if employee:
                employee_fields = employee._fields
                if "work_contact_id" in employee_fields:
                    partner = employee.work_contact_id
                elif "private_address_id" in employee_fields:
                    partner = employee.private_address_id
                elif "address_home_id" in employee_fields:
                    partner = employee.address_home_id
                elif "address_id" in employee_fields:
                    partner = employee.address_id
            rec.partner_id = partner

    @api.model
    def _cron_treasury_overdue_alerts(self):
        today = fields.Date.context_today(self)
        tomorrow = today + timedelta(days=1)
        in_2_days = today + timedelta(days=2)

        cashier_group = self.env.ref("treasury_management.group_treasury_cashier", raise_if_not_found=False)
        df_group = self.env.ref("treasury_management.group_treasury_df", raise_if_not_found=False)
        users = (cashier_group and cashier_group.users) or self.env["res.users"]
        users |= (df_group and df_group.users) or self.env["res.users"]
        activity_type = self.env.ref("mail.mail_activity_data_todo")

        # Paiements en retard (date dépassée, non payés)
        overdue_payments = self.search([
            ("state", "not in", ("paid", "cancelled")),
            ("planned_payment_date", "<", today),
        ])
        for rec in overdue_payments:
            days_late = (today - rec.planned_payment_date).days
            for user in users:
                rec.activity_schedule(
                    activity_type.id,
                    user_id=user.id,
                    summary=f"Décaissement en retard de {days_late} jour(s)",
                    note=f"Le décaissement {rec.name} ({rec.beneficiary_display or ''}) est en retard de {days_late} jour(s). Montant : {rec.amount:,.0f}.",
                )

        # Paiements urgents niveau 1 (★★) : alerter le jour J
        urgent_l1_today = self.search([
            ("state", "not in", ("paid", "cancelled")),
            ("priority", "=", "2"),
            ("planned_payment_date", "=", today),
        ])
        for rec in urgent_l1_today:
            for user in users:
                rec.activity_schedule(
                    activity_type.id,
                    user_id=user.id,
                    summary="⚠ Paiement urgent — Échéance aujourd'hui",
                    note=f"Le décaissement {rec.name} ({rec.beneficiary_display or ''}) est marqué urgent (★★) et arrive à échéance aujourd'hui. Montant : {rec.amount:,.0f}.",
                )

        # Paiements très urgents niveau 2 (★★★) : alerter J-2 et J-1
        urgent_l2_soon = self.search([
            ("state", "not in", ("paid", "cancelled")),
            ("priority", "=", "3"),
            ("planned_payment_date", "in", [tomorrow, in_2_days]),
        ])
        for rec in urgent_l2_soon:
            days_left = (rec.planned_payment_date - today).days
            for user in users:
                rec.activity_schedule(
                    activity_type.id,
                    user_id=user.id,
                    summary=f"🔴 Paiement très urgent — J-{days_left}",
                    note=f"Le décaissement {rec.name} ({rec.beneficiary_display or ''}) est marqué très urgent (★★★) et arrive à échéance dans {days_left} jour(s). Montant : {rec.amount:,.0f}. À régler en priorité absolue.",
                )

        # Encaissements en retard
        receipts = self.env["treasury.receipt"].search([
            ("state", "not in", ("paid", "cancelled")),
            ("planned_receipt_date", "<", today),
        ])
        for rec in receipts:
            days_late = (today - rec.planned_receipt_date).days
            for user in users:
                rec.activity_schedule(
                    activity_type.id,
                    user_id=user.id,
                    summary=f"Encaissement en retard de {days_late} jour(s)",
                    note=f"L'encaissement {rec.name} est en retard de {days_late} jour(s) par rapport à la date prévue.",
                )

    @api.model
    def get_payment_dashboard_data(self):
        """Retourne les données agrégées pour le tableau de bord opérationnel."""
        today = fields.Date.context_today(self)
        in_7_days = today + timedelta(days=7)
        company = self.env.company
        currency = company.currency_id

        pending = self.search([("state", "not in", ("paid", "cancelled"))])
        urgent = pending.filtered(lambda r: r.priority in ("2", "3"))
        overdue = pending.filtered(lambda r: r.planned_payment_date and r.planned_payment_date < today)
        upcoming = pending.filtered(
            lambda r: r.planned_payment_date and today <= r.planned_payment_date <= in_7_days
        )

        payment_type_labels = dict(self._fields["payment_type"].selection)
        state_labels = dict(self._fields["state"].selection)

        def to_list(recs, limit=15):
            rows = []
            for r in recs.sorted(key=lambda x: (x.planned_payment_date or fields.Date.from_string("9999-12-31"), -int(x.priority or 0)))[:limit]:
                rows.append({
                    "id": r.id,
                    "name": r.name,
                    "partner": r.partner_id.name or r.beneficiary_display or "",
                    "amount": r.amount,
                    "planned_date": r.planned_payment_date.strftime("%d/%m/%Y") if r.planned_payment_date else "",
                    "priority": r.priority or "0",
                    "payment_type": payment_type_labels.get(r.payment_type, r.payment_type or ""),
                    "state": r.state,
                    "state_label": state_labels.get(r.state, r.state),
                    "is_overdue": r.is_overdue,
                    "urgency_reason": r.urgency_reason or "",
                })
            return rows

        # Soldes des journaux de trésorerie (bank + cash)
        journals = self.env["account.journal"].search([
            ("type", "in", ("bank", "cash")),
            ("company_id", "=", company.id),
        ])
        journal_balances = []
        if journals:
            self.env.cr.execute("""
                SELECT j.id,
                       COALESCE(SUM(l.balance), 0.0) AS balance
                  FROM account_journal j
             LEFT JOIN account_move_line l
                    ON l.journal_id = j.id
                   AND l.account_id = j.default_account_id
             LEFT JOIN account_move m
                    ON m.id = l.move_id
                 WHERE j.id IN %s
                   AND (l.id IS NULL OR m.state = 'posted')
              GROUP BY j.id
            """, [tuple(journals.ids)])
            bal_map = dict(self.env.cr.fetchall())
            for j in journals:
                journal_balances.append({
                    "id": j.id,
                    "name": j.name,
                    "type": j.type,
                    "balance": bal_map.get(j.id, 0.0),
                    "currency_symbol": (j.currency_id or currency).symbol or "",
                    "currency_position": (j.currency_id or currency).position or "after",
                })

        return {
            "pending": {"count": len(pending), "amount": sum(pending.mapped("amount"))},
            "urgent": {"count": len(urgent), "amount": sum(urgent.mapped("amount"))},
            "overdue": {"count": len(overdue), "amount": sum(overdue.mapped("amount"))},
            "upcoming": {"count": len(upcoming), "amount": sum(upcoming.mapped("amount"))},
            "urgent_list": to_list(urgent.sorted(key=lambda r: (-int(r.priority or 0), r.planned_payment_date or fields.Date.from_string("9999-12-31")))),
            "overdue_list": to_list(overdue.sorted("planned_payment_date")),
            "upcoming_list": to_list(upcoming.sorted("planned_payment_date")),
            "journal_balances": journal_balances,
            "company": {
                "currency_symbol": currency.symbol or "",
                "currency_position": currency.position or "after",
            },
            "today": today.strftime("%d/%m/%Y"),
        }

    @api.model
    def get_treasury_forecast(self, date_from, date_to):
        """Prévisions de trésorerie par mois sur la période donnée."""
        company = self.env.company
        currency = company.currency_id

        d_from = fields.Date.from_string(date_from)
        d_to = fields.Date.from_string(date_to)

        months = []
        cursor = d_from.replace(day=1)
        while cursor <= d_to:
            m_start = max(cursor, d_from)
            m_end = min(cursor + relativedelta(months=1, days=-1), d_to)

            payments = self.search([
                ("state", "not in", ("paid", "cancelled")),
                ("planned_payment_date", ">=", m_start),
                ("planned_payment_date", "<=", m_end),
            ])
            receipts = self.env["treasury.receipt"].search([
                ("state", "not in", ("paid", "cancelled")),
                ("planned_receipt_date", ">=", m_start),
                ("planned_receipt_date", "<=", m_end),
            ])

            pay_amount = sum(payments.mapped("amount"))
            rec_amount = sum(receipts.mapped("amount"))
            net = rec_amount - pay_amount

            months.append({
                "label": cursor.strftime("%b %Y"),
                "date_from": m_start.strftime("%Y-%m-%d"),
                "date_to": m_end.strftime("%Y-%m-%d"),
                "payments_count": len(payments),
                "payments_amount": pay_amount,
                "receipts_count": len(receipts),
                "receipts_amount": rec_amount,
                "net": net,
                "is_positive": net >= 0,
            })
            cursor += relativedelta(months=1)

        total_pay = sum(m["payments_amount"] for m in months)
        total_rec = sum(m["receipts_amount"] for m in months)

        return {
            "months": months,
            "total": {
                "payments_amount": total_pay,
                "receipts_amount": total_rec,
                "net": total_rec - total_pay,
                "is_positive": (total_rec - total_pay) >= 0,
            },
            "company": {
                "currency_symbol": currency.symbol or "",
                "currency_position": currency.position or "after",
            },
        }

    @api.model
    def _register_hook(self):
        res = super()._register_hook()
        cr = self.env.cr
        # Map legacy states to the new workflow
        cr.execute("""
            UPDATE treasury_payment
               SET state = 'planned'
             WHERE state IN ('approved', 'to_cash')
        """)
        cr.execute("""
            UPDATE treasury_payment
               SET state = 'planned'
             WHERE state = 'processing'
        """)
        cr.execute("""
            UPDATE treasury_payment
               SET state = 'draft'
             WHERE state IS NULL
        """)
        return res
