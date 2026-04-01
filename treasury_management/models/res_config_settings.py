from odoo import models, fields


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    treasury_alert_threshold = fields.Float(
        string="Seuil d'alerte trésorerie",
        config_parameter="treasury_management.alert_threshold",
        default=0.0,
    )
    treasury_alert_days = fields.Integer(
        string="Horizon d'alerte (jours)",
        config_parameter="treasury_management.alert_days",
        default=30,
    )
    treasury_approval_threshold = fields.Float(
        string="Seuil validation manager",
        config_parameter="treasury_management.approval_threshold",
        default=0.0,
    )
    treasury_cash_threshold = fields.Float(
        string="Seuil caisse",
        config_parameter="treasury_management.cash_threshold",
        default=100000.0,
    )
    treasury_cash_journal_id = fields.Many2one(
        "account.journal",
        string="Journal caisse dépenses",
        domain="[('type','=','cash')]",
        config_parameter="treasury_management.cash_journal_id",
    )

    payroll_code_net = fields.Char(
        string="Codes net à payer",
        default="NET",
        config_parameter="treasury_management.payroll_code_net",
        help="Codes de règles de paie utilisés pour le net à payer (séparés par des virgules).",
    )
    payroll_code_ipress = fields.Char(
        string="Codes IPRESS",
        default="IPRESS,IPRES",
        config_parameter="treasury_management.payroll_code_ipress",
        help="Codes de cotisation IPRESS (séparés par des virgules).",
    )
    payroll_code_cfce = fields.Char(
        string="Codes CFCE",
        default="CFCE",
        config_parameter="treasury_management.payroll_code_cfce",
        help="Codes de cotisation CFCE (séparés par des virgules).",
    )
    payroll_code_family_allowance = fields.Char(
        string="Codes allocations familiales",
        default="AF,ALLOCFAM",
        config_parameter="treasury_management.payroll_code_family_allowance",
        help="Codes des allocations familiales (séparés par des virgules).",
    )
    payroll_code_income_tax = fields.Char(
        string="Codes impôt sur le revenu",
        default="IR,IRPP,IRRF",
        config_parameter="treasury_management.payroll_code_income_tax",
        help="Codes d'impôt sur le revenu (séparés par des virgules).",
    )
