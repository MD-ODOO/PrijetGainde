# -*- coding: utf-8 -*-
######################################################################
#                                                                    #
# Part of EKIKA CORPORATION PRIVATE LIMITED (Website: ekika.co).     #
# See LICENSE file for full copyright and licensing details.         #
#                                                                    #
######################################################################

import os
import json
import pickle
import odoo
from odoo.http import request
from odoo import models, fields, api
from odoo.exceptions import ValidationError
from odoo.fields import Datetime


class ResUsers(models.Model):
    _inherit = 'res.users'

    session_limit_count = fields.Integer(string='Session Limit Count', default=1)
    session_expiry_hours = fields.Integer(string='Session Expiry In Hours', default=48)

    def write(self, vals):
        if 'session_limit_count' in vals and vals['session_limit_count'] < 1:
            raise ValidationError('Session Limit Count should not less than 1')
        if 'session_expiry_hours' in vals and vals['session_expiry_hours'] < 1:
            raise ValidationError('Session Expiry should not less than 1')
        return super().write(vals)

    @api.model_create_multi
    def create(self, vals_list):
        for val in vals_list:
            if 'session_limit_count' in val and val['session_limit_count'] < 1:
                raise ValidationError('Session Limit Count should not less than 1')
            if 'session_expiry_hours' in val and val['session_expiry_hours'] < 1:
                raise ValidationError('Session Expiry should not less than 1')
        return super().create(vals_list)

    @classmethod
    def authenticate(cls, db, credential, user_agent_env):
        auth_info = super().authenticate(db, credential, user_agent_env)
        cls.save_user_login_history(auth_info['uid'])
        if request.env['ir.config_parameter'].sudo().get_param('user_session_manage.session_limit_management'):
            session_limit_conf = request.env['ir.config_parameter'].sudo().get_param(
                'user_session_manage.session_limit_configuration')
            if session_limit_conf == 'one_session_all_user':
                cls.remove_all_other_session_of_user(auth_info['uid'])
            elif session_limit_conf == 'user_based':
                cls.remove_session_user_based(auth_info['uid'])
        return auth_info

    @classmethod
    def save_user_login_history(cls, uid):
        request.env['user.login.history'].sudo().create({
            'user_id': uid,
            'login_datetime': Datetime.now()
        })

    @classmethod
    def remove_all_other_session_of_user(cls, uid):
        cur_sess_paths = cls.get_current_user_session_path(uid)
        cls.remove_session_files(cur_sess_paths)

    @classmethod
    def remove_session_user_based(cls, uid):
        user = request.env['res.users'].sudo().search([('id', '=', uid)])
        session_rec = request.env['user.session.detail'].sudo().search([('user_id', '=', user.id)],
                                        order='first_activity')
        if user.session_limit_count <= len(session_rec):
            path = odoo.tools.config.session_dir
            if user.session_limit_count == 1:
                unlink_sessions = session_rec
            elif user.session_limit_count == len(session_rec):
                unlink_sessions = session_rec[:user.session_limit_count-1]
            else:
                unlink_sessions = session_rec[:-user.session_limit_count+1]
            for u in unlink_sessions:
                session_path = f'{path}/{u.session_identifier[:2]}/{u.session_identifier}'
                if os.path.exists(session_path):
                    os.remove(session_path)
            unlink_sessions.unlink()

    @classmethod
    def get_current_user_session_path(cls, uid):
        path = odoo.tools.config.session_dir
        session_files = cls.read_files_in_subdirectories(path)
        cur_sess_paths = []
        for s in session_files:
            with open(f'{path}/{s}', 'rb') as f:
                file_content = f.read()
                try:
                    session_data = json.loads(file_content)
                    if session_data['db'] == request.db and session_data['uid'] == uid:
                        cur_sess_paths.append(f'{path}/{s}')
                except Exception:
                    session_data = pickle.loads(file_content)
                    if session_data['db'] == request.db and session_data['uid'] == uid:
                        cur_sess_paths.append(f'{path}/{s}')
        return cur_sess_paths

    @classmethod
    def read_files_in_subdirectories(cls, path):
        """
        Reads all files inside the subdirectories of a specified directory.

        Parameters:
            path (str): The path to the directory.

        Returns:
            list: A list of file names (with their relative paths) in the subdirectories.
                Returns an empty list if there are no subdirectories or if the directory doesn't exist.
        """
        try:
            # Check if the path exists and is a directory
            if not os.path.exists(path):
                return []
            if not os.path.isdir(path):
                return []
            
            # Initialize an empty list to store file paths
            files_in_subdirs = []
            
            # Iterate through the subdirectories
            for entry in os.listdir(path):
                subdir_path = os.path.join(path, entry)
                if os.path.isdir(subdir_path):  # Check if it's a subdirectory
                    # Add files from the subdirectory
                    files_in_subdirs.extend(
                        [os.path.join(entry, file) for file in os.listdir(subdir_path)
                        if os.path.isfile(os.path.join(subdir_path, file))]
                    )
            
            return files_in_subdirs
        except Exception as e:
            return []

    @classmethod
    def remove_session_files(cls, session_files):
        for c in session_files:
            if os.path.exists(c):
                os.remove(c)
