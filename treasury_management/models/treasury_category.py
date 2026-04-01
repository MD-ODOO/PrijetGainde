from odoo import models, fields, api


class TreasuryCategory(models.Model):
    _name = "treasury.category"
    _description = "Catégorie de trésorerie"

    name = fields.Char(required=True, string="Nom")
    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
        string="Société",
    )
    currency_id = fields.Many2one(
        "res.currency",
        related="company_id.currency_id",
        readonly=True,
    )
    budget_amount = fields.Monetary(currency_field="currency_id", string="Budget")
    spent_amount = fields.Monetary(
        currency_field="currency_id",
        compute="_compute_spent_amount",
        store=True,
        string="Montant payé",
    )
    remaining_amount = fields.Monetary(
        currency_field="currency_id",
        compute="_compute_spent_amount",
        store=True,
        string="Montant restant",
    )
    payment_ids = fields.One2many("treasury.payment", "category_id")

    @api.depends("payment_ids.amount", "payment_ids.state", "budget_amount")
    def _compute_spent_amount(self):
        for rec in self:
            spent = sum(rec.payment_ids.filtered(lambda p: p.state == "paid").mapped("amount"))
            rec.spent_amount = spent
            rec.remaining_amount = (rec.budget_amount or 0.0) - spent
