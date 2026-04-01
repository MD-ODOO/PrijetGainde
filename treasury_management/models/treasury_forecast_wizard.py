from odoo import models, fields, _


class TreasuryForecastGenerateWizard(models.TransientModel):
    _name = "treasury.forecast.generate.wizard"
    _description = "Générer des prévisions de trésorerie"

    start_date = fields.Date(required=True, default=fields.Date.context_today)
    end_date = fields.Date(required=True)
    period_type = fields.Selection(
        [("month", "Mensuel"), ("quarter", "Trimestriel")],
        default="month",
        required=True,
    )

    def action_generate(self):
        self.ensure_one()
        Forecast = self.env["treasury.forecast"].sudo()
        Forecast.generate_from_sources(
            start_date=self.start_date,
            end_date=self.end_date,
            period_type=self.period_type,
        )
        domain = [
            ("date", ">=", self.start_date),
            ("date", "<=", self.end_date),
        ]
        grouped = Forecast.read_group(
            domain,
            ["amount", "signed_amount"],
            ["flow_direction"],
        )
        incoming = sum(g["amount"] for g in grouped if g["flow_direction"] == "in")
        outgoing = sum(g["amount"] for g in grouped if g["flow_direction"] == "out")
        net = incoming - outgoing
        currency = self.env.company.currency_id
        return {
            "type": "ir.actions.act_window",
            "name": _("Prévisions %(start)s → %(end)s (Net: %(net)s)") % {
                "start": self.start_date,
                "end": self.end_date,
                "net": f"{currency.symbol} {net:,.2f}",
            },
            "res_model": "treasury.forecast",
            "view_mode": "list,graph,pivot",
            "domain": domain,
            "context": {
                "search_default_flow_direction": 1,
                "group_by": ["period_type", "flow_direction"],
            },
        }
