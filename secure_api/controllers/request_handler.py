import werkzeug
from odoo import SUPERUSER_ID, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools.mimetypes import guess_mimetype
from odoo import fields
from odoo.release import version_info  # (18, ...)
if version_info[0] >= 19:
    from odoo.fields import Domain as expression
else:
    from odoo.osv import expression
from dateutil.relativedelta import relativedelta
from datetime import datetime, timedelta
import datetime
import random
import string
import copy
import json
import ast
import base64
import re
from .hashids import Hashids
import functools

import logging

_logger = logging.getLogger(__name__)

BULK_ID_IN_URL = "bulk"
DECODE_FIELDS_DEFAULT_KEY = "__self__"

def replacer(match):
    inside = match.group(1).strip()
    # If already has .id after ref(...), keep as is
    if inside.endswith(".id'") or inside.endswith('.id"'):
        return f"self.request.env.ref({inside})"
    return f"self.request.env.ref({inside}).id"


def decode_now(s_hash_manager, encoded_id):
    id_arr = s_hash_manager.decode(str(encoded_id))  # (14,) or may be empty tuple ()
    if id_arr:
        return id_arr[0]
    return encoded_id


class RequestHandler:
    def __init__(self, request, api_record, kargs):
        self.request = request
        self.api_record = api_record
        self.kargs = kargs
        self.security_user_id = False
        self.data = {}
        self.model_name = False
        self.http_url = self.request.httprequest.url
        self.field_names = []
        if not self.api_record:
            raise werkzeug.exceptions.NotFound()

        self._setup()
        pass

    def _get_first_model_name(self):
        return self.api_record.model_ids[0].model  # "res.partner"

    def _setup(self):
        """
        Initialize fields:
            - self.security_user_id
            - self.data
            - self.model_name
            - self.field_names
        """
        if self.api_record.auth == "user":  # private
            self.security_user_id = self.request.env.user.id
        else:  # public
            self.security_user_id = self.api_record.security_user_id.id if self.api_record.security_user_id else SUPERUSER_ID

        self.data = {}
        try:
            self.data = self.request.httprequest.args.to_dict()
        except:
            _logger.error("Cannot parse http request args (%s)" % str(self.request.httprequest.args))
            pass
        ## v14
        json_data = self.request.jsonrequest if hasattr(self.request, "jsonrequest") else {}
        json_data = json_data["__params"] if "__params" in json_data else json_data
        if isinstance(json_data, dict):
            self.data.update(json_data)
        else:  # [{}, {}]
            self.data = json_data

        # https://werkzeug.palletsprojects.com/en/stable/wrappers/#werkzeug.wrappers.Request.get_data
        if not self.data:
            request_data = {}  # might be a dict or list
            if hasattr(self.request.httprequest, "data") and self.request.httprequest.data:
                try:
                    request_data = json.loads(self.request.httprequest.data)
                except json.JSONDecodeError:
                    _logger.error("Cannot parse http request data (%s)" % str(self.request.httprequest.data))
            self.data = request_data

        self.model_name = self.kargs.get("model", False) if self.api_record.is_multi_model else self._get_first_model_name()

        if self.api_record.allowed_field_type == "all":  # get all field records from the model
            target_model = self.request.env["ir.model"].sudo().search([("model", "=", self.model_name)], limit=1)

            if target_model:
                self.field_records = target_model.field_id
            else:
                self.field_records = []
        else:  # specific fields
            self.field_records = self.api_record.field_ids.filtered(lambda x: x.model_id.model == self.model_name)

        self.field_names = self.field_records.mapped("name")

        if not self.field_names:
            self.field_names = ["id"]

        self.hash_manager = self.api_record.get_hash_manager()

        # Setup field alias mappings
        self._setup_alias_mappings()
        # | -------------------- |

        # setup "decode_fields"
        if self.api_record.is_secure_record_id:
            rel_fields = self.request.env["ir.model.fields"].sudo().search([
                ("model_id.model", "=", self.model_name),
                ("ttype", "in", ["many2one", "one2many", "many2many"])
            ])
            self.decode_fields = {DECODE_FIELDS_DEFAULT_KEY: rel_fields.mapped("name")}
            for rfield in rel_fields:                
                self.decode_fields[rfield.name] = self.request.env["ir.model.fields"].sudo().search([
                    ("model_id.model", "=", rfield.relation),
                    ("ttype", "in", ["many2one", "one2many", "many2many"])
                ]).mapped('name')     

        # apply on C/U/D and RPC, requires: self.hash_manager and self.decode_fields
        if (
            self.api_record.api_action in ("create", "update", "delete")
            or (self.api_record.api_action == "rest" and self.request.httprequest.method in ("POST", "PATCH", "DELETE"))
            or self.api_record.api_action == "rpc"
        ) and self.api_record.is_secure_record_id:
            decoded_data = self._decode_data_recursive(data=self.data, decode_fields=self.decode_fields)
            self.data = decoded_data
            pass

        self.target_id = self.kargs.get("id", False)
        self.target_ids = self._parse_ids()

        # --
        if version_info[0] >= 19:
            self.context = {
                **self.request.env.context,
                "api_id": self.api_record.id,
            }
        else:
            self.context = {
                **self.request.context,
                "api_id": self.api_record.id,
            }
        
        self.model_with_user = self.request.env[self.model_name].with_user(self.security_user_id).with_context(self.context)
        self.app_3rd_party = False      # value of this field is assigned later in self.check_security()

        # Convert aliases to real field names in request data (after data parsing, before CRUD operations)
        if self.api_record.alias_field_ids:
            self.data = self._convert_aliases_to_real_names(self.data)
        pass

    def _setup_alias_mappings(self):
        """
        Build alias mapping dictionaries from self.api_record.alias_field_ids
        Creates:
            - self.alias_to_real_map: {model_name: {alias: real_field_name}}
            - self.real_to_alias_map: {model_name: {real_field_name: alias}}
            - self.field_relation_cache: {model_name: {field_name: related_model}}
        """
        self.alias_to_real_map = {}
        self.real_to_alias_map = {}
        self.field_relation_cache = {}

        if not self.api_record.alias_field_ids:
            return

        # Collect all models that have aliases defined
        models_with_aliases = set()

        for alias_record in self.api_record.alias_field_ids:
            model_name = alias_record.model_id.model
            real_name = alias_record.field_id.name
            alias_name = alias_record.alias

            models_with_aliases.add(model_name)

            if model_name not in self.alias_to_real_map:
                self.alias_to_real_map[model_name] = {}
                self.real_to_alias_map[model_name] = {}

            self.alias_to_real_map[model_name][alias_name] = real_name
            self.real_to_alias_map[model_name][real_name] = alias_name

        # Build field relation cache for all models with aliases
        # This avoids repeated database queries in _get_related_model_for_field
        self._build_field_relation_cache(models_with_aliases)

    def _build_field_relation_cache(self, models_with_aliases):
        """
        Build a cache of relational fields for models that have aliases defined.
        This cache maps {model_name: {field_name: related_model}} for relational fields.
        """
        if not models_with_aliases:
            return

        # Get all relational fields for models with aliases in a single query
        model_objs = self.request.env["ir.model"].sudo().search([("model", "in", list(models_with_aliases))])
        if not model_objs:
            return

        relational_fields = self.request.env["ir.model.fields"].sudo().search([
            ("model_id", "in", model_objs.ids),
            ("ttype", "in", ["many2one", "one2many", "many2many"]),
            ("relation", "!=", False)
        ])

        for field_obj in relational_fields:
            model_name = field_obj.model_id.model
            if model_name not in self.field_relation_cache:
                self.field_relation_cache[model_name] = {}
            self.field_relation_cache[model_name][field_obj.name] = field_obj.relation

    def _convert_aliases_to_real_names(self, data, model_name=None):
        """
        Recursively traverse request data and replace alias field names with real field names.
        Handles:
            - Dictionary data (field: value pairs)
            - Domain filters [('field', 'op', value)]
            - Nested objects
            - O2M/M2M commands [(0, 0, {...}), (1, id, {...}), ...]
        """
        if model_name is None:
            model_name = self.model_name

        alias_map = self.alias_to_real_map.get(model_name, {})

        if isinstance(data, dict):
            result = {}
            for key, value in data.items():
                # Convert key from alias to real name if applicable
                real_key = alias_map.get(key, key)

                # Check if this is a relational field and get its related model
                related_model = self._get_related_model_for_field(model_name, real_key)

                if related_model and isinstance(value, (dict, list)):
                    # Recursively process nested data for related model
                    result[real_key] = self._convert_aliases_to_real_names(value, related_model)
                else:
                    result[real_key] = value
            return result

        elif isinstance(data, (tuple, list)):
            result = []
            for item in data:
                if isinstance(item, dict):
                    result.append(self._convert_aliases_to_real_names(item, model_name))
                elif isinstance(item, (tuple, list)):
                    # Check for domain condition or o2m/m2m command
                    if len(item) == 3:
                        if isinstance(item[0], int) and item[0] in range(7):
                            # O2M/M2M command: (0, 0, values), (1, id, values), etc.
                            cmd_code, cmd_id, cmd_vals = item
                            if cmd_code in (0, 1) and isinstance(cmd_vals, dict):
                                # Get related model from context if available
                                subres = [cmd_code, cmd_id, self._convert_aliases_to_real_names(cmd_vals, model_name)]
                            else:
                                subres = list(item)
                            subres = tuple(subres) if isinstance(item, tuple) else subres
                            result.append(subres)
                        elif isinstance(item[0], str):
                            # Domain condition: ('field', 'op', value)
                            field_name, op, value = item
                            # Convert field name from alias to real
                            real_field = alias_map.get(field_name, field_name)
                            # Handle dotted field names (e.g., 'partner_id.company_id')
                            if '.' in field_name:
                                parts = field_name.split('.')
                                converted_parts = []
                                current_model = model_name
                                for part in parts:
                                    part_alias_map = self.alias_to_real_map.get(current_model, {})
                                    real_part = part_alias_map.get(part, part)
                                    converted_parts.append(real_part)
                                    # Get related model for next iteration
                                    related_model = self._get_related_model_for_field(current_model, real_part)
                                    if related_model:
                                        current_model = related_model
                                real_field = '.'.join(converted_parts)
                            subres = [real_field, op, value]
                            subres = tuple(subres) if isinstance(item, tuple) else subres
                            result.append(subres)
                        else:
                            result.append(item)
                    else:
                        result.append(self._convert_aliases_to_real_names(item, model_name))
                else:
                    result.append(item)
            return tuple(result) if isinstance(data, tuple) else result

        return data

    def _convert_real_names_to_aliases(self, result, model_name=None, field_records=None):
        """
        Convert real field names back to aliases in API responses.
        Handles related model fields with their respective alias mappings.
        """
        if model_name is None:
            model_name = self.model_name

        alias_map = self.real_to_alias_map.get(model_name, {})

        if not alias_map and not self._has_related_model_aliases():
            return result

        if isinstance(result, dict):
            new_result = {}
            for key, value in result.items():
                # Get the alias for this field if it exists
                alias_key = alias_map.get(key, key)

                # Check if this is a relational field with data that needs alias conversion
                related_model = self._get_related_model_for_field(model_name, key)
                if related_model and isinstance(value, (dict, list)):
                    value = self._convert_related_value_to_aliases(value, related_model)

                new_result[alias_key] = value
            return new_result

        elif isinstance(result, list):
            return [self._convert_real_names_to_aliases(item, model_name, field_records) for item in result]

        return result

    def _convert_related_value_to_aliases(self, value, related_model):
        """
        Convert related model field values to use aliases.
        Handles various formats: dict, list of dicts, [id, {...}] format
        """
        related_alias_map = self.real_to_alias_map.get(related_model, {})

        if isinstance(value, dict):
            new_value = {}
            for k, v in value.items():
                alias_k = related_alias_map.get(k, k)
                new_value[alias_k] = v
            return new_value

        elif isinstance(value, list):
            if len(value) == 2 and isinstance(value[0], (int, str)) and isinstance(value[1], dict):
                # Format: [id, {...}] - many2one with expanded data
                return [value[0], self._convert_related_value_to_aliases(value[1], related_model)]
            elif len(value) > 0 and isinstance(value[0], dict):
                # List of dicts - o2m/m2m with expanded data
                return [self._convert_related_value_to_aliases(item, related_model) for item in value]

        return value

    def _get_related_model_for_field(self, model_name, field_name):
        """
        Get the related model name for a relational field.
        Uses cached field relation data built during _setup_alias_mappings().
        Returns None if the field is not relational or doesn't exist.
        """
        # Use cache first (populated during _setup_alias_mappings)
        if hasattr(self, 'field_relation_cache') and self.field_relation_cache:
            model_cache = self.field_relation_cache.get(model_name, {})
            if field_name in model_cache:
                return model_cache[field_name]

        # Field not in cache - no need to query DB since we only care about
        # models with aliases, and those are already cached
        return None

    def _has_related_model_aliases(self):
        """Check if there are any aliases defined for related models."""
        if not self.real_to_alias_map:
            return False
        # Check if any model other than the main model has aliases
        for model_name in self.real_to_alias_map:
            if model_name != self.model_name and self.real_to_alias_map[model_name]:
                return True
        return False

    def _check_api_state(self):
        return self.api_record.state == "published"

    def _check_http_method(self):
        http_method = self.request.httprequest.method

        # First check if the method is allowed for this API
        if not ((not self.api_record.method_ids) or (self.api_record.method_ids and http_method in self.api_record.method_ids.mapped("name"))):
            return False

        # Then check if there's at least one active endpoint with this HTTP method
        active_endpoints = self.api_record.endpoint_ids.filtered(lambda e: e.state == "active" and e.http_method_id.name == http_method)
        return len(active_endpoints) > 0

    def _check_applied_model(self):
        if not self.model_name:
            return False
        return self.model_name in self.api_record.model_ids.mapped("model")

    def _check_is_allow_multi(self):
        if self.api_record.is_allow_multi or self.api_record.api_action == "search":
            return True
        if self.api_record.api_action in ("create", "read", "update", "delete"):
            if isinstance(self.data, (tuple, list)):
                return False
            ids = self.data.get("ids", [])
            if len(ids) > 1:
                return False
        return True
        pass

    def _check_int(self, s):
        if not s:
            return False
        s = str(s)
        if s[0] in ("-", "+"):
            return s[1:].isdigit()
        return s.isdigit()

    def _decode_id(self, encoded_id, is_raise_exception=True, custom_exception=None):
        if not encoded_id:
            return False

        if encoded_id == BULK_ID_IN_URL:  # special case "bulk"
            return encoded_id

        # the "encoded_id" must be (string) in integer format (id) or an encoded id string (be able to decode)
        if self.api_record.is_secure_record_id:
            decoded_result = decode_now(self.hash_manager, encoded_id)
            if decoded_result == encoded_id:  # cannot decode smoothly
                if is_raise_exception:
                    if not custom_exception:
                        raise werkzeug.exceptions.NotFound()
                    else:
                        raise custom_exception
                else:
                    return encoded_id
            else:
                return decoded_result
        elif self._check_int(encoded_id):
            return encoded_id
        else:
            if not custom_exception:
                raise werkzeug.exceptions.NotFound()
            else:
                raise custom_exception
    
    def _decode_data_recursive(self, data, decode_fields={}, decode_func=None):
        """
        Decode obfuscated IDs to Integer for payload or domain.
        Support decode_fields: {
            DECODE_FIELDS_DEFAULT_KEY: ["id", "ids", "company_id", "parent_id", ...]
            "child_ids": ["company_id", ...]
            "parent_id": ["id", "company_id", ...]
        }
        """
        decoder = functools.partial(self._decode_id, is_raise_exception=True, custom_exception=ValidationError(_("Invalid ID"))) if (decode_func is None) else decode_func
        default_fields_to_decode = ["id", "ids"] if self.api_record.is_allow_multi else ["id"]
        decode_fields.setdefault(DECODE_FIELDS_DEFAULT_KEY, default_fields_to_decode)
        decode_fields = {k:list(set(v+default_fields_to_decode)) for k, v in decode_fields.items()}
        ## Build "result" from "data" ##
        if isinstance(data, dict):  # {}
            result = {}
            for key, value in data.items():
                if key in decode_fields:    # m2o, o2m, m2m
                    result[key] = self._decode_data_recursive(data=value, decode_fields={DECODE_FIELDS_DEFAULT_KEY: decode_fields[key]}, decode_func=decoder)
                elif key in decode_fields[DECODE_FIELDS_DEFAULT_KEY]:  # m2o
                    result[key] = self._decode_data_recursive(data=value, decode_fields={}, decode_func=decoder)
                else:
                    result[key] = value
                pass
            pass
        elif isinstance(data, (tuple, list)):   # multiple cases
            result = []
            if all(isinstance(item, str) for item in data): # ["0VOgV","pda0b"]
                result = [decoder(item) for item in data]
            else:
                for item in data:
                    if isinstance(item, dict):
                        result.append(self._decode_data_recursive(data=item, decode_fields=decode_fields, decode_func=decoder))
                    elif isinstance(item, (tuple, list)):   # domain condition or o2m/m2m command
                        if len(item)==3 and (isinstance(item[0], int) and item[0] in range(7)) and (isinstance(item[1], str) or item[1]==0) and (isinstance(item[2], (tuple, list, dict)) or item[2]==0): # o2m/m2m command
                            # (0, 0, values), (...)]: adds a new record created from the provided value dict.
                            # (1, id, values): updates an existing record of id id with the values in values. Can not be used in create().
                            # (2, id, 0): removes the record of id id from the set, then deletes it (from the database). Can not be used in create().
                            # (3, id, 0): removes the record of id id from the set, but does not delete it. Can not be used in create().
                            # (4, id, 0): adds an existing record of id id to the set.
                            # (5, 0, 0): removes all records from the set, equivalent to using the command 3 on every record explicitly. Can not be used in create().
                            # (6, 0, ids): replaces all existing records in the set by the ids list, equivalent to using the command 5 followed by a command 4 for each id in ids.
                            subres = []
                            cmd_code, cmd_id, cmd_vals = item
                            if cmd_code==0 and cmd_id==0:
                                subres = [cmd_code, cmd_id, self._decode_data_recursive(cmd_vals, decode_fields=decode_fields, decode_func=decoder)]
                            elif cmd_code==1:
                                subres = [cmd_code, decoder(cmd_id), self._decode_data_recursive(cmd_vals, decode_fields=decode_fields, decode_func=decoder)]
                            elif cmd_code in (2, 3, 4) and cmd_vals==0:
                                subres = [cmd_code, decoder(cmd_id), cmd_vals]
                            elif cmd_code==6 and cmd_id==0:
                                d_ids = [decoder(x) for x in cmd_vals]
                                d_ids = tuple(d_ids) if isinstance(cmd_vals, tuple) else d_ids   # keep "d_ids" type as "cmd_vals"
                                subres = [cmd_code, cmd_id, d_ids]
                            else: # (5, 0, 0)
                                subres = [cmd_code, cmd_id, cmd_vals]
                            subres = tuple(subres) if isinstance(item, tuple) else subres   # keep "subres" type as "item"
                            result.append(subres)
                        elif len(item)==3:   # domain condition: ("id", "in", ["0VOgV","pda0b"]) ("partner_id", "=", "0VOgV")
                            subres = []
                            ifield, iops, ivalue = item
                            if ifield in decode_fields:
                                subres = [ifield, iops, self._decode_data_recursive(data=ivalue, decode_fields={DECODE_FIELDS_DEFAULT_KEY: decode_fields[ifield]}, decode_func=decoder)]
                            elif ifield in decode_fields[DECODE_FIELDS_DEFAULT_KEY]:
                                subres = [ifield, iops, self._decode_data_recursive(data=ivalue, decode_fields={}, decode_func=decoder)]
                            elif ifield.count(".")>0:  # "partner_id.name", "partner_id.company_id"
                                fnames = ifield.split(".")
                                if fnames[0] in decode_fields.keys() and fnames[1] in decode_fields[fnames[0]]:     #"partner_id.company_id"
                                    subres = [ifield, iops, self._decode_data_recursive(data=ivalue, decode_fields={}, decode_func=decoder)]
                                else:   # "partner_id.name"
                                    subres = [ifield, iops, ivalue]
                                pass
                            else:
                                subres = [ifield, iops, ivalue]
                            subres = tuple(subres) if isinstance(item, tuple) else subres   # keep "subres" type as "item"
                            result.append(subres)
                        else:
                            result.append(item)
                        pass
                    else:
                        result.append(item)
                pass
            result = tuple(result) if isinstance(data, tuple) else result   # keep "result" type as "data"
        elif isinstance(data, str):
            result = decoder(data)
        else:
            # primitive type or not handle yet
            result = data
            pass
        ## --------------------------- ##
        return result

    def _parse_ids(self):
        target_id = self._decode_id(self.kargs.get("id", False), is_raise_exception=True)  # "1", "bulk", ...
        if self._check_int(target_id):
            return [
                int(target_id),
            ]

        if self.api_record.api_action in ("rest", "read") and target_id == BULK_ID_IN_URL:  # /.../bulk
            args_ids = self.data.get("ids", "[]")  # "[1, 2, 3]" or "1,2,3" or "['0VOgV','pda0b']" or '["0VOgV","pda0b"]' or "0VOgV,pda0b"

            # If already a list, use it directly
            if isinstance(args_ids, list):
                res = args_ids
            # If it's a string, parse it
            elif isinstance(args_ids, str):
                args_ids = args_ids.strip()

                if not args_ids or args_ids == "[]":
                    res = []
                # Try JSON format first: [1,2,3] or ["0VOgV","pda0b"]
                elif args_ids.startswith("[") and args_ids.endswith("]"):
                    try:
                        res = json.loads(args_ids)
                    except json.JSONDecodeError:
                        # Try Python literal format: ['0VOgV','pda0b']
                        try:
                            res = ast.literal_eval(args_ids)
                        except (ValueError, SyntaxError):
                            # Fall back to simple comma splitting if JSON parsing fails
                            res = [x.strip() for x in args_ids[1:-1].split(",") if x.strip()]
                # Handle comma-separated format: "1,2,3" or "0VOgV,pda0b"
                else:
                    res = [x.strip() for x in args_ids.split(",") if x.strip()]
            else:
                res = []
            return [int(self._decode_id(x, is_raise_exception=True)) for x in res]

        if isinstance(self.data, dict) and self.data:
            ## "self.data" is decoded data recursively => no need to decode again
            return self.data.get("ids", [])

        if isinstance(self.data, (tuple, list)):
            ids = []
            for item_data in self.data:
                if isinstance(item_data, dict) and "id" in item_data:
                    ## "self.data" is decoded data recursively => no need to decode again
                    ids.append(item_data["id"])
                elif isinstance(item_data, int):
                    ids.append(item_data)
            ids = [int(x) for x in ids]
            return ids

        if target_id:  # cannot decode the string id => just keep as it is
            return [
                target_id,
            ]

        # any case else!?
        #################
        return []

    def result_single_dict_if_possible(self, result):
        if isinstance(result, list) and len(result) == 1:
            return result[0]
        return result

    def result_wrap(self, result=[], field_records=False, model_name=False, is_enable_related_model_field=True):
        """
        result: [{"id": ..., "...": ...}]
        """
        field_records = self.field_records if field_records is False else field_records
        model_name = self.model_name if model_name is False else model_name  # hr.applicant

        if self.api_record.binary_field_return == "url":
            binary_fields = field_records.filtered(lambda x: x.ttype == "binary")
            for res in result:
                record_id = res.get("id", False)  # original id (integer)
                if record_id:
                    binary_dict = {}
                    for bf in binary_fields:
                        bf_name = bf.name

                        if res.get(bf_name, False) is False or res.get(bf_name, False) is None:
                            binary_dict[bf_name] = ""  # empty string instead of `false`
                            continue
                        elif isinstance(res[bf_name], dict):
                            binary_dict[bf_name] = res[bf_name]
                            continue

                        # _logger.warning(f"Value binary going to decode field ({bf_name}) = {res.get(bf_name, b"")} ")

                        bf_mimetype = guess_mimetype(base64.b64decode(res.get(bf_name, b"")), default="text/plain")
                        if self.api_record.auth == "user":
                            media_prefix = "/web/image" if bf_mimetype.startswith("image") else "/web/content"
                            binary_dict[bf_name] = "%s/%s/%d/%s" % (media_prefix, model_name, record_id, bf_name)
                        else:
                            media_prefix = "/api/image" if bf_mimetype.startswith("image") else "/api/content"
                            binary_dict[bf_name] = "%s/%d/%s/%s/%s" % (
                                media_prefix,
                                self.api_record.id,
                                model_name,
                                (self.hash_manager.encode(record_id) if self.api_record.is_secure_record_id else str(record_id)),
                                bf_name,
                            )

                    res.update(binary_dict)

        # convert False value to "" (empty string) based on field type
        ftype_dict = {fr.name: fr.ttype for fr in field_records}
        is_result_of_search = self.request.httprequest.method == "GET" and not self.target_id
        for res in result:
            for k in res.keys():
                v = res[k]
                if v is False or v is None:
                    if ftype_dict.get(k, False) in ("char", "text", "selection", "date", "datetime", "binary"):
                        res[k] = ""
                    elif ftype_dict.get(k, False) in ("many2one",):
                        if version_info[0] >= 17 and is_result_of_search:   # From Odoo 17, "web_search_read" returns {..., "country_id": 2} instead of {..., "country_id": [2, "Country Name"]}
                            # Assign to null to make data type consistent
                            res[k] = None
                        else:                       # "country_id": [2, "Country Name"]
                            res[k] = []
                    elif ftype_dict.get(k, False) in ("one2many", "many2many"):
                        res[k] = []

        # Implement "related_model_field_ids", query related model records
        if is_enable_related_model_field and self.api_record.related_model_field_ids:
            rmodel_names = [r_model_field.model_id.model for r_model_field in self.api_record.related_model_field_ids]  # ['res.partner', 'res.country', ...]
            fname2model_dict = {fr.name: fr.relation for fr in field_records if fr.relation in rmodel_names}
            # calculate "model2ids_dict"
            model2ids_dict = {rmname: [] for rmname in rmodel_names}
            for res in result:
                for fname, related_model_name in fname2model_dict.items():
                    if isinstance(res[fname], (tuple, list)) and len(res[fname]) > 0:
                        if ftype_dict.get(fname, False) in ("many2one",):  # value format: [<id>, "name"]
                            model2ids_dict[related_model_name].append(res[fname][0])
                        elif ftype_dict.get(fname, False) in (
                            "one2many",
                            "many2many",
                        ):  # value format: [<id>, <id>, ...]
                            model2ids_dict[related_model_name] += res[fname]
                    elif isinstance(res[fname], int) and ftype_dict.get(fname, False) in ("many2one",):
                        model2ids_dict[related_model_name].append(res[fname])
                pass

            # calculate "model2records_dict"
            model2records_dict = {rmname: {} for rmname in rmodel_names}
            for r_model_field in self.api_record.related_model_field_ids:
                related_model_name = r_model_field.model_id.model
                related_ids = model2ids_dict[related_model_name]
                if related_ids:
                    related_model_with_user = self.request.env[related_model_name].with_user(self.security_user_id).with_context(self.context)
                    related_field_names = [mf_field.name for mf_field in r_model_field.field_ids]
                    related_results = self.result_wrap(
                        result=related_model_with_user.browse(related_ids).read(related_field_names),
                        field_records=r_model_field.field_ids,
                        model_name=related_model_name,
                        is_enable_related_model_field=False,
                    )
                    for rid, rval in zip(related_ids, related_results):
                        model2records_dict[related_model_name][
                            rid
                        ] = rval  # Value of "id" key in "rval" may be already encoded by "hash_manager", so we use "rid" (int) in "related_ids"

            # modify result
            for res in result:
                for fname, related_model_name in fname2model_dict.items():
                    v = res[fname]
                    if isinstance(res[fname], (tuple, list)) and len(v) > 0:
                        if ftype_dict.get(fname, False) in ("many2one",):  # value format: [<id>, "name"]
                            res[fname] = [
                                v[0],
                                copy.deepcopy(model2records_dict[related_model_name][v[0]]),
                            ]  # [<id>, {...}]
                        elif ftype_dict.get(fname, False) in (
                            "one2many",
                            "many2many",
                        ):  # value format: [<id>, <id>, ...]
                            res[fname] = [copy.deepcopy(model2records_dict[related_model_name][rid]) for rid in v]
                    elif isinstance(v, int) and ftype_dict.get(fname, False) in ("many2one",):
                        res[fname] = copy.deepcopy(model2records_dict[related_model_name][v])  # {...}
                    pass
                pass
            pass

        # Hash record ids: id of current record, id of relation fields: many2one, one2many, many2many
        if self.api_record.is_secure_record_id:
            for res in result:
                for k, v in res.items():
                    if k == "id":
                        res[k] = self.hash_manager.encode(v)
                    elif ftype_dict.get(k, False) in ("many2one",):
                        if isinstance(v, int):  # 'state_id': 13
                            res[k] = self.hash_manager.encode(v)
                        elif isinstance(v, (tuple, list)) and len(v) > 0:
                            res[k] = [self.hash_manager.encode(v[0]), v[1]]
                    elif ftype_dict.get(k, False) in ("one2many", "many2many") and len(v) > 0 and isinstance(v[0], int):
                        res[k] = [self.hash_manager.encode(rid) for rid in v]

        # Convert real field names to aliases in response (if aliases are configured)
        if self.api_record.alias_field_ids:
            result = [self._convert_real_names_to_aliases(res, model_name, field_records) for res in result]

        return result

    def apply_field_default(self, data, default_dict):
        for key, (data_type, text_value) in default_dict.items():
            try:
                if key in data:
                    continue
                # binary, boolean, char, date, datetime, float, html, integer, json, many2many, many2one, many2one_reference,
                # monetary, one2many, properties, properties_definition, reference, selection, text
                if text_value == "False":
                    data[key] = False
                    continue
                if data_type == "boolean":
                    if text_value.lower() not in ("true", "false"):
                        continue
                    value = True if text_value.lower() == "true" else False
                elif data_type in ("float", "monetary"):
                    value = float(text_value)
                elif data_type == "integer":
                    value = int(text_value)
                elif data_type == "json":
                    value = json.loads(text_value)
                elif data_type in ("many2many", "one2many", "many2one", "many2one_reference"):  # "[(6, 0, [1, 2])]" or "ref('base.user_admin')"
                    if text_value.count("ref(") > 0:
                        # Replace all ref(...) with self.request.env.ref(...).id
                        text_value = re.sub(r"ref\((.*?)\)", replacer, text_value)
                        value = eval(text_value)
                    else:
                        value = ast.literal_eval(text_value)
                elif data_type in ("date", "datetime"):  # fields.Date.today()+relativedelta(days=10) or datetime.today()+timedelta(days=10)
                    value = eval(text_value)
                elif data_type in ("binary", "char", "html", "properties", "properties_definition", "reference", "selection", "text"):  # just assign
                    # test again: date, datetime
                    value = text_value
                else:
                    value = text_value
                data[key] = value
            except Exception as e:
                pass
        pass

    def check_security(self):
        if not self._check_api_state():
            raise werkzeug.exceptions.NotFound()

        if not self._check_http_method():
            raise werkzeug.exceptions.NotFound()

        if not self._check_applied_model():
            raise werkzeug.exceptions.NotFound()

        if not self._check_is_allow_multi():
            raise werkzeug.exceptions.NotFound()

        if self.api_record.auth == "user" and self.api_record.app_ids:  # => controller with 'public' auth => the user session is logged-in user or "base.public_user"
            if self.request.uid == self.request.env.ref("base.public_user").id:  # base.public_user
                access_token = self.request.httprequest.headers.get("Authorization")
                if access_token and access_token.startswith("Bearer "):
                    access_token = access_token[7:]

                    # Try OAuth2 opaque token first
                    app = self.request.env["secure.api.app.token"].sudo().get_3rd_party_app(access_token=access_token)

                    # If OAuth2 token not found, try JWT token
                    if not app:
                        app = self.request.env["secure.api.app"].sudo().validate_jwt_token(access_token)

                    self.app_3rd_party = app
                    if app:
                        app_scope_actions = app.get_scope_actions()
                        app_ctx = {     # add "app_id" to context
                            **self.context,
                            "app_id": app.id,
                        }
                        if self.api_record.api_action in ("search", "create", "read", "update", "delete", "rpc") and self.api_record.api_action in app_scope_actions:  # OK
                            self.security_user_id = app.security_user_id.id
                            # re-assign model with user
                            self.context = app_ctx
                            self.model_with_user = self.request.env[self.model_name].with_user(self.security_user_id).with_context(self.context)
                        elif self.api_record.api_action == "rest":
                            api_action = ""
                            # extract api_action
                            http_method = self.request.httprequest.method
                            if http_method == "GET":  # search or read
                                api_action = "read" if self.target_id else "search"
                            elif http_method == "POST":  # create
                                api_action = "create"
                            elif http_method == "PATCH":  # update
                                api_action = "update"
                            elif http_method == "DELETE":  # delete
                                api_action = "delete"
                            if api_action in app_scope_actions:  # OK
                                self.security_user_id = app.security_user_id.id
                                self.context = app_ctx
                                # re-assign model with user
                                self.model_with_user = self.request.env[self.model_name].with_user(self.security_user_id).with_context(self.context)
                            else:  # out of scope
                                raise werkzeug.exceptions.Unauthorized()
                        else:
                            raise werkzeug.exceptions.Unauthorized()
                    else:  # expired or not existed token (both OAuth2 and JWT)
                        raise werkzeug.exceptions.Unauthorized()
                else: # Jan 03, 2026: try to access API configured with 3rd-party app (OAuth2 or JWT) neither logged in user nor access token
                    raise werkzeug.exceptions.Unauthorized()
            else:  # normal user
                # do nothing
                pass
        return True

    def search(self):
        # update "self.field_records" and "self.field_names" dynamically
        if not self.field_records:  # False or []
            if self.api_record.search_field_ids:
                self.field_records = self.api_record.search_field_ids
            else:
                # do nothing
                pass
        else:  # has values
            if self.api_record.search_field_ids:
                self.field_records = self.field_records.filtered(lambda x: x.id in self.api_record.search_field_ids.ids)
            else:
                # do nothing
                pass
            pass

        self.field_names = self.field_records.mapped("name") or ["id"]
        # --------------------------------------------------------------

        domain, fields, offset, limit, order = "[]", None, 0, None, None
        domain = ast.literal_eval(self.data.get("domain", domain))
        offset = int(self.data.get("offset", offset))
        limit = int(self.data.get("limit", self.api_record.listing_limit))  # get from module settings
        order = self.data.get("order", order)
        # fields = None if self.api_record.allowed_field_type == "all" and not self.api_record.search_field_ids else self.field_names
        fields = self.field_names

        # decode "domain"
        domain = self._decode_data_recursive(data=domain, decode_fields=self.decode_fields) if self.api_record.is_secure_record_id else domain

        _logger.info(f"domain after decode: {domain}, offset={offset}, limit={limit}, order={order}")

        if self.api_record.domain:
            api_domain = ast.literal_eval(self.api_record.domain or "[]")
            domain = expression.AND([domain, api_domain])

        fields = {fname: {} for fname in self.field_names}        # Dict[str, Dict]
        result = self.model_with_user.web_search_read(
            domain=domain, specification=fields, offset=offset, limit=limit, order=order
        )  # {'length': 36, 'records': [{'id': 14, 'active': True,  ...}]}
        # _logger.warning("list result: %s", str(result))
        if result.get("records", []):
            result["records"] = self.result_wrap(result["records"])
        return result

    def read(self):  # read one and list many records!!
        if not self.target_ids:
            raise ValidationError("Missing ids")
        fields = None if self.api_record.allowed_field_type == "all" else self.field_names
        result = self.model_with_user.browse(self.target_ids).read(fields)
        return self.result_single_dict_if_possible(self.result_wrap(result))

    def create(self):
        if self.api_record.default_field_ids:  # modify self.data
            field_defaults = self.api_record.default_field_ids.filtered(lambda x: x.model_id.model == self.model_name)
            field_defaults = {fd.field_id.name: (fd.field_type, fd.value) for fd in field_defaults}  # {"name": ("char", "Minh"), ...}
            if isinstance(self.data, list):
                new_data = []
                for s_data in self.data:
                    self.apply_field_default(data=s_data, default_dict=field_defaults)
                    new_data.append(s_data)
                self.data = new_data
                pass
            elif isinstance(self.data, dict):
                self.apply_field_default(data=self.data, default_dict=field_defaults)
                pass
            pass
        new_records = self.model_with_user.create(self.data)
        fields = None if self.api_record.allowed_field_type == "all" else self.field_names
        return self.result_single_dict_if_possible(self.result_wrap(new_records.read(fields)))

    def update(self):
        if not self.target_ids:
            raise ValidationError("Missing ids")

        fields = None if self.api_record.allowed_field_type == "all" else self.field_names

        if self.target_id and len(self.target_ids) == 1:
            record = self.model_with_user.browse(self.target_ids)
            record.write(self.data)
            return self.result_single_dict_if_possible(self.result_wrap(record.read(fields)))
        else:  # bulk
            is_same_update = True  # ["ids": [...], "data": {...}]
            if len(self.target_ids) > 1 and isinstance(self.data, (tuple, list)):  # [{}, {}]
                is_same_update = False

            if is_same_update:  # single or multi
                records = self.model_with_user.browse(self.target_ids)
                overwrite_data = self.data.copy()
                overwrite_data.pop("ids")
                if overwrite_data:
                    records.write(overwrite_data)
                    return self.result_wrap(records.read(fields))
                else:
                    return []
            else:
                result = []
                records = self.model_with_user.browse(self.target_ids)
                for idx, data_item in enumerate(self.data):
                    overwrite_data = data_item.copy()
                    overwrite_data.pop("id")
                    if not overwrite_data:
                        continue

                    record = records[idx]
                    record.write(overwrite_data)
                    result.append(record.read(fields)[0])
                return self.result_wrap(result)

    def delete(self):
        if not self.target_ids:
            raise ValidationError("Missing ids")

        records = self.model_with_user.browse(self.target_ids)
        removed_ids = records.ids
        records.unlink()
        if self.api_record.is_secure_record_id:
            removed_ids = [self.hash_manager.encode(rid) for rid in removed_ids]
        return removed_ids

    def rpc(self):
        http_method = self.request.httprequest.method
        if http_method == "GET":  # handle no target id
            if not self.target_ids:
                m = getattr(self.model_with_user, self.api_record.rpc_method)
                result = m(**self.data)
                return result
            records = self.model_with_user.browse(self.target_ids)
            m = getattr(records, self.api_record.rpc_method)
            result = m(**self.data)
            return result
        elif http_method in ("POST", "PUT", "DELETE", "PATCH"):
            if not self.target_ids:  # handle no target id
                m = getattr(self.model_with_user, self.api_record.rpc_method)
                result = m(**self.data)
                return result
            elif self.target_id and len(self.target_ids) == 1:
                records = self.model_with_user.browse(self.target_ids)
                m = getattr(records, self.api_record.rpc_method)
                result = m(**self.data)
                return result
            else:  # bulk
                is_same_update = True  # ["ids": [...], "key": value]
                if len(self.target_ids) > 1 and isinstance(self.data, (tuple, list)):  # [{}, {}]
                    is_same_update = False

                if is_same_update:  # single or multi
                    records = self.model_with_user.browse(self.target_ids)
                    overwrite_data = self.data.copy()
                    overwrite_data.pop("ids", False)
                    m = getattr(records, self.api_record.rpc_method)
                    result = m(**overwrite_data)
                    return result
                else:
                    result = []
                    records = self.model_with_user.browse(self.target_ids)
                    for idx, data_item in enumerate(self.data):
                        overwrite_data = data_item.copy()

                        record = records[idx]

                        m = getattr(record, self.api_record.rpc_method)
                        subresult = m(**overwrite_data)
                        result.append(subresult)
                    return result
            pass

        # http method has not handled!
        raise werkzeug.exceptions.NotFound()

    def rest(self):
        http_method = self.request.httprequest.method
        result = False
        if http_method == "GET":  # search or read
            result = self.read() if self.target_id else self.search()
        elif http_method == "POST":  # create
            result = self.create()
        elif http_method == "PATCH":  # update
            result = self.update()
        elif http_method == "DELETE":  # delete
            result = self.delete()
        return result

    def __call__(self):
        action = getattr(self, self.api_record.api_action, False)  # rest, create, read, update, delete, rpc
        if action is False:
            raise ValidationError("Secure API Action (%s) has not been implemented!" % self.api_record.api_action)

        if self.api_record.mode == "test" or (self.app_3rd_party and self.app_3rd_party.mode == "test"):
            act_result = action()
            self.model_with_user.env.cr.rollback()  # rollback the previous transaction
        else:
            act_result = action()

        return act_result

