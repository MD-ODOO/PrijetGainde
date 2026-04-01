from odoo import models, fields, _
from odoo.exceptions import UserError
from collections import defaultdict
import base64


# =====================================================
# MOIS EN FRANÇAIS (ROBUSTE, SANS LOCALE)
# =====================================================
MONTHS_FR = {
    1: 'JANVIER',
    2: 'FÉVRIER',
    3: 'MARS',
    4: 'AVRIL',
    5: 'MAI',
    6: 'JUIN',
    7: 'JUILLET',
    8: 'AOÛT',
    9: 'SEPTEMBRE',
    10: 'OCTOBRE',
    11: 'NOVEMBRE',
    12: 'DÉCEMBRE',
}


class HrPayslip(models.Model):
    _inherit = 'hr.payslip'

    sent_to_employee = fields.Boolean(
        string="Envoyé à l'employé",
        default=False
    )

    # =====================================================
    # REPORT (SANS ID)
    # =====================================================
    def _get_gainde_report(self):
        report = self.env['ir.actions.report'].sudo()._get_report_from_name(
            'paie_gainde.report_payroll_cesag'
        )
        if not report:
            raise UserError("Le report Bulletin Gaindé est introuvable.")
        return report

    # =====================================================
    # SUJET EMAIL
    # =====================================================
    def _get_subject_from_slip(self, slip):
        date_from = slip.date_from
        date_to = slip.date_to

        month_label = MONTHS_FR.get(date_to.month, '')
        year = date_to.year

        return (
            f"Bulletin de paie du "
            f"{date_from.strftime('%d')} au {date_to.strftime('%d')} "
            f"{month_label} {year}"
        )

    # =====================================================
    # ENVOI GROUPÉ (TEST / CRON)
    # =====================================================
    def _send_grouped(self, slips, test=False):
        report = self._get_gainde_report()

        slips_by_employee = defaultdict(lambda: self.env['hr.payslip'])
        for slip in slips:
            slips_by_employee[slip.employee_id] |= slip

        Mail = self.env['mail.mail'].sudo()
        Attachment = self.env['ir.attachment'].sudo()

        for employee, emp_slips in slips_by_employee.items():

            if not employee.work_email:
                continue

            # Sujet basé sur le premier bulletin
            subject = self._get_subject_from_slip(emp_slips[0])
            if test:
                subject = f" {subject}"

            mail = Mail.create({
                'subject': subject,
                'email_to': employee.work_email,
                'body_html': f"""
                     <p>Bonjour {self.employee_id.name},</p>
                <p>Veuillez trouver en pièce jointe votre bulletin de paie.</p>
                <p>Cordialement,<br/>Service RH</p>
            """,
            })
            

            for slip in emp_slips:
                pdf, _ = report._render_qweb_pdf(
                    report.report_name,
                    res_ids=[slip.id]
                )

                attachment = Attachment.create({
                    'name': f"Bulletin_{slip.name}.pdf",
                    'type': 'binary',
                    'datas': base64.b64encode(pdf),
                    'mimetype': 'application/pdf',
                })

                mail.write({
                    'attachment_ids': [(4, attachment.id)]
                })

            mail.send()

            if not test:
                emp_slips.write({'sent_to_employee': True})

    # =====================================================
    # CRON – FIN DE MOIS
    # =====================================================
    def cron_send_grouped_payslips(self):
        slips = self.search([
            ('state', '=', 'done'),
            ('sent_to_employee', '=', False),
            ('employee_id.work_email', '!=', False),
        ])

        if slips:
            self._send_grouped(slips, test=False)

    # =====================================================
    # BOUTON – ENVOI SIMPLE
    # =====================================================
    def action_payslip_send(self):
        self.ensure_one()

        if self.state != 'done':
            raise UserError("Le bulletin doit être validé (DONE).")

        if not self.employee_id.work_email:
            raise UserError("Aucun email renseigné pour cet employé.")

        report = self._get_gainde_report()
        subject = self._get_subject_from_slip(self)

        pdf, _ = report._render_qweb_pdf(
            report.report_name,
            res_ids=self.ids
        )

        attachment = self.env['ir.attachment'].sudo().create({
            'name': f"Bulletin_{self.name}.pdf",
            'type': 'binary',
            'datas': base64.b64encode(pdf),
            'mimetype': 'application/pdf',
        })

        mail = self.env['mail.mail'].sudo().create({
            'subject': subject,
            'email_to': self.employee_id.work_email,
            'body_html': f"""
                <p>Bonjour {self.employee_id.name},</p>
                <p>Veuillez trouver en pièce jointe votre bulletin de paie.</p>
                <p>Cordialement,<br/>Service RH</p>
            """,
            'attachment_ids': [(4, attachment.id)],
        })

        mail.send()

        self.write({'sent_to_employee': True})

    # =====================================================
    # BOUTON – TEST ENVOI GROUPÉ (LISTE)
    # =====================================================
    def action_test_send_grouped_payslips(self):
        slips = self.filtered(
            lambda s: s.state == 'done' and s.employee_id.work_email
        )

        if not slips:
            raise UserError(
                "Veuillez sélectionner au moins un bulletin validé avec un email."
            )

        self._send_grouped(slips, test=True)

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Test terminé',
                'message': 'Les emails de test groupés ont été envoyés.',
                'sticky': False,
            }
        }
