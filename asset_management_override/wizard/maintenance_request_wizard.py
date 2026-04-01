from odoo import models, fields, api, _
from odoo.exceptions import UserError


class MaintenanceRequestWizard(models.TransientModel):
    _name = 'maintenance.request.wizard'
    _description = 'Wizard pour créer une demande de maintenance'

    asset_id = fields.Many2one(
        'asset.management',
        string='Actif',
        required=True,
        readonly=True
    )
    
    description = fields.Text(
        string='Description de la maintenance',
        required=True,
        help='Décrivez le problème ou la maintenance nécessaire'
    )
    
    maintenance_type = fields.Selection(
        [('corrective', 'Corrective'), ('preventive', 'Préventive')],
        string='Type de maintenance',
        default='corrective',
        required=True
    )
    
    schedule_date = fields.Datetime(
        string='Date prévue',
        default=fields.Datetime.now,
        help='Date à laquelle la maintenance est prévue'
    )

    def action_confirm(self):
        """Créer la demande de maintenance et mettre l'actif en maintenance"""
        self.ensure_one()
        
        if not self.description:
            raise UserError(_("La description de la maintenance est obligatoire."))
        
        # Récupérer ou créer l'équipement de maintenance basé sur le product_id
        equipment = None
        if self.asset_id.product_id:
            # Chercher si un équipement existe déjà avec le nom du produit
            equipment = self.env['maintenance.equipment'].search([
                ('name', '=', self.asset_id.product_id.name)
            ], limit=1)
            
            # Si pas trouvé, créer un nouvel équipement
            if not equipment:
                equipment = self.env['maintenance.equipment'].create({
                    'name': self.asset_id.product_id.name,
                })
        
        # Créer la demande de maintenance
        maintenance_request = self.env['maintenance.request'].create({
            'name': self.description,
            'description': self.description,
            'maintenance_type': self.maintenance_type,
            'schedule_date': self.schedule_date,
            'request_date': fields.Date.today(),
            'owner_user_id': self.env.user.id,
            'equipment_id': equipment.id if equipment else False,
        })
        
        # Mettre l'actif en statut maintenance et lier la demande
        self.asset_id.write({
            'status': 'repair',
            'maintenance_request_id': maintenance_request.id,
        })
        
        # Notification
        self.asset_id._notify_accounting(
            _("Actif mis en maintenance : %s") % self.description
        )
        
        return {'type': 'ir.actions.act_window_close'}

