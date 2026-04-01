import base64
import math
import os

from odoo import api, models


def _load_custom_logo():
    logo_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static", "logo.png")
    try:
        with open(logo_path, "rb") as f:
            return base64.b64encode(f.read())
    except FileNotFoundError:
        return False


class ReportAssetLabelCustomGainde(models.AbstractModel):
    _name = "report.asset_management_override.label_custom"
    _description = "Custom Asset Label Report"

    @api.model
    def _get_report_values(self, docids, data=None):
        docs = self.env["asset.management"].browse(docids)
        return {
            "docs": docs,
            "logo_data": _load_custom_logo(),
        }


class ReportAssetLabel2x7(models.AbstractModel):
    _name = "report.asset_management_override.report_assettemplatelabel2x7"
    _description = "Asset Label 2x7 Report"

    @api.model
    def _get_report_values(self, docids, data=None):
        assets = self.env["asset.management"].browse(docids)

        quantity = {}
        for asset in assets:
            barcode = asset.barcode or asset.name or str(asset.id)
            quantity[asset] = [(barcode, 1)]

        labels_per_page = 14
        total_labels = len(assets)
        page_numbers = math.ceil(total_labels / labels_per_page) or 1

        return {
            "docs": assets,
            "quantity": quantity,
            "page_numbers": page_numbers,
            "logo_data": _load_custom_logo(),
        }
