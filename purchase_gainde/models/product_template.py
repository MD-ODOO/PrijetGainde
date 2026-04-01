# Copyright 2018-2019 ForgeFlow, S.L.
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0)

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from . import selection


class ProductTemplate(models.Model):
    _inherit = "product.template"

    approval_state = fields.Selection(
        selection=selection.APPROVAL_STATES,
        string="Approval State",
        default=selection.APPROVAL_STATE_PENDING,
        copy=False,
        tracking=True,
        help="État d'approbation (utilisé par certains écrans/flux de validation).",
    )

    purchase_request = fields.Boolean(
        help="Check this box to generate Purchase Request instead of "
        "generating Requests For Quotation from procurement.",
        company_dependent=True,
    )

    post_id = fields.Many2one(
        comodel_name="account.analytic.account",
        string="Poste budgétaire",
        domain=[("is_budgetary_poste", "=", True)],
        help="Poste budgétaire lié au produit",
    )

    @api.constrains("categ_id")
    def _check_category_has_user_profile(self):
        for template in self:
            if template.categ_id and not template.categ_id.user_profile_id:
                raise ValidationError(
                    _("La nature de produit %s doit avoir un profil RND défini.")
                    % (template.categ_id.display_name,)
                )


class ProductProduct(models.Model):
    _inherit = "product.product"

    purchase_request = fields.Boolean(
        help="Check this box to generate Purchase Request instead of "
        "generating Requests For Quotation from procurement.",
        company_dependent=True,
    )

    post_id = fields.Many2one(
        related="product_tmpl_id.post_id",
        string="Poste budgétaire",
        store=True,
        readonly=False,
        help="Poste budgétaire lié à la variante produit (hérité du produit).",
    )


class ProductCategory(models.Model):
    _inherit = "product.category"

    user_profile_id = fields.Many2one(
        comodel_name="user.profiles",
        string="User Profile",
        domain=[("profile_type", "=", "rnd")],
        ondelete="restrict",
        required=False,
        index=True,
        help="Profil utilisateur lié (depuis account_users_manager)",
    )

    @api.model_create_multi
    def create(self, vals_list):
        """Créer/relier automatiquement un profil RND pour la catégorie.

        - Si aucun ``user_profile_id`` n'est fourni, on cherche un profil
          de type ``rnd``.
        - S'il n'existe pas encore, on le crée avec le nom
          ``RND_<NOM_DE_LA_CATEGORIE>``.
        - Le module ``purchase_gainde`` crée ensuite automatiquement le
          manager de profil lié via l'extension de ``user.profiles``.
        """
        UserProfile = self.env["user.profiles"].sudo()

        for vals in vals_list:
            if not vals.get("user_profile_id"):
                cat_name = vals.get("name") or "RND"
                profile_name = f"RND_{cat_name}"
                # Un profil dédié par catégorie : on cherche d'abord s'il existe
                profile = UserProfile.search(
                    [
                        ("name", "=", profile_name),
                        ("profile_type", "=", "rnd"),
                    ],
                    limit=1,
                )
                if not profile:
                    # On désactive la génération immédiate des Domain Access
                    # pendant la création automatique liée à la catégorie.
                    profile = UserProfile.with_context(gainde_skip_domain_update=True).create(
                        {
                            "name": profile_name,
                            "profile_type": "rnd",
                        }
                    )
                vals["user_profile_id"] = profile.id

        return super(ProductCategory, self).create(vals_list)

    def write(self, vals):
        """Sur écriture, s'assurer qu'une catégorie a un profil RND lié.

        Si, après écriture, une catégorie n'a pas de ``user_profile_id``,
        on applique la même logique que dans ``create``.
        """
        res = super(ProductCategory, self).write(vals)

        UserProfile = self.env["user.profiles"].sudo()
        for categ in self:
            if not categ.user_profile_id:
                cat_name = categ.name or "RND"
                profile_name = f"RND_{cat_name}"
                profile = UserProfile.search(
                    [
                        ("name", "=", profile_name),
                        ("profile_type", "=", "rnd"),
                    ],
                    limit=1,
                )
                if not profile:
                    profile = UserProfile.with_context(gainde_skip_domain_update=True).create(
                        {
                            "name": profile_name,
                            "profile_type": "rnd",
                        }
                    )
                categ.user_profile_id = profile.id

        return res
