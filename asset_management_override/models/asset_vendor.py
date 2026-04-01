from odoo import models


class AssetVendor(models.Model):
    _inherit = "asset.vendor"

    def unlink(self):
        assets = self.env["asset.management"].search([("vendor_id", "in", self.ids)])
        if assets:
            assets.write({"vendor_id": False})
        return super().unlink()
