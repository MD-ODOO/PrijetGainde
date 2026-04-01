# -*- coding: utf-8 -*-
##############################################################################
#
#    Cybrosys Technologies Pvt. Ltd.
#
#    Copyright (C) 2023-TODAY Cybrosys Technologies(<https://www.cybrosys.com>).
#    Author: Mruthul Raj @cybrosys(odoo@cybrosys.com)
#
#    You can modify it under the terms of the GNU AFFERO
#    GENERAL PUBLIC LICENSE (AGPL v3), Version 3.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU AFFERO GENERAL PUBLIC LICENSE (AGPL v3) for more details.
#
#    You should have received a copy of the GNU AFFERO GENERAL PUBLIC LICENSE
#    (AGPL v3) along with this program.
#    If not, see <http://www.gnu.org/licenses/>.
#
###############################################################################
import datetime 
from odoo import http
from odoo.http import request
from odoo import models, fields, api, _
from operator import itemgetter
import itertools
import operator
from datetime import date, timedelta

class ProjectFilter(http.Controller):
    """The ProjectFilter class provides the filter option to the js.
    When applying the filter returns the corresponding data."""

    @http.route('/all_helpdesk_etp_filter', auth='public', type='json')
    def all_helpdesk_etp_filter(self):
        team_list = []
        user_list = []
        partner_list = []
        stages_list = []
        
        team_ids = request.env['helpdesk.team'].search([])
        user_ids = request.env['res.users'].search([])
        partner_ids = request.env['res.partner'].search([])
        stages_ids = request.env['helpdesk.stage'].search([])
       
        for team_id in team_ids:
            dic = {'name': team_id.name,
                   'id': team_id.id}
            team_list.append(dic)
        for user_id in user_ids:
            dic = {'name': user_id.name,
                   'id': user_id.id}
            user_list.append(dic)
        for partner_id in partner_ids:
            dic = {'name': partner_id.name,
                   'id': partner_id.id}
            partner_list.append(dic)
        for stage_id in stages_ids:
            dic = {'name': stage_id.name,
                   'id': stage_id.id}
            stages_list.append(dic)    
     
        return [team_list,user_list, partner_list,stages_list]    
    
    
    @http.route('/get/helpdesk-etp/tiles/data', auth='public', type='json')
    def get_helpdesk_etp_tiles_data(self, **kwargs):

        today = date.today()
        closing_domain = []
        
        if not kwargs.get('duration'):
            closing_domain = [('create_date', '>=', today),('create_date', '<=', today)]
        if kwargs:
            if kwargs['team_id']:
                if kwargs['team_id'] != 'all':
                    team_id = int(kwargs['team_id'])
                    closing_domain += [('team_id.id','=',team_id)]
            if kwargs['user_id']:
                if kwargs['user_id'] != 'all':
                    user_id = int(kwargs['user_id'])
                    closing_domain += [('user_id','=',user_id)]
            if kwargs['partner_id']:
                if kwargs['partner_id'] != 'all':
                    partner_id = int(kwargs['partner_id'])
                    closing_domain += [('partner_id','=',partner_id)]
            if kwargs['stage_id']:
                if kwargs['stage_id'] != 'all':
                    stage_id = int(kwargs['stage_id'])
                    closing_domain += [('stage_id.id','=',stage_id)]
            if kwargs['duration']:
                duration = kwargs['duration']
                if duration != "all":
                    duration = int(duration)
                    filter_date = today - timedelta(days=duration)
                    closing_domain += [('create_date', '>=', filter_date), ('create_date', '<=', today)]

        helpdesk_ids = request.env['helpdesk.ticket'].search(closing_domain)
        is_configured = False

        all_ticket_data = []
        in_progress_ticket_data = []
        solve_ticket_data = []
        cancel_ticket_data = []

        for helpdesk_id in helpdesk_ids:
            if helpdesk_id.stage_id.id == request.env.user.company_id.draft_stage_id.id:
                in_progress_ticket_data.append(helpdesk_id.id)
            if helpdesk_id.stage_id.id == request.env.user.company_id.done_stage_id.id:
                solve_ticket_data.append(helpdesk_id.id)
            if helpdesk_id.stage_id.id == request.env.user.company_id.cancel_stage_id.id:
                cancel_ticket_data.append(helpdesk_id.id)
            if helpdesk_id.stage_id.id not in solve_ticket_data or cancel_ticket_data:
                all_ticket_data.append(helpdesk_id.id)       
            
        if request.env.user.company_id.draft_stage_id.id and request.env.user.company_id.done_stage_id.id and request.env.user.company_id.close_stage_id.id and request.env.user.company_id.cancel_stage_id.id:
            is_configured = True
        
        user_name = request.env.user.name
        user_img = request.env.user.image_1920

        return {
            'is_configured': is_configured,
            'all_ticket_data': all_ticket_data,
            'in_progress_ticket_data': in_progress_ticket_data,
            'solve_ticket_data': solve_ticket_data,
            'cancel_ticket_data': cancel_ticket_data,
            'user_img': user_img,
            'user_name': user_name
        }

    # chart group by stages------------------------

    @http.route('/stages/chart/data', auth='public', type='json')
    def get_stages_chart_data(self, **kw):
        
        all_color_list = ['#00daa3', '#f06c67', '#0c9fa1', '#cf9ab5', '#bce459', '#3f8eae', '#ed843f', '#00c4aa',
                          '#966ca2', '#e2d65e', '#d56e80', '#c99a5c', '#61e180', '#bf784b', '#fec863', '#7269ad']     
    
        data=kw['data']
        today = date.today()
        closing_domain = []
        
        if not data.get('duration'):
            closing_domain = [('create_date', '>=', today),('create_date', '<=', today)]

        if data:
            if data['team_id']:
                if data['team_id'] != 'all':
                    team_id = int(data['team_id'])
                    closing_domain += [('team_id.id','=',team_id)]
            
            if data['user_id']:
                if data['user_id'] != 'all':
                    user_id = int(data['user_id'])
                    closing_domain += [('user_id','=',user_id)]

            if data['partner_id']:
                if data['partner_id'] != 'all':
                    partner_id = int(data['partner_id'])
                    closing_domain += [('partner_id','=',partner_id)]
        
            if data['stage_id']:
                if data['stage_id'] != 'all':
                    stage_id = int(data['stage_id'])
                    closing_domain += [('stage_id.id','=',stage_id)]

            if data['duration']:
                duration = data['duration']
                if duration != "all":
                    duration = int(duration)
                    filter_date = today - timedelta(days=duration)
                    closing_domain += [('create_date', '>=', filter_date), ('create_date', '<=', today)]

        
        helpdesk_stage_label=[]
        helpdesk_stage_values=[]

        helpdesk_stage_data = request.env['helpdesk.ticket'].search_read(closing_domain, fields=['stage_id', 'name'])

        n_lines = sorted(helpdesk_stage_data, key=itemgetter('stage_id'))
        groups = itertools.groupby(n_lines, key=operator.itemgetter('stage_id'))
        lines = [{'stage_id': k, 'values': [x for x in v]} for k, v in groups]
               
        stage_counting_ids=[]                                                                                                                       
        for x in lines:
            stage_counting_id = []                                                                                                                  
            for id in x['values']:
                stage_counting_id.append(id['id']) 
            stage_counting_ids.append(stage_counting_id) 
        
        for line in lines:
            helpdesk_stage_label.append(line.get('stage_id')[1])
            helpdesk_stage_values.append(len(line.get('values')))
        
        stages_chart_data = {
            'labels': helpdesk_stage_label,
            'datasets': [{
                'label': "Team",
                'backgroundColor': all_color_list[:len(helpdesk_stage_label)],
                'data': helpdesk_stage_values,
                'detail' : stage_counting_ids
            }]
        }
        return {
            'stages_chart_data': stages_chart_data,
        }

    # ------------Group By Team---------------

    @http.route('/team/chart/data', auth='public', type='json')
    def get_team_chart_data(self, **kw):
        
        all_color_list = ['#00daa3', '#f06c67', '#0c9fa1', '#cf9ab5', '#bce459', '#3f8eae', '#ed843f', '#00c4aa',
                          '#966ca2', '#e2d65e', '#d56e80', '#c99a5c', '#61e180', '#bf784b', '#fec863', '#7269ad']     
    
        data=kw['data']
        today = date.today()
        closing_domain = []
        
        if not data.get('duration'):
            closing_domain = [('create_date', '>=', today),('create_date', '<=', today)]

        if data:
            if data['team_id']:
                if data['team_id'] != 'all':
                    team_id = int(data['team_id'])
                    closing_domain += [('team_id.id','=',team_id)]
            
            if data['user_id']:
                if data['user_id'] != 'all':
                    user_id = int(data['user_id'])
                    closing_domain += [('user_id','=',user_id)]

            if data['partner_id']:
                if data['partner_id'] != 'all':
                    partner_id = int(data['partner_id'])
                    closing_domain += [('partner_id','=',partner_id)]
        
            if data['stage_id']:
                if data['stage_id'] != 'all':
                    stage_id = int(data['stage_id'])
                    closing_domain += [('stage_id.id','=',stage_id)]

            if data['duration']:
                duration = data['duration']
                if duration != "all":
                    duration = int(duration)
                    filter_date = today - timedelta(days=duration)
                    closing_domain += [('create_date', '>=', filter_date), ('create_date', '<=', today)]    

        helpdesk_team_label=[]
        helpdesk_team_values=[]

        helpdesk_team_data = request.env['helpdesk.ticket'].search_read(closing_domain, fields=['team_id', 'name'])

        n_lines = sorted(helpdesk_team_data, key=itemgetter('team_id'))
        groups = itertools.groupby(n_lines, key=operator.itemgetter('team_id'))
        lines = [{'team_id': k, 'values': [x for x in v]} for k, v in groups]
               
        team_counting_ids=[]                                                                                                                       
        for x in lines:
            team_counting_id = []                                                                                                                  
            for id in x['values']:
                team_counting_id.append(id['id']) 
            team_counting_ids.append(team_counting_id) 
        
        for line in lines:
            helpdesk_team_label.append(line.get('team_id')[1])
            helpdesk_team_values.append(len(line.get('values')))
        
        helpdesk_team_chart_data = {
            'labels': helpdesk_team_label,
            'datasets': [{
                'label': "Team",
                'backgroundColor': all_color_list[:len(helpdesk_team_label)],
                'data': helpdesk_team_values,
                'detail' : team_counting_ids
            }]
        }
        return{
            'helpdesk_team_chart_data': helpdesk_team_chart_data
        }

    # ------------Group By Priority---------------

    @http.route('/priority/chart/data', auth='public', type='json')
    def get_priority_chart_data(self, **kw):
        
        all_color_list = ['#00daa3', '#f06c67', '#0c9fa1', '#cf9ab5', '#bce459', '#3f8eae', '#ed843f', '#00c4aa',
                          '#966ca2', '#e2d65e', '#d56e80', '#c99a5c', '#61e180', '#bf784b', '#fec863', '#7269ad']     
    
        data=kw['data']
        today = date.today()
        closing_domain = []
        
        if not data.get('duration'):
            closing_domain = [('create_date', '>=', today),('create_date', '<=', today)]

        if data:
            if data['team_id']:
                if data['team_id'] != 'all':
                    team_id = int(data['team_id'])
                    closing_domain += [('team_id.id','=',team_id)]
            
            if data['user_id']:
                if data['user_id'] != 'all':
                    user_id = int(data['user_id'])
                    closing_domain += [('user_id','=',user_id)]

            if data['partner_id']:
                if data['partner_id'] != 'all':
                    partner_id = int(data['partner_id'])
                    closing_domain += [('partner_id','=',partner_id)]
        
            if data['stage_id']:
                if data['stage_id'] != 'all':
                    stage_id = int(data['stage_id'])
                    closing_domain += [('stage_id.id','=',stage_id)]

            if data['duration']:
                duration = data['duration']
                if duration != "all":
                    duration = int(duration)
                    filter_date = today - timedelta(days=duration)
                    closing_domain += [('create_date', '>=', filter_date), ('create_date', '<=', today)]    
   
        low = []
        medium = []
        high = []
        very_high = []
        priority_data = request.env['helpdesk.ticket'].search(closing_domain)
        for p_data in priority_data:
            if p_data.priority == '0':
                low.append(p_data['id'])
            if p_data.priority == '1':
                medium.append(p_data['id'])
            if p_data.priority == '2':
                high.append(p_data['id'])
            if p_data.priority == '3':
                very_high.append(p_data['id'])
        
        priority_label = ['Low','Medium','High','Very High']
        priority_value = [len(low),len(medium),len(high),len(very_high)]
        priority_counting_ids = [low,medium,high,very_high]

        helpdesk_priority_chart_data = {
            'labels': priority_label,
            'datasets': [{
                'label': "Priority",
                'backgroundColor': all_color_list[:len(priority_label)],
                'data': priority_value,
                'detail' : priority_counting_ids
            }]
        }
        return{
            'helpdesk_priority_chart_data': helpdesk_priority_chart_data
        }

    # ------------Group By Source---------------

    @http.route('/source/chart/data', auth='public', type='json')
    def get_source_chart_data(self, **kw):
        
        all_color_list = ['#00daa3', '#f06c67', '#0c9fa1', '#cf9ab5', '#bce459', '#3f8eae', '#ed843f', '#00c4aa',
                          '#966ca2', '#e2d65e', '#d56e80', '#c99a5c', '#61e180', '#bf784b', '#fec863', '#7269ad']     
    
        data=kw['data']
        today = date.today()
      
        closing_domain = []
        source_domain = []
        if not data.get('duration'):
            source_domain = [('create_date', '>=', today),('create_date', '<=', today)]
            source_domain = [('date_deadline', '=', today)]

        if data:
            if data['team_id']:
                if data['team_id'] != 'all':
                    team_id = int(data['team_id'])
                    closing_domain += [('team_id.id','=',team_id)]
                    source_domain += [('team_id.id','=',team_id)]
            if data['user_id']:
                if data['user_id'] != 'all':
                    user_id = int(data['user_id'])
                    closing_domain += [('user_id','=',user_id)]
                    source_domain += [('user_id','=',user_id)]

            if data['partner_id']:
                if data['partner_id'] != 'all':
                    partner_id = int(data['partner_id'])
                    source_domain += [('partner_id','=',partner_id)]
        
            if data['stage_id']:
                if data['stage_id'] != 'all':
                    stage_id = int(data['stage_id'])
                    closing_domain += [('stage_id.id','=',stage_id)]
                    source_domain += [('stage_id.id','=',stage_id)]
            if data['duration']:
                duration = data['duration']
                if duration != "all":
                    duration = int(duration)
                    filter_date = today - timedelta(days=duration)
                    source_domain += [('create_date', '>=', filter_date), ('create_date', '<=', today)]       

        helpdesk_source_label=[]
        helpdesk_source_values=[]
        helpdesk_source_data = request.env['helpdesk.ticket'].search(source_domain)
        helpdek_data = []
        for h_data in helpdesk_source_data:

            helpdek_data.append({
                                'source_id':h_data.source_id.name or 'None',
                                'id':h_data.id or False,
                                'name':h_data.name or 'None',
            })

        n_lines = sorted(helpdek_data, key=itemgetter('source_id'))
        groups = itertools.groupby(n_lines, key=operator.itemgetter('source_id'))
        lines = [{'source_id': k, 'values': [x for x in v]} for k, v in groups]
               
        source_counting_ids=[]                                                                                                                       
        for x in lines:
            source_counting_id = []                                                                                                                  
            for id in x['values']:
                source_counting_id.append(id.get('id'))
            source_counting_ids.append(source_counting_id)
            
        for line in lines:
            helpdesk_source_label.append(line.get('source_id')[0:10])
            helpdesk_source_values.append(len(line.get('values')))
        
        helpdesk_source_chart_data = {
            'labels': helpdesk_source_label,
            'datasets': [{
                'label': "Total",
                'backgroundColor': all_color_list[:len(helpdesk_source_label)],
                'data': helpdesk_source_values,
                'detail' : source_counting_ids
            }]
        }
        return{
            'helpdesk_source_chart_data': helpdesk_source_chart_data
        }

    @http.route('/helpdesk/table/data', auth='public', type='json')
    def get_expense_table_data(self, **kw):
        
        all_color_list = ['#00daa3', '#f06c67', '#0c9fa1', '#cf9ab5', '#bce459', '#3f8eae', '#ed843f', '#00c4aa',
                          '#966ca2', '#e2d65e', '#d56e80', '#c99a5c', '#61e180', '#bf784b', '#fec863', '#7269ad']     
    
        data=kw['data']
        today = date.today()

        domain = []
        closing_domain = []
        source_domain = []
        
        if not data.get('duration'):
            domain = [('create_date', '>=', today),('create_date', '<=', today)]
            closing_domain = [('date_deadline', '>=', today)]
            source_domain = [('create_date', '>=', today),('create_date', '<=', today)]

        if data:
            if data['team_id']:
                if data['team_id'] != 'all':
                    team_id = int(data['team_id'])
                    domain += [('team_id.id','=',team_id)]
                    closing_domain += [('team_id.id','=',team_id)]
                    source_domain += [('team_id.id','=',team_id)]
            
            if data['user_id']:
                if data['user_id'] != 'all':
                    user_id = int(data['user_id'])
                    domain += [('user_id','=',user_id)]
                    closing_domain += [('user_id','=',user_id)]
                    source_domain += [('user_id','=',user_id)]

            if data['partner_id']:
                if data['partner_id'] != 'all':
                    partner_id = int(data['partner_id'])
                    domain += [('partner_id','=',partner_id)]
                    closing_domain += [('partner_id','=',partner_id)]
                    source_domain += [('partner_id','=',partner_id)]
        
            if data['stage_id']:
                if data['stage_id'] != 'all':
                    stage_id = int(data['stage_id'])
                    domain += [('stage_id.id','=',stage_id)]
                    closing_domain += [('stage_id.id','=',stage_id)]
                    source_domain += [('stage_id.id','=',stage_id)]

            if data['duration']:
                duration = data['duration']
                if duration != "all":
                    duration = int(duration)
                    filter_date = today - timedelta(days=duration)
                    domain += [('create_date', '>=', filter_date), ('create_date', '<=', today)]
                    closing_domain += [('date_deadline', '>=', filter_date), ('date_deadline', '>=', today)]
                    source_domain += []
           
        all_team_list = request.env['helpdesk.ticket'].search_read(domain,
                                                            fields=['name', 'partner_id', 'team_id','create_date'],
                                                            order="id desc")
        for ticket in all_team_list:
            ticket['create_date'] = ticket['create_date'].date()


        closing_ticket_list = request.env['helpdesk.ticket'].search_read(
            [('date_deadline', '!=', False)] + closing_domain,
            fields=['stage_id', 'date_deadline', 'name', 'partner_id', 'partner_phone'],
            order="id desc"
        )

        cancel_stage_id = request.env.user.company_id.cancel_stage_id.id

        filtered_ticket_list = []
        for close in closing_ticket_list:
            if close['stage_id'][0] != cancel_stage_id:
                ticket_copy = close.copy()  # remove stages
                ticket_copy.pop('stage_id', None)
                filtered_ticket_list.append(ticket_copy)
                    
        return{
            'all_team_list': all_team_list,
            'closing_ticket_list': filtered_ticket_list,
            
        }
        

    @http.route('/helpdesk-etp/filter-apply', auth='public', type='json')
    def helpdesk_etp_filter_apply(self, **kw):
        data = kw['data']
        team_id = data['team']
        user_id = data['user']
        partner_id = data['partner']
        stage_id = data['stage']
        duration = data['duration']

        result = self.get_helpdesk_etp_tiles_data(team_id=team_id,user_id=user_id, partner_id=partner_id,stage_id=stage_id,duration=duration)
        return result
    
    
