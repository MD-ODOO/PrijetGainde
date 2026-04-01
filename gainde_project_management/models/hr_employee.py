from odoo import models, fields, api, _
from odoo.exceptions import UserError
import datetime
from datetime import timedelta
from dateutil.relativedelta import relativedelta
from odoo.addons.mail.models.mail_thread import MailThread


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    rate_profile_id = fields.Many2one(
        'hr.employee.rate.profile',
        string="Profil coût horaire"
    )
    availability_calendar = fields.Many2one('resource.calendar',
                                            string='Calendrier de Disponibilité')

    @api.onchange('rate_profile_id')
    def _onchange_rate_profile_id(self):
        if self.rate_profile_id:
            self.hourly_cost = self.rate_profile_id.hourly_rate


    @api.model
    def init(self):
        """ Calcule le prochain lundi à 8h lors de l'installation/mise à jour """
        cron = self.env.ref('gainde_project_management.cron_timesheet_reminder_weekly', raise_if_not_found=False)
        if cron and (not cron.nextcall or cron.nextcall < fields.Datetime.now()):
            # Calcule le prochain lundi 08:00
            next_monday = datetime.datetime.now() + relativedelta(weekday=0, hour=8, minute=0, second=0)
            if next_monday < datetime.datetime.now():
                next_monday += relativedelta(weeks=1)
            cron.nextcall = next_monday

    @api.model
    def _send_timesheet_reminders(self):
        """ Envoie un rappel par email aux employés qui n'ont pas saisi leurs timesheets pour la semaine précédente """
        # Configurable via ir.config_parameter
        reminder_enabled = self.env['ir.config_parameter'].sudo().get_param(
            'gainde_project_management.timesheet_reminder_enabled', 'True'
        ) == 'True'
        if not reminder_enabled:
            return

        # 2. Dates (Semaine dernière)
        today = fields.Date.today()
        last_week_end = today - timedelta(days=today.weekday() + 1)
        last_week_start = last_week_end - timedelta(days=6)

        # 3. Employés cibles
        employees = self.search([
            ('user_id', '!=', False),
            ('active', '=', True),
            ('department_id', '!=', False),
        ])
        if not employees:
            return

        # 4. Calcul des heures (Version Odoo 18)
        # On utilise _read_group qui renvoie des tuples (employee_id, unit_amount_sum)
        timesheet_data = self.env['account.analytic.line']._read_group(
            domain=[
                ('employee_id', 'in', employees.ids),
                ('date', '>=', last_week_start),
                ('date', '<=', last_week_end),
            ],
            groupby=['employee_id'],
            aggregates=['unit_amount:sum'],
        )
        # Mapping : {employee_id: total_hours}
        timesheet_hours = {emp.id: total for emp, total in timesheet_data}

        # 5. Seuil
        min_hours = float(self.env['ir.config_parameter'].sudo().get_param(
            'gainde_project_management.timesheet_min_hours_week', '8.0'
        ))

        template = self.env.ref(
            'gainde_project_management.email_template_timesheet_reminder',
            raise_if_not_found=False)
        if not template:
            return  # Ou loggez une erreur

        sent_count = 0
        for employee in employees:
            hours = timesheet_hours.get(employee.id, 0.0)
            if hours < min_hours:
                # Préparation du contexte pour le template Jinjava
                ctx = {
                    'week_start': last_week_start.strftime('%d/%m/%Y'),
                    'week_end': last_week_end.strftime('%d/%m/%Y'),
                    'hours_filled': round(hours, 1),
                    'min_hours': min_hours,
                }

                # Envoi
                template.with_context(**ctx).send_mail(
                    employee.id,
                    force_send=True,
                    raise_exception=False
                )
                sent_count += 1

        return sent_count
