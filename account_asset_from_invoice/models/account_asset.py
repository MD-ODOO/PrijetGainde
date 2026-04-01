from odoo import api, fields, models


class AccountAsset(models.Model):
    _inherit = "account.asset"

    compte_tiers = fields.Char(string="Compte de tiers")

    @api.depends('original_move_line_ids')
    def _compute_related_purchase_value(self):
        for asset in self:
            related_purchase_value = sum(asset.original_move_line_ids.mapped('balance'))
            if asset.account_asset_id.multiple_assets_per_line and len(asset.original_move_line_ids) == 1:
                related_purchase_value /= max(1, int(asset.original_move_line_ids.quantity))

            move = asset.original_move_line_ids[:1].move_id
            if move and move.move_type in ('in_invoice', 'in_refund'):
                related_purchase_value = -related_purchase_value

            asset.related_purchase_value = related_purchase_value
