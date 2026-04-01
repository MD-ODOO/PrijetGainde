from odoo import fields, models, _
from odoo.exceptions import UserError


class OrbusInfinityPanierBatchWizard(models.TransientModel):
    _name = "orbus.infinity.panier.batch.wizard"
    _description = "Assistant d'import des paniers Orbus Infinity"

    company_id = fields.Many2one(
        "res.company",
        string="Société",
        required=True,
        default=lambda self: self.env.company,
    )

    # Filtres possibles selon la collection Postman
    connaissement = fields.Char(string="Connaissement")
    numero_dossier = fields.Char(string="Numéro dossier")
    reference_panier = fields.Char(string="Référence panier")
    numero_paiement = fields.Char(string="Numéro paiement")
    transitaire = fields.Char(string="Transitaire")

    collectionneur = fields.Boolean(
        string="Collectionneur",
        default=False,
        help="Filtre API Infinity (collectionneur). Par défaut: non.",
    )

    date_generate_reference = fields.Date(string="Date génération référence")
    last_fetched_date = fields.Date(string="Dernière date récupérée")
    start_date_paiement = fields.Date(string="Début date paiement")
    end_date_paiement = fields.Date(string="Fin date paiement")
    payer = fields.Selection(
        selection=[
            ("true", "Oui"),
            ("false", "Non"),
        ],
        string="Payé",
    )

    def action_fetch_batch(self):
        """Appelle list-panier et crée un batch de paniers Infinity."""
        self.ensure_one()

        config = self.env["orbus.infinity.api.config"].get_config_for_company(self.company_id)

        def _date_to_str(value):
            if not value:
                return False
            if isinstance(value, str):
                return value
            return fields.Date.to_string(value)

        params = {
            "connaissement": self.connaissement or "",
            "numeroDossier": self.numero_dossier or "",
            "referencePanier": self.reference_panier or "",
            "numeroPaiement": self.numero_paiement or "",
            "transitaire": self.transitaire or "",
            "collectionneur": bool(self.collectionneur),
            "dateGenerateReference": _date_to_str(self.date_generate_reference) or "",
            "lastFetchedDate": _date_to_str(self.last_fetched_date) or "",
            "startDatePaiement": _date_to_str(self.start_date_paiement) or "",
            "endDatePaiement": _date_to_str(self.end_date_paiement) or "",
        }

        if self.payer == "true":
            params["payer"] = "true"
        elif self.payer == "false":
            params["payer"] = "false"

        batch = config.fetch_paniers_batch(params)
        if not batch:
            raise UserError(_("Aucun panier n'a été récupéré."))

        action = self.env.ref(
            "api_orbus_infinity_gainde.action_orbus_infinity_panier_batch"
        ).read()[0]
        action.update(
            {
                "view_mode": "form",
                "res_id": batch.id,
                "views": [(False, "form")],
            }
        )
        return action
