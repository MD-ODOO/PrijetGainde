from datetime import date as py_date

from odoo import _, api, fields, models
from odoo.tools import date_utils
from odoo.exceptions import UserError


class TreasuryPayrollDisbursementWizard(models.TransientModel):
    _name = "treasury.payroll.disbursement.wizard"
    _description = "Assistant décaissement paie par période"

    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
    )
    currency_id = fields.Many2one(
        "res.currency",
        related="company_id.currency_id",
        readonly=True,
        store=False,
    )
    period_start = fields.Date(
        string="Début période",
        required=True,
        default=lambda self: date_utils.start_of(fields.Date.context_today(self), "month"),
    )
    period_end = fields.Date(
        string="Fin période",
        required=True,
        default=lambda self: date_utils.end_of(fields.Date.context_today(self), "month"),
    )
    batch_ids = fields.Many2many(
        "treasury.payroll.batch",
        string="Lots générés",
        readonly=True,
    )
    batch_count = fields.Integer(string="Nombre de lots", compute="_compute_batch_stats")

    total_net = fields.Monetary(
        string="Total net à payer",
        currency_field="currency_id",
        compute="_compute_totals",
        store=False,
    )
    total_ipress = fields.Monetary(
        string="Total IPRESS",
        currency_field="currency_id",
        compute="_compute_totals",
        store=False,
    )
    total_cfce = fields.Monetary(
        string="Total CFCE",
        currency_field="currency_id",
        compute="_compute_totals",
        store=False,
    )
    total_family_allowance = fields.Monetary(
        string="Allocations familiales",
        currency_field="currency_id",
        compute="_compute_totals",
        store=False,
    )
    total_income_tax = fields.Monetary(
        string="Impôt sur le revenu",
        currency_field="currency_id",
        compute="_compute_totals",
        store=False,
    )

    # Paramètres de paiement appliqués aux lots générés
    partner_id = fields.Many2one(
        "res.partner",
        string="Bénéficiaire par défaut",
        help="Partenaire à utiliser si les lots n'ont pas encore de bénéficiaire.",
    )
    journal_id = fields.Many2one(
        "account.journal",
        string="Journal de paiement",
        domain="[('type','in',('bank','cash'))]",
        help="Journal appliqué aux lots avant validation/paiement.",
    )

    def _sanitize_dates(self):
        self.ensure_one()
        start = self.period_start or date_utils.start_of(fields.Date.context_today(self), "month")
        end = self.period_end or fields.Date.context_today(self)
        if start > end:
            start, end = end, start
        self.period_start = start
        self.period_end = end
        return start, end

    @api.depends("batch_ids")
    def _compute_batch_stats(self):
        for wizard in self:
            wizard.batch_count = len(wizard.batch_ids)

    # --- Helpers ---
    def _get_code_set(self, param_name, default_value):
        param = self.env["ir.config_parameter"].sudo().get_param(param_name, default_value)
        return {code.strip().upper() for code in (param or "").split(",") if code.strip()}

    @api.depends("period_start", "period_end", "company_id")
    def _compute_totals(self):
        code_net = self._get_code_set("treasury_management.payroll_code_net", "NET")
        code_ipress = self._get_code_set("treasury_management.payroll_code_ipress", "IPRESS,IPRES")
        code_cfce = self._get_code_set("treasury_management.payroll_code_cfce", "CFCE")
        code_family = self._get_code_set("treasury_management.payroll_code_family_allowance", "AF,ALLOCFAM")
        code_ir = self._get_code_set("treasury_management.payroll_code_income_tax", "IR,IRPP,IRRF")

        for wizard in self:
            start, end = wizard.period_start, wizard.period_end
            if not start or not end:
                wizard.total_net = wizard.total_ipress = wizard.total_cfce = 0.0
                wizard.total_family_allowance = wizard.total_income_tax = 0.0
                continue

            # Trésorerie n'a pas forcément les droits RH : on lit en sudo pour
            # pouvoir agréger les montants sans exposer les bulletins dans l'IHM.
            slips = self.env["hr.payslip"].sudo().search([
                ("state", "=", "done"),
                ("company_id", "=", wizard.company_id.id),
                ("date_from", ">=", start),
                ("date_to", "<=", end),
            ])
            lines = slips.mapped("line_ids")

            def _sum(codes):
                return sum(abs(l.total) for l in lines if (l.code or "").upper() in codes)

            wizard.total_net = _sum(code_net)
            wizard.total_ipress = _sum(code_ipress)
            wizard.total_cfce = _sum(code_cfce)
            wizard.total_family_allowance = _sum(code_family)
            wizard.total_income_tax = _sum(code_ir)

    # --- Actions ---
    def action_generate_batches(self):
        self.ensure_one()
        start, end = self._sanitize_dates()
        batches = self.env["treasury.payroll.batch"]._generate_batches_for_period(
            start, end, self.company_id
        )
        # Refresh to capture possibly newly created batches
        generated = self.env["treasury.payroll.batch"].search([
            ("company_id", "=", self.company_id.id),
            ("period_start", "=", start),
            ("period_end", "=", end),
        ])
        # Appliquer éventuels paramètres de paiement
        if self.partner_id or self.journal_id:
            vals = {}
            if self.partner_id:
                vals["partner_id"] = self.partner_id.id
            if self.journal_id:
                vals["journal_id"] = self.journal_id.id
            generated.filtered(lambda b: b.state != "paid").write(vals)
        self.batch_ids = [(6, 0, generated.ids)]
        action = self.action_open_batches()
        # Slightly adjust the name to highlight the period
        if isinstance(action, dict):
            action["name"] = _("Lots paie %s ➜ %s") % (start, end)
        return action

    def action_pay_batches(self):
        """Générer/rafraîchir les lots puis les valider et les payer en chaîne."""
        self.ensure_one()
        # Génère et applique les valeurs par défaut sur les lots
        self.action_generate_batches()
        batches = self.batch_ids
        if not batches:
            return self.action_open_batches()

        # Valider les lots à payer
        to_validate = batches.filtered(lambda b: b.state == "to_pay")
        if to_validate:
            to_validate.action_validate()

        # Payer les lots validés ou encore à payer
        to_pay = batches.filtered(lambda b: b.state in ("validated", "to_pay"))
        if to_pay:
            to_pay.action_pay()

        return self.action_open_batches()

    def action_print_report(self):
        """Imprimer un rapport synthétique de la période (totaux + lots)."""
        self.ensure_one()
        self._sanitize_dates()
        report = self.env.ref(
            "treasury_management.payroll_disbursement_report",
            raise_if_not_found=False,
        )
        if not report:
            raise UserError(
                _("Le rapport n'est pas installé. Mettez à jour le module treasury_management.")
            )
        return report.report_action(self)

    def action_open_batches(self):
        self.ensure_one()
        start, end = self._sanitize_dates()
        return {
            "type": "ir.actions.act_window",
            "res_model": "treasury.payroll.batch",
            "view_mode": "list,form",
            "target": "current",
            "domain": [
                ("company_id", "=", self.company_id.id),
                ("period_start", "=", start),
                ("period_end", "=", end),
            ],
            "context": {
                "search_default_filter_to_pay": 1,
            },
        }
