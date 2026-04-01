from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class ProjectTask(models.Model):
    _inherit = 'project.task'

    planned_hours = fields.Float(string="Heures prévues", default=0.0,
                                 help="Nombre d'heures prévues pour cette tâche (utilisé dans le Gantt et la charge)",
                                 required=True)
    user_ids = fields.Many2many('res.users', relation='project_task_user_rel',
                                column1='task_id', column2='user_id',
                                string='Assignees',
                                default=lambda self: self.env.user,
                                domain="['|', ('share', '=', False), ('share', '=', True)]",
                                # <--- C'est ici
                                context={'active_test': False}
                                )

    def action_mark_done(self):
        for task in self:
            if not task.timesheet_ids:
                raise ValidationError(
                    _("Vous devez saisir du temps avant de clôturer la tâche.")
                )
        return super().action_mark_done()
