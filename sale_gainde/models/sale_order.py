from odoo import api, models, _
from odoo.exceptions import UserError


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    def _sale_gainde_compute_analytic_distribution(self):
        """Calcule et applique la distribution analytique pour cette ligne de vente.

        Utilise directement le center_id et le post_id du produit pour construire
        la clé analytique au format "{center_id},{post_id}" avec 100%.
        """
        for line in self:
            product = line.product_id
            if not product:
                continue

            tmpl = product.product_tmpl_id

            # Récupération du centre budgétaire
            center = tmpl.center_id if "center_id" in tmpl._fields else None
            if not center and "center_id" in product._fields:
                center = product.center_id

            # Récupération du poste budgétaire
            poste = tmpl.post_id if "post_id" in tmpl._fields else None
            if not poste and "post_id" in product._fields:
                poste = product.post_id

            if not center:
                raise UserError(
                    _("Centre budgétaire introuvable pour le produit « %s ».\n"
                      "Veuillez renseigner le champ « Centre budgétaire » sur la fiche produit.")
                    % product.display_name
                )

            if not poste:
                raise UserError(
                    _("Poste budgétaire introuvable pour le produit « %s ».\n"
                      "Veuillez renseigner le champ « Poste budgétaire » sur la fiche produit.")
                    % product.display_name
                )

            key = f"{center.id},{poste.id}"
            line.analytic_distribution = {key: 100}

    @api.onchange("product_id")
    def _sale_gainde_onchange_product_id(self):
        """Déclenche le mapping analytique dès la sélection du produit."""
        self._sale_gainde_compute_analytic_distribution()

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        lines._sale_gainde_compute_analytic_distribution()
        return lines

    def write(self, vals):
        res = super().write(vals)
        if "product_id" in vals:
            self._sale_gainde_compute_analytic_distribution()
        return res
