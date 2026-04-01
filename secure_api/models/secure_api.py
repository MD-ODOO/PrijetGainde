# -*- coding: utf-8 -*-
import os
import random
import string
import copy
import odoo
import json
import re
from odoo import api, fields, models, http, _
from odoo.exceptions import UserError, ValidationError
from odoo.http import request
from odoo.addons.secure_api.controllers.secure_controller import api_execute
from odoo.addons.secure_api.controllers.hashids import Hashids
import werkzeug
import functools
from odoo.release import version_info  # (18, ...)

import logging

_logger = logging.getLogger(__name__)


def random_string(size=6, digit=True, lower=True, upper=True):
    # ref: https://stackoverflow.com/a/2257449
    assert (digit or lower or upper) is True
    chars = []
    chars += string.digits if digit else []
    chars += string.ascii_lowercase if lower else []
    chars += string.ascii_uppercase if upper else []
    return "".join(random.choice(chars) for _ in range(size))


class SecureAPI(models.Model):
    _name = "secure.api"

    _description = "Secure API"

    name = fields.Char("Name", required=True)
    route = fields.Char("Route", required=True)
    active = fields.Boolean("Active", default=True)
    auth = fields.Selection(
        [
            ("none", "Public"),
            ("user", "User"),
            # ('public', 'Public'),
        ],
        string="Authentication",
        default="none",
        required=True,
        help="User: The user must be authenticated and the current request will perform using the rights of the user.\nPublic: The user may or may not be authenticated. If she isn't, the current request will perform using the configured security user.",
    )
    method_ids = fields.Many2many(
        "secure.api.method",
        "secure_api_secure_api_method_rel",
        string="HTTP Methods",
        help="Best practice to choose method is following REST API design.\n- Create: POST\n- Read: GET\n- Update: PATCH\n- Delete: DELETE\n- RPC: POST",
    )
    cors = fields.Char("CORS", default="*", required=True)
    security_user_id = fields.Many2one(
        "res.users",
        string="Run as User",
        required=False,
        default=lambda self: self.env.user,
        help="The current request will perform using the rights of this user",
    )

    api_action = fields.Selection(
        [
            ("rest", "REST API"),
            ("search", "Search records"),
            ("create", "Create a record"),
            ("read", "Read a record"),
            ("update", "Update a record"),
            ("delete", "Delete a record"),
            ("rpc", "Call a Method in Class (RPC)"),
        ],
        default="rest",
        string="Type",
        required=True,
    )
    model_ids = fields.Many2many("ir.model", "secure_api_ir_model_rel", string="Applied on Models", required=True)
    model_id_alias = fields.Many2one("ir.model", string="Applied on One Model", required=False, ondelete="cascade")

    allowed_field_type = fields.Selection(
        [
            ("all", "All Fields"),
            ("specific", "Specific Fields"),
        ],
        default="all",
        string="Allowed Fields",
        required=True,
    )

    field_ids = fields.Many2many("ir.model.fields", "secure_api_ir_model_fields_rel", string="Exposed Fields")
    domain_search_fields = fields.Many2many("ir.model.fields", compute="_compute_domain_search_fields")
    search_field_ids = fields.Many2many(
        "ir.model.fields",
        "secure_api_search_field_ir_model_fields_rel",
        string="Fields on Search",
        help="Specify which fields can be used for searching/filtering in list endpoints. If left empty, all exposed fields will be available for search operations. This allows you to control which fields API users can search by.",
    )

    related_model_domain_ids = fields.Many2many("ir.model", store=True, compute="_get_related_model_domain_ids")  # invisible field
    related_model_field_ids = fields.One2many("secure.api.rfield", "secure_api_id", string="Fields on Related Models", copy=True)
    default_field_ids = fields.One2many("secure.api.default", "secure_api_id", string="Default Field Values", copy=True)
    alias_field_ids = fields.One2many("secure.api.alias", "secure_api_id", string="Field Aliases", copy=True)

    rpc_method = fields.Char("RPC Method", required=False)

    binary_field_return = fields.Selection([("url", "URL"), ("base64", "Base64")], string="Binary Field Return", default="url", required=True)

    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("published", "Active"),
            ("deactivated", "Inactive"),
        ],
        "State",
        default="draft",
        copy=False,
    )

    is_allow_multi = fields.Boolean(
        "Support Bulk Operation",
        default=False,
        help="Allow the action affects on multiple records with one API request (create, read, update, delete, rpc)",
    )
    is_multi_model = fields.Boolean("Is Multi Model", compute="_compute_is_multi_model")

    listing_limit = fields.Integer("Default Limit", default=10, help="Default number of results per page")

    # live test
    live_test_method = fields.Char("HTTP Method", default=False, help="HTTP Method (GET, POST, PATCH, DELETE)")
    live_test_id = fields.Char(":id", default=False, help="Record ID or ID with params (e.g., 5 or 5?filter=active)")
    live_test_ids = fields.Char("ids", default=False, help="Multiple IDs (e.g., 1,2,3)")
    live_test_model = fields.Char(":model", default=False, help="Model name (e.g., res.partner)")
    live_test_data = fields.Char("data", default=False, help='{"field": "value", "another_field": 123}')
    live_test_domain = fields.Char("domain", default=False, help='[("id", ">", 0)]')
    live_test_offset = fields.Char("offset", default=False, help="Starting position (e.g., 0)")
    live_test_limit = fields.Char("limit", default=False, help="Number of records (e.g., 10)")
    live_test_order = fields.Char("order", default=False, help="name asc, id desc")

    live_test_curl_command = fields.Char("Curl Command", default=False)
    live_test_response = fields.Text("Response")

    test_ids = fields.One2many("secure.api.test", "secure_api_id", string="Test Cases", copy=False)
    endpoint_ids = fields.One2many("secure.api.endpoint", "secure_api_id", string="Endpoints", copy=False)

    is_secure_record_id = fields.Boolean(
        "Id Obfuscation",
        default=False,
        help='Secure the record integer IDs from API users. The encoded record ID will look like a random short string (eg. AbdxXdJ5, gpkngme9, 3edpNmlZ, ...) which is not easy to guess. The encoder/decoder is powered by the open-source Python package "hashids"',
    )
    hashids_salt = fields.Char(
        "Hashids Salt",
        help="Salt used for generating obfuscated IDs. If not set, the default value from settings will be used.",
    )
    hashids_min_length = fields.Integer(
        "Hashids Min Length",
        help="Minimum length for obfuscated IDs. If not set, the default value from settings will be used.",
        default=5,
    )
    secure_record_id_example = fields.Char("Id Example", compute="_compute_secure_record_id_example")
    domain = fields.Char("Domain Filter")

    # Apr 17, 2024
    category_id = fields.Many2one("secure.api.category", string="Category", required=False, ondelete="set null")

    # Jun 04, 2024
    note = fields.Text("Note", required=False)

    # Sep 22, 2024
    sequence = fields.Integer(help="Gives the sequence order when displaying a list of APIs.")
    tag_ids = fields.Many2many("secure.api.tag", "secure_api_api_tag", string="Tags", help="Optional tags you may want to assign for apis")

    # Dec 09, 2024
    is_stats = fields.Boolean("Usage Statistics", default=True)
    secure_api_stats_id = fields.Many2one("secure.api.stats", string="API Statistics")

    stats_total_hit = fields.Integer(
        string="Total Requests",
        related="secure_api_stats_id.total_hit",
        store=True,
        readonly=False,
        depends=["secure_api_stats_id.total_hit"],
        aggregator="sum",
    )
    # Feb 10, 2025
    app_ids = fields.Many2many("secure.api.app", "secure_api_app_secure_api_rel", string="Client Apps", copy=True)

    # Feb 14, 2025
    mode = fields.Selection(
        [
            ("test", "Test Mode"),
            ("prod", "Production Mode"),
        ],
        default="prod",
        string="Mode",
        required=True,
        help="Enable Test Mode to use the API in a sandbox environment. No real data or actions will be affected. Perfect for testing and development.",
    )

    _sql_constraints = [("route_uniq", "unique (route)", "The route of the API must be unique per API !")]

    @api.model_create_multi
    def create(self, vals_list):
        res_ids = super(SecureAPI, self).create(vals_list)
        if not isinstance(vals_list, (tuple, list)):
            vals_list = [
                vals_list,
            ]
        for new_record, vals in zip(res_ids, vals_list):
            if new_record.model_ids and len(new_record.model_ids) == 1:
                new_record.update(
                    {
                        "model_id_alias": new_record.model_ids[0].id,
                    }
                )
            if "state" in vals:
                if vals["state"] == "published":
                    new_record.btn_publish_api()
                elif vals["state"] == "deactivated":
                    new_record.btn_deactivate_api()
        return res_ids

    def write(self, vals):
        res = super(SecureAPI, self).write(vals)

        if res:
            if "model_ids" in vals:  # change on model_ids
                for rec in self:
                    if rec.model_ids and len(rec.model_ids) == 1:
                        rec.write(
                            {
                                "model_id_alias": rec.model_ids[0].id,
                            }
                        )
                        pass
                    pass

            if "state" in vals and vals["state"] == "published" and not self.env.context.get("btn_publish_api", False):
                for rec in self:
                    rec.btn_publish_api()
            elif "state" in vals and vals["state"] == "deactivated" and not self.env.context.get("btn_deactivate_api", False):
                for rec in self:
                    rec.btn_deactivate_api()
        return res

    def unlink(self):
        for record in self:
            if record.state == "published":
                raise UserError(_("You cannot remove the working (state = active) API: %s (%d)." % (record.name, record.id)))
                pass
        return super(SecureAPI, self).unlink()

    @api.returns("self", lambda value: value.id)
    def copy(self, default=None):
        default = dict(default or {})
        if "route" not in default:
            default["route"] = "%s/copy" % self.route
        if "name" not in default:
            default["name"] = _("%s (Copy)") % self.name
        return super(SecureAPI, self).copy(default=default)

    @api.depends("model_ids.name")
    def _compute_is_multi_model(self):
        for record in self:
            if record.model_ids and len(record.model_ids) > 1:
                record.is_multi_model = True
            else:
                record.is_multi_model = False
        pass

    def get_hash_manager(self, default_salt=None, default_min_length=None):
        self.ensure_one()

        # Use record-specific values if set, otherwise use defaults
        salt = self.hashids_salt
        min_length = self.hashids_min_length

        if not salt or not min_length:
            if default_salt is None or default_min_length is None:  # avoid multiple calls to default_get
                default_salt = self.env["ir.config_parameter"].sudo().get_param("secure_api.hashids_salt") if default_salt is None else default_salt
                default_min_length = int(self.env["ir.config_parameter"].sudo().get_param("secure_api.hashids_min_length", 5)) if default_min_length is None else default_min_length

            salt = salt or default_salt
            min_length = min_length or default_min_length

        hash_manager = Hashids(salt=salt, min_length=min_length)
        return hash_manager

    @api.depends("is_secure_record_id", "hashids_salt", "hashids_min_length")
    def _compute_secure_record_id_example(self):
        default_salt = self.env["ir.config_parameter"].sudo().get_param("secure_api.hashids_salt")
        default_min_length = int(self.env["ir.config_parameter"].sudo().get_param("secure_api.hashids_min_length", 5))

        for record in self:
            # Skip if model_id_alias is not set
            if not record.model_id_alias or not record.model_id_alias.model:
                record.secure_record_id_example = ""
                continue

            hash_manager = record.get_hash_manager(default_salt=default_salt, default_min_length=default_min_length)
            random_int = random.randint(1, 100)
            hashed_random_int = hash_manager.encode(random_int)

            if record.is_secure_record_id:
                record.secure_record_id_example = hashed_random_int
            else:
                record.secure_record_id_example = random_int

    @api.onchange("model_id_alias")
    def onchange_model_id_alias(self):
        for record in self:
            if record.model_id_alias is not False:
                record.model_ids = [(6, 0, record.model_id_alias.ids)]
            pass
        pass

    @api.onchange("auth")
    def onchange_security_user_id(self):
        for record in self:
            if record.auth == "user":
                record.security_user_id = False

    @api.onchange("allowed_field_type")
    def onchange_allowed_field_type(self):
        for record in self:
            if record.allowed_field_type == "all":
                record.field_ids = False

    @api.onchange("route")
    def onchange_route(self):
        # standardize the name to format: /<a>/<b>/<c> (without "/" at the end)
        for record in self:
            if record.route:
                final_route = "/" + record.route.strip("/")  # /a/b
                record.route = final_route.strip()

    @api.onchange("api_action")
    def onchange_method_ids(self):
        for record in self:
            if record.api_action == "rpc":
                record.method_ids = False
            else:
                mids = []
                action2method = {
                    "rest": ["get", "post", "patch", "delete"],
                    # "rest": ["get", "post", "post", "delete"],
                    "create": ["post"],
                    "search": ["get"],
                    "read": ["get"],
                    "update": ["patch"],
                    # "update": ["post"],
                    "delete": ["delete"],
                }

                method_names = action2method[record.api_action]
                mids += [self.env.ref("secure_api.secure_api_method_%s" % method_name).id for method_name in method_names]
                record.method_ids = [(6, 0, mids)]

    # related model fields
    @api.depends("field_ids", "allowed_field_type", "model_ids")
    def _get_related_model_domain_ids(self):
        for record in self:
            ids = []
            if record.field_ids:
                model_names = [field_row.relation for field_row in record.field_ids if field_row.relation]
                records = self.env["ir.model"].search([("model", "in", model_names)])
                ids = records.ids if records else ids
            elif record.allowed_field_type == "all" and record.model_ids:
                model_names = []
                for model in record.model_ids:
                    model_names += [field_row.relation for field_row in model.field_id if field_row.relation]
                if model_names:
                    records = self.env["ir.model"].search([("model", "in", model_names)])
                    ids = records.ids if records else ids
                pass
            record.related_model_domain_ids = [(6, 0, ids)]
        pass

    @api.depends("allowed_field_type", "model_ids", "field_ids")
    def _compute_domain_search_fields(self):
        for record in self:
            if record.allowed_field_type == "all":
                # Get all fields from all selected models
                fields = self.env["ir.model.fields"].search([("model_id", "in", record.model_ids.ids)])
                record.domain_search_fields = fields
            else:
                # Use only the specific fields selected
                record.domain_search_fields = record.field_ids

    def btn_live_test(self):
        self.ensure_one()
        data = {
            k: getattr(self, k)
            for k in [
                "api_action",
                "live_test_id",
                "live_test_ids",
                "live_test_model",
                "live_test_data",
                "live_test_domain",
                "live_test_offset",
                "live_test_limit",
                "live_test_order",
                "live_test_method",
            ]
        }
        test_name = self.route
        test_name = test_name.replace(":model", self.live_test_model) if self.live_test_model else test_name
        test_name = test_name.replace(":id", self.live_test_id) if self.live_test_id else test_name
        data.update(
            {
                "name": test_name,
                "secure_api_id": self.id,
            }
        )

        test_record = self.env["secure.api.test"].create(data)
        params = {
            "test_id": test_record.id,
        }
        record_attrs = [
            "id",
            "api_action",
            "route",
            "live_test_id",
            "live_test_ids",
            "live_test_model",
            "live_test_data",
            "live_test_domain",
            "live_test_offset",
            "live_test_limit",
            "live_test_order",
            "live_test_method",
            "is_multi_model",
        ]
        params.update({attr_name: getattr(self, attr_name) for attr_name in record_attrs})

        METHOD_SUGGESTION = {
            "search": "GET",
            "create": "POST",
            "read": "GET",
            "update": "PATCH",
            "delete": "DELETE",
            "rpc": "POST",
        }
        params["live_test_method"] = METHOD_SUGGESTION.get(self.api_action, "GET") if not params["live_test_method"] else params["live_test_method"]

        result = {
            "type": "ir.actions.client",
            "tag": "btn_live_test",
            "params": params,
        }
        # _logger.info("btn_live_test => result: %s" % str(result))
        return result

    def btn_back_to_draft(self):
        self.ensure_one()
        self.write({"state": "draft"})
        return True

    def btn_publish_api(self, routing_map=None):
        self.ensure_one()
        self.with_context(btn_publish_api=True).write({"state": "published"})

        if not self.secure_api_stats_id:
            self.env["secure.api.stats"].create(
                {
                    "name": _("Stats of %s") % self.name,
                    "secure_api_id": self.id,
                }
            )

        # generate endpoints
        self._generate_endpoints()
        
        # Register routes in routing map
        self.update_routing_map(routing_map=routing_map)

        return True

    def _generate_endpoints(self):
        self.ensure_one()
        ACTION2ENDPOINT_ONE = {
            "rest": [
                ("post", "", '{"name": "Peter"}', "create"),
                ("get", "", 'domain=[("id",">",0)]&offset=0&limit=15&order=id', "search"),
                ("get", ":id", False, "read"),
                ("patch", ":id", '{"name": "Peter"}', "update"),
                # ('post', ':id', '{"name": "Peter"}', 'update'),
                ("delete", ":id", False, "delete"),
            ],
            "create": [("post", "", '{"name": "Peter"}', "create")],
            "search": [("get", "", 'domain=[("id",">",0)]&offset=0&limit=15&order=id', "search")],
            "read": [("get", ":id", False, "read")],
            "update": [("patch", ":id", '{"name": "Peter"}', "update")],
            # "update": [('post', ':id', '{"name": "Peter"}', 'update')],   # request_handler.rest() has not handled yet
            "delete": [("delete", ":id", False, "delete")],
            "rpc": [],
        }
        ACTION2ENDPOINT_BULK = {
            "rest": [
                ("post", "", '[{"name": "Peter"}, {"name": "Mitchell"}]', "create"),
                ("get", "bulk", "ids=1,2,3", "read"),
                (
                    "patch",
                    "",
                    '[{"id": 100, "name": "Peter", "phone": "(870)-931-0505"}, {"id": 101, "name": "Mitchell"}]',
                    "update",
                ),
                ("patch", "", '{"ids": [100, 101], "name": "Mark", "phone": "(441)-695-2334"}', "update"),
                # ('post', '', '[{"id": 100, "name": "Peter", "phone": "(870)-931-0505"}, {"id": 101, "name": "Mitchell"}]', 'update'), ('post', '', '{"ids": [100, 101], "name": "Mark", "phone": "(441)-695-2334"}', 'update'),
                ("delete", "", "[100, 101]", "delete"),
                ("delete", "", '{"ids": [100, 101]}', "delete"),
            ],
            "create": [("post", "", '[{"name": "Peter"}, {"name": "Mitchell"}]', "create")],
            "search": [],
            "read": [("get", "bulk", "ids=1,2,3", "read")],
            "update": [
                (
                    "patch",
                    "",
                    '[{"id": 100, "name": "Peter", "phone": "(870)-931-0505"}, {"id": 101, "name": "Mitchell"}]',
                    "update",
                ),
                ("patch", "", '{"ids": [100, 101], "name": "Mark", "phone": "(441)-695-2334"}', "update"),
            ],
            # "update": [('post', '', '[{"id": 100, "name": "Peter", "phone": "(870)-931-0505"}, {"id": 101, "name": "Mitchell"}]', 'update'), ('post', '', '{"ids": [100, 101], "name": "Mark", "phone": "(441)-695-2334"}', 'update')],
            "delete": [("delete", "", "[100, 101]", "delete"), ("delete", "", '{"ids": [100, 101]}', "delete")],
            "rpc": [],
        }

        endpoint_data = []
        endpoint_data += [
            list(x)
            + [
                False,
            ]
            for x in ACTION2ENDPOINT_ONE[self.api_action]
        ]

        if self.is_allow_multi:
            endpoint_data += [
                list(x)
                + [
                    True,
                ]
                for x in ACTION2ENDPOINT_BULK[self.api_action]
            ]

        if self.api_action == "rpc":
            method_names = self.method_ids.mapped("name")
            for methd_name in method_names:
                methd_name = methd_name.lower()
                if methd_name == "get":
                    endpoint_data += [
                        (methd_name, "", "arg1=val1&arg2=val2", "rpc", False),
                        (methd_name, ":id", "arg1=val1&arg2=val2", "rpc", False),
                    ]
                    # Jun 04, 2024
                    endpoint_data += (
                        [
                            (methd_name, "bulk", "ids=1,2,3&arg1=val1&arg2=val2", "rpc", True),
                        ]
                        if self.is_allow_multi
                        else []
                    )
                elif methd_name == "head":
                    endpoint_data += [
                        (methd_name, "", "", "rpc", False),
                    ]
                else:
                    endpoint_data += [
                        (methd_name, "", '{"arg1": val1, "arg2": val2}', "rpc", False),
                        (methd_name, ":id", '{"arg1": val1, "arg2": val2}', "rpc", False),
                    ]
                    # Jun 04, 2024
                    endpoint_data += (
                        [
                            (methd_name, "", '[{"id": 1, "arg1": val1, "arg2": val2}, {...}, ...]', "rpc", True),
                            (methd_name, "", '{"ids": [1, 2, 3], "arg1": val1, "arg2": val2}', "rpc", True),
                        ]
                        if self.is_allow_multi
                        else []
                    )
                pass
            pass

        # _logger.warning("endpoint_data: %s", str( endpoint_data))

        endpoint_route = self.route
        if self.is_multi_model:
            endpoint_route += "/:model"

        self.endpoint_ids.unlink()
        for method, postfix, sample_data, api_action, is_bulk in endpoint_data:
            self.env["secure.api.endpoint"].create(
                {
                    "http_method_id": self.env.ref("secure_api.secure_api_method_%s" % method).id,
                    "route": endpoint_route + "/" + postfix if postfix else endpoint_route,
                    "data": sample_data if sample_data else False,
                    "is_bulk_operation": is_bulk,
                    "secure_api_id": self.id,
                    "api_action": api_action,
                }
            )
        pass

    def _get_endpoint(self, method_ref, routing, method_args=[]):
        ## v14, v15
        if hasattr(http, "EndPoint"):
            endpoint = http.EndPoint(functools.partial(method_ref, *method_args), routing)
        else:
            ## v16, v17, v18, v19
            method_info = [method_ref] + method_args
            endpoint = functools.partial(*method_info)
            functools.update_wrapper(endpoint, method_ref)
            endpoint.routing = routing
        return endpoint

    def update_routing_map(self, routing_map=None):
        for record in self:
            # generate routes from "record.endpoint_ids"
            # Note: we expose all endpoints, no need to select "active" endpoints because we check it in "api_execute". Endpoint state is toogled dynamically.
            endpoint_routes = list(set(record.endpoint_ids.mapped("route")))  # [...]
            endpoint_routes = [endr.replace(":id", "<id>").replace(":model", "<model>") for endr in endpoint_routes]
            endpoint_routes = [endr for endr in endpoint_routes if not endr.endswith("/bulk")]
            if not endpoint_routes:  # empty endpoints
                endpoint_routes = [
                    record.route,
                ]
            routes = endpoint_routes

            route2endpoint = {}
            for eroute in routes:
                original_eroute = eroute.replace("<model>", ":model").replace("<id>", ":id")
                route2endpoint[eroute] = record.endpoint_ids.filtered(lambda x: x.route == original_eroute)

            routing = dict(
                type="json",  # always json
                auth="public" if (record.app_ids and record.auth == "user") else record.auth,
                methods=[
                    self.env.ref("secure_api.secure_api_method_get").name,
                    self.env.ref("secure_api.secure_api_method_post").name,
                    self.env.ref("secure_api.secure_api_method_put").name,
                    self.env.ref("secure_api.secure_api_method_delete").name,
                    self.env.ref("secure_api.secure_api_method_patch").name,
                ],
                routes=routes,
                cors=record.cors,
                _is_secure_api=True,    # special key marks the endpoint registered by "secure_api"
            )

            if version_info[0] >= 18:  ## v18
                # Note: we expose all endpoints, no need to select "active" endpoints because we check it in "api_execute". Endpoint state is toogled dynamically.
                routing["readonly"] = (
                    record.is_stats is False
                    and len(set(record.endpoint_ids.filtered(lambda x: x.state == "active").mapped("api_action")).intersection(["create", "update", "delete", "rpc"])) == 0
                )  # no app, no stats recording and only read/search actions

            if version_info[0] >= 19:  ## v19
                routing["type"] = "jsonrpc"

            routing_map = routing_map or http.root.get_db_router(db=False)
            endpoint = self._get_endpoint(
                method_ref=api_execute,
                method_args=[
                    record.id,
                ],
                routing=routing,
            )
            for url in routing["routes"]:
                is_rule_existed = False
                for added_endpoint in routing_map.iter_rules():  # Iterator[Rule] # https://werkzeug.palletsprojects.com/en/2.3.x/routing/#werkzeug.routing.Rule
                    if added_endpoint.rule == url:
                        is_rule_existed = True
                        break

                if is_rule_existed:
                    break

                # if not is_update_rule:
                # copied code from ir_http.py
                xtra_keys = "defaults subdomain build_only strict_slashes redirect_to alias host".split()
                kw = {k: routing[k] for k in xtra_keys if k in routing}
                if route2endpoint.get(url, False) and len(set(route2endpoint[url].mapped("http_method_id.name")).intersection(["GET", "DELETE"]))>0:
                    routing_http = copy.deepcopy(routing)
                    routing_http["type"] = "http"
                    endpoint_http = self._get_endpoint(
                        method_ref=api_execute,
                        method_args=[
                            record.id,
                        ],
                        routing=routing_http,
                    )
                    rule = werkzeug.routing.Rule(url, endpoint=endpoint_http, methods=routing_http["methods"], **kw)
                else:
                    rule = werkzeug.routing.Rule(url, endpoint=endpoint, methods=routing["methods"], **kw)
                rule.merge_slashes = False
                routing_map.add(rule)

        return True

    def btn_deactivate_api(self):
        for record in self:
            # generate routes from "record.endpoint_ids"
            endpoint_routes = list(set(record.endpoint_ids.mapped("route")))  # [...]
            endpoint_routes = [endr.replace(":id", "<id>").replace(":model", "<model>") for endr in endpoint_routes]
            endpoint_routes = [endr for endr in endpoint_routes if not endr.endswith("/bulk")]
            if not endpoint_routes:  # empty endpoints
                endpoint_routes = [
                    record.route,
                ]
            routes = endpoint_routes

        routing_map = http.root.get_db_router(db=False)

        # handle multiple versions of werkzeug
        is_modified_routing_map = False
        num_try = 0
        while not is_modified_routing_map and num_try <= 2:
            try:
                if num_try == 0:
                    routing_map._rules = [rule for rule in routing_map._rules if rule.rule not in routes]
                    is_modified_routing_map = True
                    pass
                elif num_try == 1:
                    rules_to_keep = [rule for rule in routing_map._rules if rule.rule not in routes]
                    routing_map._rules.clear()
                    for rule in rules_to_keep:
                        routing_map.add(rule)
                    is_modified_routing_map = True
                    pass
                elif num_try == 2:
                    if hasattr(routing_map, "_rules_by_endpoint") and isinstance(routing_map._rules_by_endpoint, dict):
                        endpoints_todel = []
                        for endpoint, rules in routing_map._rules_by_endpoint.items():  # t.Any, list[Rule] in dict[t.Any, list[Rule]]
                            for rule in rules:
                                if rule.rule in routes:
                                    endpoints_todel.append(rule.endpoint)
                                    break
                            pass
                        for endpoint2del in endpoints_todel:
                            routing_map._rules_by_endpoint.pop(endpoint2del, None)
                        is_modified_routing_map = True
                        pass
                    pass
            except:
                num_try += 1

        if not is_modified_routing_map:
            # raise error
            raise ValidationError(f"Cannot not deactivate APIs ({record.ids})")

        self.with_context(btn_deactivate_api=True).write({"state": "deactivated"})
        return True

    @api.model
    def btn_expose_new_api(self, model_name):  # res.partner
        model_description = self.env["ir.model"]._get(model_name).name  # Contact
        model_name_flat = model_name.replace(".", "_")  # res_partner
        new_name = model_description
        expose_api_route_prefix = self.env["ir.config_parameter"].sudo().get_param("secure_api.expose_api_route_prefix")  # /api/model
        expose_api_route_prefix = ("/" + expose_api_route_prefix) if not expose_api_route_prefix.startswith("/") else expose_api_route_prefix
        expose_api_route_prefix += "/" if not expose_api_route_prefix.endswith("/") else ""

        new_route = expose_api_route_prefix + model_name_flat  # /api/model/res_partner
        model_id = self.env["ir.model"]._get(model_name).id  # int

        # check route existence
        check_record = self.search([("route", "=", new_route)], limit=1)
        try_counter = 0
        while check_record and try_counter < 10:  # try 10 times at max
            try_counter += 1
            new_route = expose_api_route_prefix + model_name_flat + f"_{try_counter}"  # /api/model/res_partner_1
            new_name = model_description + f" ({try_counter})"  # Contact (1)
            check_record = self.search([("route", "=", new_route)], limit=1)  # UPDATE check record

        if try_counter >= 10:  # generate a random string
            random_postfix = random_string(size=6, digit=False, lower=True, upper=False)  # djzcch
            new_route = expose_api_route_prefix + model_name_flat + f"_{random_postfix}"  # /api/model/res_partner_djzcch
            new_name = model_description + f" ({random_postfix})"  # Contact (djzcch)
            pass

        api_form = self.env.ref("secure_api.secure_api_form_view", raise_if_not_found=False)
        return {
            "name": f"{new_name}",
            "type": "ir.actions.act_window",
            "view_mode": "form",
            "res_model": self._name,
            "context": {
                "default_name": new_name,
                "default_route": new_route,
                "default_model_id_alias": model_id,
            },
            "views": [(api_form.id, "form")],
            "view_id": api_form.id,
            "target": "current",
        }

    # /api/key/authenticate
    @api.model
    def api_key_authenticate(self, db, login=None, password=None):
        wsgienv = {
            "interactive": False,  # <- changed "True" to "False"
            "base_location": request.httprequest.url_root.rstrip("/"),
            "HTTP_HOST": request.httprequest.environ["HTTP_HOST"],
            "REMOTE_ADDR": request.httprequest.environ["REMOTE_ADDR"],
        }
        odoo_version = version_info[0]
        if odoo_version <= 17:
            uid = odoo.registry(db)["res.users"].authenticate(db, login, password, wsgienv)
        elif odoo_version <= 18:
            auth_info = odoo.registry(db)["res.users"].authenticate(db, {"login": login, "type": "password", "password": password}, wsgienv)
            uid = auth_info["uid"]
        else:  ## v19
            if not request.db or request.db != db:
                cr = odoo.modules.registry.Registry(db).cursor()
                env_with_db = odoo.api.Environment(cr, None, {})
            else:
                env_with_db = request.env

            auth_info = env_with_db["res.users"].authenticate({"login": login, "type": "password", "password": password}, wsgienv)
            uid = auth_info["uid"]

        session = request.session
        if odoo_version >= 19:
            session.uid = None
            session["pre_login"] = login
            session["pre_uid"] = uid
        else:
            if odoo_version >= 16:
                session.uid = None
                session.pre_login = login
            session.pre_uid = uid

        if odoo_version < 16:
            session.rotate = True
            session.db = db
            session.login = login
            request.disable_db = False

        user = request.env(user=uid)["res.users"].browse(uid)
        if odoo_version >= 18 and (auth_info.get("mfa") == "skip" or not user._mfa_url()):
            session.finalize(request.env(user=uid))
        elif not user._mfa_url():
            session.finalize(request.env(user=uid)) if odoo_version >= 16 else session.finalize()

        if odoo_version >= 16:
            if request.db == db:
                request.env = odoo.api.Environment(request.env.cr, session.uid, session.context)
                request.update_context(**session.context)
                request.env.cr.commit()
            else:
                if not request.db or request.db != db:
                    cr = odoo.modules.registry.Registry(db).cursor()
                    env = odoo.api.Environment(cr, None, {})
                else:
                    env = request.env
                request.session.db = db
                request._save_session(env)
                return env["ir.http"].with_user(request.session.uid).session_info()

        return request.env["ir.http"].session_info()

    def button_open_total_hit_stats(self):
        self.ensure_one()

        action = {
            "name": _("API Usage Statistics"),
            "type": "ir.actions.act_window",
            "res_model": "secure.api.stats.line",
            "context": {"create": False},
        }
        if len(self.secure_api_stats_id.line_ids) == 1:
            action.update(
                {
                    "view_mode": "form",
                    "res_id": self.secure_api_stats_id.line_ids.id,
                }
            )
        else:
            action.update(
                {
                    "view_mode": "list,form",
                    "domain": [("id", "in", self.secure_api_stats_id.line_ids.ids)],
                }
            )
        return action

    # ---------------------
    # API JSON EXPORT (used by Postman and Swagger wizards)
    # ---------------------
    def generate_api_json(self):
        """
        Generate API JSON representation for export.

        :return: Dictionary of APIs grouped by folder name, where each API has:
            - 'name': Name of the API
            - 'method': HTTP method (e.g., 'GET', 'POST')
            - 'url': URL of the API endpoint
            - 'headers': Dictionary of headers (optional)
            - 'body': Request body (optional, can be a dictionary or string)
            - 'description': Description of the API (optional)
        """
        result = {}
        base_url = self.env["ir.config_parameter"].sudo().get_param("web.base.url", default="http://localhost:8069")

        for record in self:
            folder_name = f"{record.name} {record.route}"  # Folder name
            if folder_name not in result:
                result[folder_name] = []

            for endpoint in record.endpoint_ids:
                for model in record.model_ids:
                    endpoint_route = endpoint.route.replace(":model", model.model)
                    result[folder_name].append(
                        {
                            "name": f"{endpoint.api_action.capitalize()} {model.name}",
                            "method": endpoint.http_method_id.name,
                            "url": base_url + re.sub(r":(\w+)", r"{{\1}}", endpoint_route),
                            "headers": {"Content-Type": "application/json"},
                            "body": {},
                            "is_secure_record_id": record.is_secure_record_id,
                        }
                    )
        return result

