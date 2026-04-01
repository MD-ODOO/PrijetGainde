from odoo import models, fields, api, _


class AssetTransferEntry(models.Model):
    _inherit = "asset.transfer.entry"

    localisation = fields.Many2one(
        "asset.localisation",
        string="Localisation",
        help="Localisation de l'actif lors du transfert",
    )

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for record in records:
            if record.status == "assigned" and record.asset_id:
                record.asset_id._notify_accounting(
                    _("Transfert effectué pour l'actif : %s") % (record.asset_id.display_name or record.asset_id.name)
                )
        return records

    def write(self, vals):
        notify = "status" in vals and vals.get("status") == "assigned"
        res = super().write(vals)
        if notify:
            for record in self:
                if record.status == "assigned" and record.asset_id:
                    record.asset_id._notify_accounting(
                        _("Transfert effectué pour l'actif : %s") % (record.asset_id.display_name or record.asset_id.name)
                    )
        return res


