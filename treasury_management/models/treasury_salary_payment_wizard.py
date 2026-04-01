from odoo import _, api, fields, models
from odoo.exceptions import UserError


class TreasurySalaryPaymentWizard(models.TransientModel):
    _name = "treasury.salary.payment.wizard"
    _description = "Assistant de paiement des salaires"

    employee_id = fields.Many2one(
        "hr.employee", string="Employé", required=True
    )
    partner_id = fields.Many2one(
        "res.partner",
        string="Contact comptable",
        compute="_compute_partner_id",
        store=False,
    )
    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
    )
    currency_id = fields.Many2one(
        "res.currency",
        required=True,
        default=lambda self: self.env.company.currency_id,
        string="Devise",
    )
    amount = fields.Monetary(
        string="Montant à payer",
        currency_field="currency_id",
        required=True,
    )
    payment_date = fields.Date(
        string="Date de paiement",
        required=True,
        default=fields.Date.context_today,
    )
    planned_payment_date = fields.Date(
        string="Date prévue",
        default=fields.Date.context_today,
        help="Date souhaitée de décaissement. Laisser vide pour utiliser la date du jour.",
    )
    payment_channel = fields.Selection(
        [
            ("transfer", "Virement bancaire"),
            ("cheque", "Chèque"),
            ("cash", "Espèces"),
        ],
        string="Mode de paiement",
        required=True,
        default="transfer",
    )
    journal_id = fields.Many2one(
        "account.journal",
        string="Journal de paiement",
        domain="[]",
        required=True,
    )
    responsible_user_id = fields.Many2one(
        "res.users",
        string="Demandé par",
        default=lambda self: self.env.user,
    )
    note = fields.Text(string="Message pour la comptabilité")

    @api.depends("employee_id")
    def _compute_partner_id(self):
        for wizard in self:
            partner = False
            employee = wizard.employee_id
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
            wizard.partner_id = partner

    @api.onchange("payment_channel")
    def _onchange_payment_channel(self):
        domain = []
        allowed_types = []

        if self.payment_channel in ["transfer", "cheque"]:
            domain = [("type", "=", "bank")]
            allowed_types = ["bank"]
        elif self.payment_channel == "cash":
            domain = [("type", "=", "cash")]
            allowed_types = ["cash"]

        # Clear pre-set journal if it does not match the selected channel
        if self.journal_id and allowed_types and self.journal_id.type not in allowed_types:
            self.journal_id = False

        return {"domain": {"journal_id": domain}}

    @api.onchange("employee_id")
    def _onchange_employee_id(self):
        partner = False
        employee = self.employee_id
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
        self.partner_id = partner
        if not partner:
            self.journal_id = False
        return {}

    def action_confirm(self):
        self.ensure_one()
        if not self.partner_id:
            raise UserError(
                _(
                    "L'employé sélectionné n'a pas d'adresse de contact. Ajoutez une adresse privée sur la fiche Employé pour permettre le paiement."
                )
            )

        planned_date = self.planned_payment_date or self.payment_date or fields.Date.context_today(self)

        payment_vals = {
            "payment_type": "salary",
            "employee_id": self.employee_id.id,
            "partner_id": self.partner_id.id,
            "currency_id": self.currency_id.id,
            "amount_currency": self.amount,
            "payment_date": self.payment_date,
            "planned_payment_date": planned_date,
            "payment_channel": self.payment_channel,
            "journal_id": self.journal_id.id,
            "instructions": self.note,
            "responsible_user_id": self.responsible_user_id.id,
            "state": "planned",
            "company_id": self.company_id.id,
        }

        payment = self.env["treasury.payment"].create(payment_vals)

        # Prévenir la comptabilité (et la trésorerie) via une activité TODO
        activity_type_xmlid = "mail.mail_activity_data_todo"
        account_group = self.env.ref("account.group_account_manager", raise_if_not_found=False)
        treasury_group = self.env.ref(
            "treasury_management.group_treasury_df", raise_if_not_found=False
        )
        users = account_group and account_group.users or self.env["res.users"]
        if treasury_group:
            users |= treasury_group.users
        if not users:
            users = self.env.user

        readable_mode = dict(self._fields["payment_channel"].selection).get(
            self.payment_channel, self.payment_channel
        )
        message = _(
            "Demande de paiement de salaire pour %s. Montant: %s %s. Mode: %s."
        ) % (
            self.employee_id.name,
            self.amount,
            self.currency_id.name,
            readable_mode,
        )
        if self.note:
            message += "\n" + self.note

        for user in users:
            payment.activity_schedule(
                activity_type_xmlid,
                user_id=user.id,
                summary=_("Salaire à valider"),
                note=message,
            )

        payment.message_post(
            body=message,
            message_type="comment",
            subtype_xmlid="mail.mt_comment",
        )

        return {
            "type": "ir.actions.act_window",
            "res_model": "treasury.payment",
            "res_id": payment.id,
            "view_mode": "form",
        }
