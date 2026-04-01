from datetime import date as py_date

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class TreasuryPayrollBatch(models.Model):
    _name = "treasury.payroll.batch"
    _description = "Lot de décaissement de paie"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "period_start desc, batch_type"

    name = fields.Char(default=lambda self: self._default_name(), tracking=True)
    period_start = fields.Date(string="Début période", required=True, tracking=True)
    period_end = fields.Date(string="Fin période", required=True, tracking=True)
    batch_type = fields.Selection(
        [
            ("42", "Salaires"),
            ("43", "Cotisations sociales"),
            ("44", "Impôts et taxes"),
        ],
        string="Type de lot",
        required=True,
        tracking=True,
    )
    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
        tracking=True,
    )
    currency_id = fields.Many2one(
        "res.currency",
        required=True,
        default=lambda self: self.env.company.currency_id,
        tracking=True,
    )
    partner_id = fields.Many2one(
        "res.partner",
        string="Bénéficiaire",
        tracking=True,
    )
    journal_id = fields.Many2one(
        "account.journal",
        string="Journal de paiement",
        domain="[('type', 'in', ('bank', 'cash'))]",
        tracking=True,
    )
    payment_id = fields.Many2one(
        "account.payment",
        string="Paiement comptable",
        readonly=True,
        tracking=True,
    )
    payment_move_id = fields.Many2one(
        "account.move",
        string="Pièce comptable paiement",
        readonly=True,
        copy=False,
    )
    payroll_payment_id = fields.Many2one(
        "treasury.payment",
        string="Ordre de décaissement",
        readonly=True,
        tracking=True,
    )
    state = fields.Selection(
        [
            ("to_pay", "À payer"),
            ("scheduled", "Programmé"),
            ("validated", "Validé"),
            ("paid", "Payé"),
        ],
        string="État",
        default="to_pay",
        tracking=True,
    )
    planned_payment_date = fields.Date(
        string="Date de règlement prévue",
        tracking=True,
        help="Date à laquelle ce décaissement est prévu d'être réglé.",
    )
    payslip_ids = fields.Many2many(
        "hr.payslip",
        "treasury_payroll_batch_payslip_rel",
        "batch_id",
        "payslip_id",
        string="Bulletins",
    )
    payslip_line_ids = fields.Many2many(
        "hr.payslip.line",
        "treasury_payroll_batch_line_rel",
        "batch_id",
        "line_id",
        string="Lignes de paie",
    )
    ignored_line_ids = fields.Many2many(
        "hr.payslip.line",
        "treasury_payroll_batch_ignored_rel",
        "batch_id",
        "line_id",
        string="Lignes ignorées",
        help="Lignes sans compte de tiers ou hors racines 42/43/44.",
    )
    ignored_line_count = fields.Integer(
        compute="_compute_ignored_count",
        string="Lignes ignorées",
    )
    amount_total = fields.Monetary(
        string="Montant à payer",
        currency_field="currency_id",
        compute="_compute_amount_total",
        store=True,
        tracking=True,
    )

    total_net = fields.Monetary(
        string="Total net",
        currency_field="currency_id",
        compute="_compute_components",
        store=True,
        readonly=True,
    )
    total_ipress = fields.Monetary(
        string="Total IPRESS",
        currency_field="currency_id",
        compute="_compute_components",
        store=True,
        readonly=True,
    )
    total_cfce = fields.Monetary(
        string="Total CFCE",
        currency_field="currency_id",
        compute="_compute_components",
        store=True,
        readonly=True,
    )
    total_family_allowance = fields.Monetary(
        string="Allocations familiales",
        currency_field="currency_id",
        compute="_compute_components",
        store=True,
        readonly=True,
    )
    total_income_tax = fields.Monetary(
        string="Impôt sur le revenu",
        currency_field="currency_id",
        compute="_compute_components",
        store=True,
        readonly=True,
    )

    @api.model
    def _default_name(self):
        today = fields.Date.context_today(self)
        if isinstance(today, py_date):
            today = fields.Date.to_string(today)
        return _("Lot paie %s") % today

    @api.model
    def create(self, vals):
        if not vals.get("name") and vals.get("period_start") and vals.get("batch_type"):
            period_label = vals["period_start"]
            if isinstance(period_label, py_date):
                period_label = period_label.strftime("%Y-%m")
            elif isinstance(period_label, str) and len(period_label) >= 7:
                period_label = period_label[:7]
            type_label = dict(self._fields["batch_type"].selection).get(
                vals["batch_type"], vals["batch_type"]
            )
            vals["name"] = _("Lot paie %s - %s") % (period_label, type_label)
        return super().create(vals)

    @api.depends("payslip_line_ids.total")
    def _compute_amount_total(self):
        for batch in self:
            total = sum(batch.payslip_line_ids.mapped("total"))
            batch.amount_total = abs(total)

    # --- Breakdown helpers ---
    @api.model
    def _get_code_list(self, param_name, default_value):
        param = self.env["ir.config_parameter"].sudo().get_param(param_name, default_value)
        return {code.strip().upper() for code in (param or "").split(",") if code.strip()}

    @api.depends("payslip_line_ids.total", "payslip_line_ids.code")
    def _compute_components(self):
        # Parse codes once (unchanged across records thanks to sudo cache)
        code_net = self._get_code_list("treasury_management.payroll_code_net", "NET")
        code_ipress = self._get_code_list("treasury_management.payroll_code_ipress", "IPRESS,IPRES")
        code_cfce = self._get_code_list("treasury_management.payroll_code_cfce", "CFCE")
        code_family = self._get_code_list("treasury_management.payroll_code_family_allowance", "AF,ALLOCFAM")
        code_ir = self._get_code_list("treasury_management.payroll_code_income_tax", "IR,IRPP,IRRF")

        for batch in self:
            lines = batch.payslip_line_ids
            def _sum(codes):
                return sum(abs(l.total) for l in lines if (l.code or "").upper() in codes)

            batch.total_net = _sum(code_net)
            batch.total_ipress = _sum(code_ipress)
            batch.total_cfce = _sum(code_cfce)
            batch.total_family_allowance = _sum(code_family)
            batch.total_income_tax = _sum(code_ir)

    @api.depends("ignored_line_ids")
    def _compute_ignored_count(self):
        for batch in self:
            batch.ignored_line_count = len(batch.ignored_line_ids)

    @api.model
    def _get_root_for_line(self, line):
        account = line.salary_rule_id.account_credit
        if not account or not account.code:
            return False
        code = account.code or ""
        if code.startswith(("42", "422")):
            return "42"
        if code.startswith(("43", "421")):
            return "43"
        if code.startswith("44"):
            return "44"
        return False

    @api.model
    def _generate_batches_for_period(self, date_from, date_to, company):
        """Agrège les bulletins validés en lots Salaires/Cotisations/Impôts pour la période.

        Utilise sudo afin que la trésorerie puisse récupérer les bulletins même
        sans accès direct au module Paie (les données agrégées restent stockées
        dans les lots, on n'expose pas les bulletins eux‑mêmes dans l'IHM)."""
        self = self.sudo()
        slips = self.env["hr.payslip"].sudo().search([
            ("state", "=", "done"),
            ("company_id", "=", company.id),
            ("date_from", ">=", date_from),
            ("date_to", "<=", date_to),
        ])

        lines = slips.mapped("line_ids")
        grouped = {
            "42": self.env["hr.payslip.line"],
            "43": self.env["hr.payslip.line"],
            "44": self.env["hr.payslip.line"],
        }
        ignored = self.env["hr.payslip.line"]

        for line in lines:
            root = self._get_root_for_line(line)
            if root:
                grouped[root] |= line
            else:
                ignored |= line

        created = False

        for root, root_lines in grouped.items():
            if not root_lines and slips:
                continue
            existing = self.search([
                ("company_id", "=", company.id),
                ("period_start", "=", date_from),
                ("period_end", "=", date_to),
                ("batch_type", "=", root),
            ], limit=1)

            vals = {
                "period_start": date_from,
                "period_end": date_to,
                "batch_type": root,
                "company_id": company.id,
                "currency_id": company.currency_id.id,
            }

            if existing:
                if existing.state == "paid":
                    created = True
                    continue  # ne pas altérer un lot déjà payé
                # Ne pas écraser : ajouter uniquement les nouveaux bulletins/lignes ignorées
                new_slips = [
                    slip_id for slip_id in root_lines.mapped("slip_id").ids
                    if slip_id not in existing.payslip_ids.ids
                ]
                new_lines = [
                    line_id for line_id in root_lines.ids
                    if line_id not in existing.payslip_line_ids.ids
                ]
                new_ignored = [
                    line_id for line_id in ignored.ids
                    if line_id not in existing.ignored_line_ids.ids
                ]
                commands = {}
                if new_slips:
                    commands["payslip_ids"] = [(4, sid) for sid in new_slips]
                if new_lines:
                    commands["payslip_line_ids"] = [(4, lid) for lid in new_lines]
                if new_ignored:
                    commands["ignored_line_ids"] = [(4, lid) for lid in new_ignored]
                if commands:
                    existing.write(commands)
            else:
                vals.update({
                    "payslip_ids": [(6, 0, root_lines.mapped("slip_id").ids)],
                    "payslip_line_ids": [(6, 0, root_lines.ids)],
                    "ignored_line_ids": [(6, 0, ignored.ids)],
                })
                self.create(vals)
            created = True

        # Si aucune ligne de paie n'est disponible, créer tout de même un lot salaire vide
        if not created:
            existing = self.search([
                ("company_id", "=", company.id),
                ("period_start", "=", date_from),
                ("period_end", "=", date_to),
                ("batch_type", "=", "42"),
            ], limit=1)
            vals = {
                "period_start": date_from,
                "period_end": date_to,
                "batch_type": "42",
                "company_id": company.id,
                "currency_id": company.currency_id.id,
            }
            if existing:
                # Ne rien écraser si déjà existant (lot vide toléré)
                pass
            else:
                vals.update({
                    "payslip_ids": [(6, 0, [])],
                    "payslip_line_ids": [(6, 0, [])],
                    "ignored_line_ids": [(6, 0, [])],
                })
                self.create(vals)

        return self

    def _check_payslips_validated(self):
        for batch in self.sudo():
            # Tolère les lots vides (montant zéro) pour permettre un décaissement symbolique
            if not batch.payslip_ids and float(batch.amount_total or 0.0) == 0.0:
                continue
            if not batch.payslip_ids:
                raise UserError(_("Aucun bulletin lié au lot %s.") % batch.display_name)
            invalid = batch.payslip_ids.filtered(lambda slip: slip.state != "done")
            if invalid:
                raise UserError(_("Tous les bulletins doivent être validés (état 'Done')."))

    def _check_account_balance(self):
        for batch in self:
            if float(batch.amount_total or 0.0) == 0.0:
                continue
            accounts = self.env["account.account"].search([
                ("company_id", "=", batch.company_id.id),
                ("code", "=like", batch.batch_type + "%"),
            ])
            if not accounts:
                raise UserError(_("Aucun compte trouvé pour la racine %s") % batch.batch_type)
            aml = self.env["account.move.line"].read_group(
                [("account_id", "in", accounts.ids), ("move_id.state", "=", "posted")],
                ["balance"],
                [],
            )
            balance = aml and aml[0].get("balance", 0.0) or 0.0
            available = abs(balance)
            if batch.amount_total > available + 1e-6:
                raise UserError(
                    _(
                        "Le solde réel des comptes %s (%.2f) est insuffisant pour payer le lot (%.2f)."
                    )
                    % (batch.batch_type, available, batch.amount_total)
                )

    def action_schedule_payment(self):
        """Programmer le règlement : crée l'ordre de décaissement trésorerie sans payer.
        L'état passe à 'scheduled'. Le paiement effectif se fait ultérieurement
        depuis l'ordre de décaissement ou via 'Confirmer le paiement'."""
        self._check_payslips_validated()
        for batch in self:
            if batch.state == "paid":
                continue
            if not batch.partner_id:
                raise UserError(
                    _("Veuillez indiquer le bénéficiaire avant de programmer le règlement du lot %s.")
                    % batch.display_name
                )
            if not batch.journal_id:
                raise UserError(
                    _("Veuillez sélectionner un journal avant de programmer le règlement du lot %s.")
                    % batch.display_name
                )
        self._ensure_payroll_payment()
        # Mettre à jour la date prévue sur l'ordre de décaissement
        for batch in self:
            if batch.payroll_payment_id and batch.planned_payment_date:
                batch.payroll_payment_id.write({
                    "planned_payment_date": batch.planned_payment_date,
                })
        self.filtered(lambda b: b.state not in ("validated", "paid")).write({"state": "scheduled"})

    def action_validate(self):
        self._check_payslips_validated()
        for batch in self:
            if batch.amount_total < 0:
                raise UserError(_("Le montant du lot doit être positif ou nul avant validation."))
        self._check_account_balance()
        self._ensure_payroll_payment()
        self.write({"state": "validated"})

    def action_pay(self):
        for batch in self:
            if batch.state not in ("validated", "to_pay", "scheduled"):
                continue
            batch._check_payslips_validated()
            batch._check_account_balance()
            if not batch.journal_id:
                raise UserError(_("Veuillez sélectionner un journal de paiement."))
            if not batch.partner_id:
                raise UserError(_("Veuillez indiquer le bénéficiaire."))

            if batch.batch_type == "42":
                batch._create_payment_move(fields.Date.context_today(self))
                if batch.payroll_payment_id and batch.payroll_payment_id.state != "paid":
                    batch.payroll_payment_id.state = "paid"
                batch.state = "paid"
                continue

            if batch.payment_id:
                batch.state = "paid"
                continue

            payment = self.env["account.payment"].create({
                "payment_type": "outbound",
                "partner_type": "supplier",
                "partner_id": batch.partner_id.id,
                "amount": batch.amount_total,
                "currency_id": batch.currency_id.id,
                "date": fields.Date.context_today(self),
                "journal_id": batch.journal_id.id,
                "ref": batch.name,
                "narration": _("Paiement lot paie %s (%s - %s)") % (
                    batch.batch_type,
                    batch.period_start,
                    batch.period_end,
                ),
            })
            payment.action_post()
            batch.payment_id = payment.id
            if batch.payroll_payment_id and batch.payroll_payment_id.state != "paid":
                batch.payroll_payment_id.state = "paid"
            batch.state = "paid"

    # --- Helpers ---
    def _ensure_payroll_payment(self):
        """Créer ou mettre à jour l'ordre de décaissement global pour ce lot."""
        Payment = self.env["treasury.payment"]
        for batch in self:
            vals = {
                "payment_type": self._map_payment_type(batch.batch_type),
                "currency_id": batch.currency_id.id,
                "amount_currency": batch.amount_total,
                "payment_date": batch.period_end or batch.period_start or fields.Date.context_today(self),
                "planned_payment_date": batch.period_end or batch.period_start or fields.Date.context_today(self),
                "payment_channel": "transfer",
                "company_id": batch.company_id.id,
                "state": "planned",
                "payroll_batch_id": batch.id,
            }
            if batch.partner_id:
                vals["partner_id"] = batch.partner_id.id
            if batch.journal_id:
                vals["journal_id"] = batch.journal_id.id

            if batch.payroll_payment_id and batch.payroll_payment_id.state != "paid":
                batch.payroll_payment_id.write(vals)
            elif not batch.payroll_payment_id:
                payment = Payment.create(vals)
                batch.payroll_payment_id = payment.id

    def _create_payment_move(self, payment_date=None):
        """Créer l'écriture de règlement des éléments de paie avec contrepartie trésorerie."""
        for batch in self:
            if batch.payment_move_id:
                continue
            if not batch.journal_id:
                raise UserError(_("Veuillez sélectionner un journal de paiement."))

            treasury_account = (
                batch.journal_id.payment_credit_account_id
                or batch.journal_id.default_account_id
            )
            if not treasury_account:
                raise UserError(
                    _("Le journal %s n'a pas de compte de trésorerie défini.")
                    % batch.journal_id.display_name
                )

            grouped = {}
            for line in batch.payslip_line_ids:
                account = line.salary_rule_id.account_credit
                if not account:
                    continue
                amount = abs(line.total)
                grouped[account.id] = grouped.get(account.id, 0.0) + amount

            lines = []
            total = sum(grouped.values())

            if grouped:
                for account_id, amount in grouped.items():
                    lines.append((0, 0, {
                        "name": _("Règlement paie %s") % batch.name,
                        "account_id": account_id,
                        "debit": amount,
                        "credit": 0.0,
                        "partner_id": batch.partner_id.id or False,
                        "company_id": batch.company_id.id,
                    }))
            else:
                # Aucune ligne de paie exploitable : générer quand même une pièce neutre
                lines.append((0, 0, {
                    "name": _("Règlement paie %s") % batch.name,
                    "account_id": treasury_account.id,
                    "debit": 0.0,
                    "credit": 0.0,
                    "partner_id": batch.partner_id.id or False,
                    "company_id": batch.company_id.id,
                }))

            lines.append((0, 0, {
                "name": _("Paiement paie %s") % batch.name,
                "account_id": treasury_account.id,
                "debit": 0.0,
                "credit": total,
                "partner_id": batch.partner_id.id or False,
                "company_id": batch.company_id.id,
            }))

            move_vals = {
                "date": payment_date or fields.Date.context_today(self),
                "ref": _("Paiement éléments de paie %s") % batch.name,
                "journal_id": batch.journal_id.id,
                "company_id": batch.company_id.id,
                "line_ids": lines,
            }
            move = self.env["account.move"].create(move_vals)
            # Laisser en brouillon pour validation comptable manuelle
            batch.payment_move_id = move.id

    @api.model
    def _map_payment_type(self, batch_type):
        if batch_type == "42":
            return "salary"
        if batch_type == "43":
            return "tax"  # cotisations sociales
        if batch_type == "44":
            return "tax"
        return "other"

    def action_create_payment_order(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": "treasury.payroll.order.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_batch_id": self.id,
                "default_partner_id": self.partner_id.id,
                "default_journal_id": self.journal_id.id,
                "default_payment_date": fields.Date.context_today(self),
            },
        }

    def action_view_payment(self):
        self.ensure_one()
        if self.payment_id:
            return {
                "type": "ir.actions.act_window",
                "res_model": "account.payment",
                "res_id": self.payment_id.id,
                "view_mode": "form",
            }
        if self.payment_move_id:
            return {
                "type": "ir.actions.act_window",
                "res_model": "account.move",
                "res_id": self.payment_move_id.id,
                "view_mode": "form",
            }
        return False

    def action_view_payroll_payment(self):
        self.ensure_one()
        if not self.payroll_payment_id:
            return False
        return {
            "type": "ir.actions.act_window",
            "res_model": "treasury.payment",
            "res_id": self.payroll_payment_id.id,
            "views": [[False, "form"]],
            "target": "current",
        }

    def action_view_payslips(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Bulletins de paie — %s") % self.name,
            "res_model": "hr.payslip",
            "view_mode": "list,form",
            "domain": [("id", "in", self.payslip_ids.ids)],
            "target": "current",
        }
