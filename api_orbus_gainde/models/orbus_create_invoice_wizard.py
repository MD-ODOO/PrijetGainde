from odoo import fields, models, _
from odoo.exceptions import UserError


class OrbusCreateInvoiceWizard(models.TransientModel):
    _name = "orbus.create.invoice.wizard"
    _description = "Assistant de creation de facture depuis Orbus"

    numero_facture = fields.Char(
        string="Numero de facture Orbus",
        required=True,
        help="Numero de facture tel que fourni par Orbus.",
    )

    company_id = fields.Many2one(
        "res.company",
        string="Societe",
        required=True,
        default=lambda self: self.env.company,
    )

    def action_create_invoice(self):
        """Appelle l'API Orbus pour creer une facture client Odoo.

        Utilise la configuration orbus.api.config de la societe
        choisie, appelle create_odoo_invoice_from_orbus_facture et ouvre
        la facture creee.
        """
        self.ensure_one()

        config = self.env["orbus.api.config"].get_config_for_company(self.company_id)
        invoice = config.create_odoo_invoice_from_orbus_facture(self.numero_facture)
        if not invoice:
            raise UserError(
                _("Aucune facture n'a ete creee a partir de la facture Orbus %s.")
                % self.numero_facture
            )

        action = self.env.ref("account.action_move_out_invoice_type").read()[0]
        action.update(
            {
                "view_mode": "form",
                "res_id": invoice.id,
                "views": [(False, "form")],
            }
        )
        return action
