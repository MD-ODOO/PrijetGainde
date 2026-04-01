from odoo import models, fields, api, _


class AccountAsset(models.Model):
    _inherit = "account.asset"

    barcode = fields.Char(string="Barcode", copy=False)

    asset_management_id = fields.Many2one(
        "asset.management",
        string="Actif immobilisé",
        compute="_compute_asset_management_id",
        store=False,
    )

    def _compute_asset_management_id(self):
        for rec in self:
            rec.asset_management_id = self.env["asset.management"].search(
                [("account_asset_id", "=", rec.id)], limit=1
            )

    def action_open_asset_management(self):
        """Naviguer vers l'actif immobilisé lié."""
        self.ensure_one()
        am = self.asset_management_id
        if not am:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'message': _("Aucun actif immobilisé lié à cet actif comptable."),
                    'type': 'warning',
                },
            }
        return {
            'type': 'ir.actions.act_window',
            'name': _('Actif immobilisé'),
            'res_model': 'asset.management',
            'res_id': am.id,
            'view_mode': 'form',
            'target': 'current',
        }
