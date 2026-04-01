from odoo import models, fields, api
from odoo.exceptions import UserError


class TreasuryReceipt(models.Model):
    _name = "treasury.receipt"
    _description = "Encaissement de trésorerie"
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
    receipt_type = fields.Selection(
        [("customer", "Client"), ("other", "Autre")],
        required=True,
        default="customer",
        tracking=True,
        string="Type d'encaissement",
    )
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
        required=True,
        tracking=True,
        string="Montant",
    )
    amount_collected_currency = fields.Monetary(
        currency_field="currency_id",
        string="Montant encaissé",
        default=0.0,
        tracking=True,
    )
    amount_collected = fields.Monetary(
        currency_field="company_currency_id",
        compute="_compute_amounts_collected",
        inverse="_inverse_amounts_collected",
        store=True,
        tracking=True,
        string="Montant encaissé (société)",
    )
    amount_remaining_currency = fields.Monetary(
        currency_field="currency_id",
        string="Reliquat à encaisser",
        compute="_compute_remaining_amounts",
        store=True,
        tracking=True,
    )
    amount_remaining = fields.Monetary(
        currency_field="company_currency_id",
        compute="_compute_remaining_amounts",
        store=True,
        tracking=True,
        string="Reliquat (société)",
    )
    payment_amount_currency = fields.Monetary(
        currency_field="currency_id",
        string="Montant à encaisser",
        tracking=True,
    )
    receipt_date = fields.Date(default=fields.Date.context_today, tracking=True, string="Date d'encaissement")
    planned_receipt_date = fields.Date(string="Date prévue", tracking=True)
    priority = fields.Selection(
        [("0", "Basse"), ("1", "Normale"), ("2", "Haute"), ("3", "Urgente")],
        default="1",
        tracking=True,
        string="Priorité",
    )
    priority_color = fields.Integer(compute="_compute_badge_colors", store=False)
    urgency_reason = fields.Text(string="Motif d'urgence", tracking=True)
    state = fields.Selection(
        [
            ("draft", "Non encaissé"),
            ("partial", "Partiellement encaissé"),
            ("paid", "Encaissé"),
            ("cancelled", "Annulé"),
        ],
        default="draft",
        tracking=True,
        string="État",
    )
    state_color = fields.Integer(compute="_compute_badge_colors", store=False)
    category_id = fields.Many2one("treasury.category", string="Catégorie", tracking=True)
    partner_id = fields.Many2one("res.partner", string="Client", tracking=True)
    invoice_id = fields.Many2one(
        "account.move",
        string="Facture client",
        domain="[('move_type','=','out_invoice')]",
        tracking=True,
    )
    journal_id = fields.Many2one(
        "account.journal",
        string="Journal de paiement",
        domain="[('type','in',('bank','cash'))]",
        tracking=True,
    )
    payment_id = fields.Many2one("account.payment", string="Paiement", readonly=True, tracking=True)
    statement_line_id = fields.Many2one(
        "account.bank.statement.line",
        string="Ligne de relevé bancaire",
        tracking=True,
    )
    responsible_user_id = fields.Many2one(
        "res.users",
        string="Responsable",
        default=lambda self: self.env.user,
        tracking=True,
    )
    is_overdue = fields.Boolean(string="En retard", compute="_compute_is_overdue", store=True)

    @api.model
    def create(self, vals):
        if vals.get("name", "Nouveau") == "Nouveau":
            vals["name"] = self.env["ir.sequence"].next_by_code("treasury.receipt")
        if not vals.get("planned_receipt_date"):
            vals["planned_receipt_date"] = vals.get("receipt_date") or fields.Date.context_today(self)
        vals.setdefault("amount_collected_currency", 0.0)
        # Préremplir le montant à encaisser avec le solde prévu
        if not vals.get("payment_amount_currency"):
            planned_amount = vals.get("amount_currency") or vals.get("amount")
            vals["payment_amount_currency"] = planned_amount or 0.0
        if "amount_currency" not in vals and "amount" in vals:
            currency = self.env["res.currency"].browse(vals.get("currency_id")) or self.env.company.currency_id
            company = self.env["res.company"].browse(vals.get("company_id")) or self.env.company
            date = vals.get("receipt_date") or fields.Date.context_today(self)
            if currency == company.currency_id:
                vals["amount_currency"] = vals["amount"]
            else:
                vals["amount_currency"] = company.currency_id._convert(
                    vals["amount"], currency, company, date
                )
        return super().create(vals)

    @api.depends("amount_collected_currency", "currency_id", "company_id", "receipt_date")
    def _compute_amounts_collected(self):
        for rec in self:
            # Synchroniser automatiquement avec la facture liée le cas échéant
            if rec.invoice_id:
                rec.amount_collected_currency = rec.invoice_id.amount_total - rec.invoice_id.amount_residual
                rec.amount_collected = rec.invoice_id.amount_total_signed - rec.invoice_id.amount_residual_signed
            elif not rec.currency_id or not rec.company_currency_id:
                rec.amount_collected = rec.amount_collected_currency or 0.0
                continue
            elif rec.currency_id == rec.company_currency_id:
                rec.amount_collected = rec.amount_collected_currency or 0.0
            else:
                rec.amount_collected = rec.currency_id._convert(
                    rec.amount_collected_currency or 0.0,
                    rec.company_currency_id,
                    rec.company_id,
                    rec.receipt_date or fields.Date.context_today(rec),
                )

    def _inverse_amounts_collected(self):
        for rec in self:
            if not rec.currency_id or not rec.company_currency_id:
                rec.amount_collected_currency = rec.amount_collected
                continue
            if rec.currency_id == rec.company_currency_id:
                rec.amount_collected_currency = rec.amount_collected
            else:
                rec.amount_collected_currency = rec.company_currency_id._convert(
                    rec.amount_collected or 0.0,
                    rec.currency_id,
                    rec.company_id,
                    rec.receipt_date or fields.Date.context_today(rec),
                )

    @api.depends("amount_currency", "amount_collected_currency", "currency_id", "company_id")
    def _compute_remaining_amounts(self):
        for rec in self:
            # Aligner le montant cible sur la facture liée si présente
            if rec.invoice_id:
                rec.amount_currency = rec.invoice_id.amount_total
                rec.amount = rec.invoice_id.amount_total_signed

            remaining_currency = (rec.amount_currency or 0.0) - (rec.amount_collected_currency or 0.0)
            if remaining_currency < 0:
                remaining_currency = 0.0
            rec.amount_remaining_currency = remaining_currency
            if not rec.currency_id or not rec.company_currency_id:
                rec.amount_remaining = remaining_currency
                continue
            if rec.currency_id == rec.company_currency_id:
                rec.amount_remaining = remaining_currency
            else:
                rec.amount_remaining = rec.currency_id._convert(
                    remaining_currency,
                    rec.company_currency_id,
                    rec.company_id,
                    rec.receipt_date or fields.Date.context_today(rec),
                )
            rec._update_collection_state()

    @api.onchange("amount_currency", "amount_collected_currency")
    def _onchange_payment_amount_currency(self):
        for rec in self:
            if rec.payment_amount_currency in (None, 0.0) or rec.payment_amount_currency > rec.amount_remaining_currency:
                rec.payment_amount_currency = rec.amount_remaining_currency

    def _update_collection_state(self):
        for rec in self:
            if rec.state == "paid":
                continue
            if (rec.amount_remaining_currency or 0.0) <= 0:
                rec.state = "paid"
            elif (rec.amount_collected_currency or 0.0) > 0 and rec.state != "draft":
                rec.state = "partial"

    @api.depends("amount_currency", "currency_id", "company_id", "receipt_date")
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
                    rec.receipt_date or fields.Date.context_today(rec),
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
                    rec.receipt_date or fields.Date.context_today(rec),
                )

    @api.model
    def action_sync_from_invoices(self):
        """Create draft receipts for every open customer invoice not yet linked to a treasury receipt."""
        today = fields.Date.context_today(self)
        company = self.env.company
        invoices = self.env["account.move"].search([
            ("move_type", "in", ("out_invoice", "out_refund")),
            ("state", "=", "posted"),
            ("payment_state", "!=", "paid"),
            ("company_id", "=", company.id),
        ])
        Receipt = self.env["treasury.receipt"]
        created = self.env["treasury.receipt"]

        for inv in invoices:
            if Receipt.search_count([("invoice_id", "=", inv.id), ("company_id", "=", company.id)]):
                continue
            amount_currency = inv.amount_residual if inv.currency_id == company.currency_id else inv.amount_residual_currency or inv.amount_residual
            vals = {
                "name": "Nouveau",
                "company_id": company.id,
                "currency_id": inv.currency_id.id,
                "amount_currency": amount_currency,
                "amount": inv.amount_residual_signed,
                "payment_amount_currency": amount_currency,
                "receipt_type": "customer",
                "partner_id": inv.partner_id.id,
                "invoice_id": inv.id,
                "planned_receipt_date": inv.invoice_date_due or inv.invoice_date or today,
                "receipt_date": False,
                "state": "draft",
            }
            created |= Receipt.create(vals)

        action = self.env.ref("treasury_management.action_treasury_receipt").read()[0]
        # Focus on newly created records if any
        if created:
            action["domain"] = [("id", "in", created.ids)]
        return action

    @api.depends("state", "planned_receipt_date")
    def _compute_is_overdue(self):
        today = fields.Date.context_today(self)
        for rec in self:
            rec.is_overdue = bool(
                rec.state not in ("paid",)
                and rec.planned_receipt_date
                and rec.planned_receipt_date < today
            )

    def _get_approval_threshold(self):
        param = self.env["ir.config_parameter"].sudo().get_param("treasury_management.approval_threshold", default="0")
        try:
            return float(param)
        except ValueError:
            return 0.0

    def _compute_badge_colors(self):
        state_to_color = {
            "draft": 3,
            "partial": 6,
            "paid": 7,
        }
        priority_to_color = {
            "0": 7,
            "1": 2,
            "2": 5,
            "3": 1,
        }
        for rec in self:
            rec.state_color = state_to_color.get(rec.state, 0)
            rec.priority_color = priority_to_color.get(rec.priority, 0)

    def action_approve_manager(self):
        threshold = self._get_approval_threshold()
        for rec in self:
            if rec.amount < threshold:
                rec.state = "approved"
                continue
            if not self.env.user.has_group("treasury_management.group_treasury_manager"):
                raise UserError("Vous n'avez pas les droits pour valider cet encaissement.")
            rec.state = "manager_approved"

    def action_approve(self):
        threshold = self._get_approval_threshold()
        for rec in self:
            if rec.amount >= threshold and rec.state != "manager_approved":
                raise UserError("Validation manager requise pour ce montant.")
            if not self.env.user.has_group("treasury_management.group_treasury_df"):
                raise UserError("Vous n'avez pas les droits pour valider cet encaissement.")
            rec.state = "approved"

    def action_pay(self):
        for rec in self:
            if rec.state not in ("draft", "partial"):
                raise UserError("L'encaissement doit être validé avant paiement.")
            if not rec.journal_id:
                raise UserError("Veuillez définir un journal de paiement.")
            if rec.amount_remaining_currency <= 0:
                rec.state = "paid"
                continue
            amount_to_pay_currency = rec.payment_amount_currency or rec.amount_remaining_currency or rec.amount_currency
            if amount_to_pay_currency <= 0:
                raise UserError("Veuillez saisir un montant à encaisser supérieur à zéro.")
            if amount_to_pay_currency > rec.amount_remaining_currency:
                amount_to_pay_currency = rec.amount_remaining_currency

            # Convert to company currency for payment creation
            amount_to_pay = amount_to_pay_currency
            if rec.currency_id != rec.company_currency_id:
                amount_to_pay = rec.currency_id._convert(
                    amount_to_pay_currency,
                    rec.company_currency_id,
                    rec.company_id,
                    rec.receipt_date or fields.Date.context_today(rec),
                )

            if rec.invoice_id:
                if rec.invoice_id.payment_state == "paid":
                    rec.state = "paid"
                    continue
                payment_register = self.env["account.payment.register"].with_context(
                    active_model="account.move",
                    active_ids=rec.invoice_id.ids,
                ).create({
                    "amount": amount_to_pay,
                    "journal_id": rec.journal_id.id,
                })
                payments = payment_register.action_create_payments()
                if isinstance(payments, dict):
                    payment_ids = payments.get("res_id") and [payments["res_id"]] or []
                else:
                    payment_ids = payments.ids
                rec.payment_id = payment_ids and payment_ids[0] or False
            else:
                payment_method = rec.journal_id.inbound_payment_method_line_ids[:1]
                if not payment_method:
                    raise UserError("Aucun mode de paiement entrant n'est configuré sur ce journal.")
                payment = self.env["account.payment"].create({
                    "payment_type": "inbound",
                    "partner_type": "customer",
                    "partner_id": rec.partner_id.id,
                    "amount": amount_to_pay,
                    "journal_id": rec.journal_id.id,
                    "payment_method_line_id": payment_method.id,
                })
                payment.action_post()
                rec.payment_id = payment.id
            # Mettre à jour les montants encaissés / reliquats
            rec.amount_collected_currency += amount_to_pay_currency
            remaining_after = max((rec.amount_remaining_currency or 0.0) - amount_to_pay_currency, 0.0)
            rec.payment_amount_currency = remaining_after
            if remaining_after <= 0.00001:
                rec.state = "paid"
            else:
                rec.state = "approved"

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

    def action_cancel(self):
        for rec in self:
            if rec.state == "cancelled":
                continue
            if rec.payment_id:
                if hasattr(rec.payment_id, "action_draft"):
                    rec.payment_id.action_draft()
                if hasattr(rec.payment_id, "action_cancel"):
                    rec.payment_id.action_cancel()
                rec.payment_id = False
            if rec.statement_line_id:
                rec.statement_line_id.unlink()
                rec.statement_line_id = False
            rec.amount_collected_currency = 0.0
            rec.payment_amount_currency = rec.amount_currency
            rec.state = "cancelled"
