from odoo import fields, models


class AccountMove(models.Model):
    _inherit = "account.move"

    # Compat: certains modules attendent un champ `attachment_id` sur account.move.
    # On le mappe vers `message_main_attachment_id`.
    attachment_id = fields.Many2one(
        "ir.attachment",
        string="Pièce jointe principale",
        related="message_main_attachment_id",
        readonly=False,
    )

    orbus_infinity_reference_panier = fields.Char(string="Référence panier Infinity")
    orbus_infinity_numero_dossier = fields.Char(string="Numéro dossier Infinity")
    orbus_infinity_numero_paiement = fields.Char(string="Numéro paiement Infinity")
    orbus_infinity_source = fields.Char(string="Source / moyen de paiement Infinity")

    orbus_infinity_date_paiement = fields.Datetime(string="Date paiement Infinity")
    orbus_infinity_date_generate_reference = fields.Datetime(
        string="Date génération référence Infinity"
    )

    orbus_infinity_payer = fields.Boolean(string="Payé (Infinity)")

    orbus_infinity_transitaire = fields.Char(string="Transitaire")
    orbus_infinity_connaissement = fields.Char(string="Connaissement")

    # IMPORTANT: garder ce champ en Selection (legacy) pour éviter les erreurs
    # d'upgrade liées au nettoyage des valeurs de sélection.
    orbus_infinity_destination = fields.Selection(
        selection=[
            ("IMPORT", "Import"),
            ("EXPORT", "Export"),
            ("TRANSIT", "Transit"),
        ],
        string="Destination (legacy)",
    )

    orbus_infinity_destination_pays = fields.Char(string="Destination (Pays)")

    orbus_infinity_montant_facture = fields.Float(string="Montant facture (Infinity)")

    orbus_infinity_factures_json = fields.Text(
        string="Factures Infinity (JSON)",
        help="Détail 'factures' renvoyé par l'API Infinity.",
    )

    orbus_infinity_batch_line_id = fields.Many2one(
        "orbus.infinity.panier.batch.line",
        string="Ligne batch Infinity",
        readonly=True,
        ondelete="set null",
    )
