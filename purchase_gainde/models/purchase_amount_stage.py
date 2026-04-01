from odoo import api, fields, models, _


class PurchaseAmountStage(models.Model):
    _name = "purchase.amount.stage"
    _description = "Seuil de montant HT d'achat"
    _order = "sequence, amount_limit"

    name = fields.Char(string="Nom", required=True)
    sequence = fields.Integer(string="Séquence", default=10)

    amount_limit = fields.Monetary(string="Seuil montant HT", required=True)
    currency_id = fields.Many2one(
        "res.currency",
        string="Devise",
        required=True,
        default=lambda self: self.env.company.currency_id.id,
    )

    comparator = fields.Selection(
        [
            ("<", "<"),
            ("<=", "<="),
            (">", ">"),
            (">=", ">="),
        ],
        string="Comparateur",
        required=True,
        default=">",
        help="Opérateur de comparaison appliqué au montant HT de la commande.",
    )

    treatment_type = fields.Selection(
        [
            ("normal", "Normal"),
            ("tdr", "TDR"),
            ("call_tender", "Appel d'offres"),
        ],
        string="Type de traitement",
        required=True,
        default="normal",
    )

    message = fields.Text(
        string="Message bloquant",
        help="Message affiché à l'utilisateur lorsque ce seuil bloque la confirmation.",
    )

    active = fields.Boolean(default=True)

    @api.model
    def _get_order_amount_untaxed_in_stage_currency(self, order):
        """Return order.amount_untaxed converted in this stage currency."""
        self.ensure_one()
        company = order.company_id or self.env.company
        date = order.date_order or fields.Date.today()
        return order.currency_id._convert(
            order.amount_untaxed,
            self.currency_id,
            company,
            date,
        )

    def _match_treatment_conditions(self, order):
        """Return True if non-amount conditions match for this stage.

        Niveaux imbriqués:
        - normal: conditions de base
            * plus de 2 devis/PO alternatifs (alternative_po_ids)
              OU
            * achat urgent (is_urgent_purchase)
        - tdr: inclut les conditions *normal* + has_tdr
        - call_tender: inclut *tdr* + *normal* + requisition_type == 'blanket_order'
        """

        self.ensure_one()

        # Récupération robuste des champs, même si certains ne sont
        # pas présents (autres modules).
        alternative_po_ids = getattr(order, "alternative_po_ids", False) or self.env["purchase.order"]
        alt_count = len(alternative_po_ids)
        is_urgent = bool(getattr(order, "is_urgent_purchase", False))
        has_tdr_flag = bool(getattr(order, "has_tdr", False))
        requisition_type = getattr(order, "requisition_type", False)

        # Niveau 1 : normal
        normal_cond = (alt_count > 2) or is_urgent
        if self.treatment_type == "normal":
            return normal_cond

        # Niveau 2 : TDR (inclut normal)
        tdr_cond = normal_cond and has_tdr_flag
        if self.treatment_type == "tdr":
            return tdr_cond

        # Niveau 3 : Appel d'offres (inclut TDR + normal)
        call_tender_cond = tdr_cond and requisition_type == "blanket_order"
        if self.treatment_type == "call_tender":
            return call_tender_cond

        return False

    def match_order(self, order):
        """Return True if order untaxed total matches this stage condition."""
        self.ensure_one()
        # Vérifie d'abord les conditions fonctionnelles liées au type de traitement
        if not self._match_treatment_conditions(order):
            return False

        amount = self._get_order_amount_untaxed_in_stage_currency(order)
        limit = self.amount_limit

        if self.comparator == ">":
            return amount > limit
        if self.comparator == ">=":
            return amount >= limit
        if self.comparator == "<":
            return amount < limit
        if self.comparator == "<=":
            return amount <= limit
        return False
