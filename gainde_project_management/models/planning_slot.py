from odoo import models, fields, api


class PlanningSlot(models.Model):
    _inherit = 'planning.slot'

    workload_percentage = fields.Float(
        string="Charge (%)",
        compute='_compute_workload_percentage',
        store=True,
        help="Pourcentage de charge de cet employé sur ce slot"
    )

    @api.depends('duration', 'resource_id')
    def _compute_workload_percentage(self):
        for slot in self:
            if not slot.resource_id or not slot.duration:
                slot.workload_percentage = 0.0
                continue
            # Exemple simple : durée du slot / capacité journalière de l'employé

            daily_hours = slot.resource_id.calendar_id.hours_per_day or 8.0
            slot.workload_percentage = round(
                (slot.duration / daily_hours) * 100.0, 1)

            # percentage = (slot.duration / daily_hours) * 100.0
            # Optionnel : cap à 100% ou laisse dépasser pour voir les surbookings
            # slot.workload_percentage = min(percentage, 200.0)
