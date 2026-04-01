# -*- coding: utf-8 -*-
##############################################################################
#
#    DevIntelle Solution(Odoo Expert)
#    Copyright (C) 2015 Devintelle Soluation (<http://devintellecs.com/>)
#
##############################################################################
import xlwt
from io import BytesIO
import base64
import pytz
from odoo import models, fields, api
from odoo.exceptions import UserError
from odoo.http import request
import logging

_logger = logging.getLogger(__name__)
class EmpTimesheetExcelWizardPortal(models.TransientModel):
    _name = 'helpdesk.ticket.excel.wizard.portal'

    start_date = fields.Date('Start Date', default=lambda self: fields.Date.context_today(self))
    end_date = fields.Date('End Date', default=lambda self: fields.Date.context_today(self))
    excel_file = fields.Binary('Excel File')
    file_name = fields.Char('Excel File', size=64)

    def helpdesk_ticket_excel(self):
        workbook = xlwt.Workbook()
        worksheet = workbook.add_sheet('Tickets')

        # Define styles
        header_style = xlwt.easyxf('font:height 250; align: horiz center; font:bold True;')
        date_style = xlwt.easyxf(num_format_str='DD-MM-YYYY HH:MM:SS')
        default_style = xlwt.easyxf()
        title_style = xlwt.easyxf('font:height 400; align: horiz center; font:bold True;')

        # Set column widths (adjust as needed)
        worksheet.col(0).width = 256 * 30
        worksheet.col(1).width = 256 * 30
        worksheet.col(2).width = 256 * 30
        worksheet.col(3).width = 256 * 30
        worksheet.col(4).width = 256 * 30
        worksheet.col(5).width = 256 * 30
        worksheet.col(6).width = 256 * 30
        worksheet.col(7).width = 256 * 30
        worksheet.col(8).width = 256 * 30
        worksheet.col(9).width = 256 * 30
        worksheet.col(10).width = 256 * 30

        # Add top header lines
        worksheet.write_merge(0, 1, 1, 3, 'Helpdesk Tickets Report', title_style)

        # Retrieve export template
        export_template = self.env['export.template'].search([('model_id.model', '=', 'helpdesk.ticket')], limit=1)

        if not export_template:
            worksheet.col(0).width = 256 * 50
            worksheet.col(1).width = 256 * 20
            worksheet.col(2).width = 256 * 25
            worksheet.col(3).width = 256 * 25
            
            # Add headers
            headers = ['Ticket', 'Reported on', 'Assigned to', 'Stage']
            for col_num, header in enumerate(headers):
                worksheet.write(3, col_num, header, header_style)

            worksheet.row(3).height_mismatch = True
            worksheet.row(3).height = 256 * 2

            domain = [
                ('create_date', '>=', self.start_date),
                ('create_date', '<=', self.end_date)
            ]

            tickets = request.env['helpdesk.ticket'].search(domain)

            if not tickets:
                _logger.warning("No tickets found for the given criteria.")

            for row_num, ticket in enumerate(tickets, start=4):
                worksheet.write(row_num, 0, ticket.name or '')
                #worksheet.write(row_num, 1, ticket.create_date.strftime('%d-%m-%Y %H:%M:%S') if ticket.create_date else '', date_style)
                worksheet.write(row_num, 1, ticket.create_date.astimezone(pytz.timezone(ticket.env.user.tz)).strftime('%d-%m-%Y %H:%M:%S') if ticket.create_date else '', date_style)
                worksheet.write(row_num, 2, ticket.user_id.name or '')
                worksheet.write(row_num, 3, ticket.stage_id.name or '')

        else:
            # Define styles
            header_style = xlwt.easyxf('font:height 250; align: horiz center;font:bold True;')
            header_style1 = xlwt.easyxf('font:height 200;font:bold True;')
            task_style1 = xlwt.easyxf(' align: horiz left;')
            title_style = xlwt.easyxf('font:height 400; align: horiz center;font:bold True;')
            date_style = xlwt.easyxf(num_format_str='DD-MM-YYYY')
            default_style = xlwt.easyxf()
        
            field_ids = export_template.field_ids.sorted(key=lambda r: r.sequence)

            worksheet.row(3).height_mismatch = True
            worksheet.row(3).height = 256 * 2

            # Write header
            headers = [field.field_label or field.field_id.field_description for field in field_ids]
            for col_num, header in enumerate(headers):
                worksheet.write(3, col_num, header, header_style)

            # Search for helpdesk tickets
            domain = [
                ('create_date', '>=', self.start_date),
                ('create_date', '<=', self.end_date)
            ]
            tickets = self.env['helpdesk.ticket'].search(domain)

            if not tickets:
                raise UserError('No tickets found for the given criteria.')

            priority_mapping = {
                '0': 'Low Priority',
                '1': 'Medium Priority',
                '2': 'High Priority',
                '3': 'Urgent Priority'
            }

            # Write data
            for row_num, ticket in enumerate(tickets, start=4):
                for col_num, field in enumerate(field_ids):
                    field_value = getattr(ticket, field.field_id.name, '')

                    if field.field_id.name == 'priority':
                        field_value = priority_mapping.get(field_value, '')
                    elif field.field_id.name == 'close_date':
                        if field_value:
                            tz = ticket.env.user.tz
                            field_value = field_value.astimezone(pytz.timezone(tz)).strftime('%d-%m-%Y %H:%M:%S')

                    elif isinstance(field_value, models.BaseModel):
                        field_value = field_value.name_get()[0][1] if field_value else ''
                    elif isinstance(field_value, fields.Datetime):
                        field_value = field_value.strftime('%d-%m-%Y %H:%M:%S') if field_value else ''
                    elif isinstance(field_value, fields.Date):
                        field_value = field_value.strftime('%d-%m-%Y') if field_value else ''
                    elif isinstance(field_value, (int, float, str)):
                        field_value = str(field_value) if field_value else ''
                    else:
                        field_value = ''

                    style = date_style if field.field_id.ttype == 'datetime' else default_style
                    worksheet.write(row_num, col_num, field_value or '', style)

        # Save the workbook to a BytesIO object
        fp = BytesIO()
        workbook.save(fp)
        fp.seek(0)

        # Encode and return the file
        export_id = self.create({
            'excel_file': base64.b64encode(fp.getvalue()),
            'file_name': 'Helpdesk_Tickets_Exported.xls'
        })
        fp.close()

        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/?model=helpdesk.ticket.excel.wizard.portal&id={export_id.id}&field=excel_file&filename_field=file_name&download=true',
            'target': 'new',
        }

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
