from odoo import models, fields, _


class PurchaseTdr(models.Model):
    _name = "purchase.tdr"
    _description = "Terms of Reference for Purchase Orders"
    _order = "date desc, name"

    name = fields.Char(string="Référence TDR", required=True)
    description = fields.Text(string="Description")
    date = fields.Date(string="Date du TDR")

    state = fields.Selection(
        [
            ("draft", "Brouillon"),
            ("approved", "Approuvé"),
            ("cancelled", "Annulé"),
        ],
        string="État",
        default="draft",
    )

    # Fichier TDR (PDF ou autre) stocké en pièce jointe
    file_data = fields.Binary(
        string="Fichier TDR",
        attachment=True,
        help="Téléchargez ici le document TDR (de préférence au format PDF).",
    )
    file_name = fields.Char(string="Nom du fichier")

    purchase_ids = fields.One2many(
        comodel_name="purchase.order",
        inverse_name="tdr_linked_id",
        string="Commandes associées",
    )

    # ------------------------------------------------------------
    # Actions de changement d'état
    # ------------------------------------------------------------

    def action_set_draft(self):
        """Remet le TDR en brouillon."""
        for rec in self:
            rec.state = "draft"

    def action_approve(self):
        """Passe le TDR à l'état approuvé."""
        for rec in self:
            rec.state = "approved"

    def action_cancel(self):
        """Annule le TDR."""
        for rec in self:
            rec.state = "cancelled"
