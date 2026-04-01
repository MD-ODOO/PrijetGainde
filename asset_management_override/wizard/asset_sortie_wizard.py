from odoo import models, fields, api


class AssetSortieWizard(models.TransientModel):
    _name = 'asset.sortie.wizard'
    _description = 'Wizard de confirmation de sortie d\'actif'

    asset_id = fields.Many2one('asset.management', string='Actif', required=True)
    confirmation = fields.Boolean(string='Je confirme la sortie de cet actif', default=False)

    def action_confirm(self):
        """Confirmer la sortie de l'actif"""
        if self.confirmation and self.asset_id:
            self.asset_id.write({'status': 'destroyed'})
        return {'type': 'ir.actions.act_window_close'}

