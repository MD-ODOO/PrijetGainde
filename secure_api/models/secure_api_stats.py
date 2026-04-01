# -*- coding: utf-8 -*-
import json
import pprint
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

import logging

_logger = logging.getLogger(__name__)


class SecureApiStats(models.Model):
    _name = "secure.api.stats"
    _description = "Secure API Stats"

    name = fields.Char()
    hit_success = fields.Integer("Success Count", default=0, aggregator="sum")
    hit_fail = fields.Integer("Error Count", default=0, aggregator="sum")
    total_hit = fields.Integer("Total Requests", compute="_compute_stats", store=True, aggregator="sum")
    rate_success = fields.Float("Success (%)", compute="_compute_stats", store=True, aggregator="avg")
    rate_fail = fields.Float("Error (%)", compute="_compute_stats", store=True, aggregator="avg")
    avg_elapsed_time = fields.Float("Avg. Execution Time (s)", compute="_compute_avg_elapsed_time", store=True, aggregator="avg")

    # one2one: https://odoo-development.readthedocs.io/en/latest/dev/py/one2one.html
    secure_api_id = fields.Many2one("secure.api", string="API", compute="_compute_secure_api_id", inverse="_inverse_secure_api_id", store=True)
    secure_api_ids = fields.One2many("secure.api", "secure_api_stats_id")

    line_ids = fields.One2many("secure.api.stats.line", "stats_id")

    # related fields
    secure_api_route = fields.Char(related="secure_api_id.route", store=True, readonly=False, depends=["secure_api_id.route"])
    secure_api_api_action = fields.Selection(related="secure_api_id.api_action", store=True, readonly=False, depends=["secure_api_id.api_action"])
    secure_api_model_ids = fields.Many2many(related="secure_api_id.model_ids")
    secure_api_auth = fields.Selection(related="secure_api_id.auth", store=True, readonly=False, depends=["secure_api_id.auth"])
    secure_api_category_id = fields.Many2one(related="secure_api_id.category_id", store=True, readonly=False, depends=["secure_api_id.category_id"])
    secure_api_state = fields.Selection(string="API State", related="secure_api_id.state", store=True, readonly=False, depends=["secure_api_id.state"])
    secure_api_is_stats = fields.Boolean(related="secure_api_id.is_stats", store=True, readonly=False, depends=["secure_api_id.is_stats"])

    @api.depends("secure_api_ids")
    def _compute_secure_api_id(self):
        for record in self:
            if not record.secure_api_ids:
                if not record.secure_api_id:
                    record.secure_api_id = False
                else:  # secure_api_id is False => do not change anything
                    pass
            else:
                if not record.secure_api_id or record.secure_api_id.id != record.secure_api_ids[0].id:
                    record.secure_api_id = record.secure_api_ids[0].id
                else:
                    # do not change if they're already equal
                    pass
        pass

    def _inverse_secure_api_id(self):
        for record in self:
            if not record.secure_api_id:
                if not record.secure_api_ids:
                    pass
                else:
                    record.secure_api_ids = False
            else:
                if not record.secure_api_ids:
                    record.secure_api_ids = [
                        (
                            6,
                            0,
                            [
                                record.secure_api_id.id,
                            ],
                        )
                    ]
                elif record.secure_api_ids[0].id != record.secure_api_id.id:
                    record.secure_api_ids = [
                        (
                            6,
                            0,
                            [
                                record.secure_api_id.id,
                            ],
                        )
                    ]
                else:
                    pass
        pass

    @api.depends("hit_success", "hit_fail")
    def _compute_stats(self):
        for rec in self:
            total = rec.hit_success + rec.hit_fail
            rec.total_hit = total
            if total == 0:
                rec.rate_success = 0
                rec.rate_fail = 0
            else:
                rec.rate_success = rec.hit_success / total
                rec.rate_fail = rec.hit_fail / total
        pass

    @api.depends("line_ids.elapsed_time")
    def _compute_avg_elapsed_time(self):
        for rec in self:
            lines = rec.line_ids.filtered(lambda l: l.elapsed_time > 0)
            if lines:
                rec.avg_elapsed_time = sum(lines.mapped("elapsed_time")) / len(lines)
            else:
                rec.avg_elapsed_time = 0.0
        pass

    @api.model
    def _parse_request_info(self, request):
        info = pprint.pformat(request.__dict__, depth=5)  # str
        return info

    @api.model
    def _parse_request_data(self, request):
        data = {}
        try:
            data = request.httprequest.args.to_dict()
        except:
            pass
        json_data = request.jsonrequest if hasattr(request, "jsonrequest") else {}
        json_data = json_data["__params"] if "__params" in json_data else json_data
        if isinstance(json_data, dict):
            data.update(json_data)
        else:  # [{}, {}]
            data = json_data

        ## v18
        if not data:
            request_data = {}  # might be a dict or list
            if hasattr(request.httprequest, "data") and request.httprequest.data:
                try:
                    request_data = json.loads(request.httprequest.data)
                except json.JSONDecodeError:
                    pass
                    # _logger.error("Cannot parse http request data (%s)" % str(request.httprequest.data))
            data = request_data

        return data

    def name_get(self):
        result = []
        for field in self:
            name = f"{field.hit_success}/{field.total_hit} " + _("Success") + f" ({field.rate_success*100:.2f}%)"  # 3/4 Success (75.00%)
            result.append((field.id, name))
        return result

    def success(self, request, elapsed_time=0.0, result={}):
        parsed_data = self._parse_request_data(request)
        parsed_request = self._parse_request_info(request)
        shorten_result = self.shortenize_result(result)
        for record in self:
            record.update({"hit_success": record.hit_success + 1})
            self.env["secure.api.stats.line"].create(
                {
                    "stats_id": record.id,
                    "line_type": "success",
                    "endpoint": request.httprequest.url,
                    "method": request.httprequest.method,
                    "data": parsed_data,
                    "request": parsed_request,
                    "elapsed_time": elapsed_time,
                    "result": shorten_result,
                }
            )
        pass

    def _shortenize_if_string(self, text, max_len=300):
        """
        Helper method to shortenize individual strings.

        Args:
            text: Any object that can be converted to string

        Returns:
            str: Shortened string representation
        """
        if isinstance(text, str) and len(text) > max_len:
            truncated = text[:max_len]
            return f"{truncated}...LONG TEXT ({len(text)}) WAS TRUNCATED"
        else:
            return text

    def shortenize_result(self, result, is_shorten=True):
        """
        Shorten the result object to prevent overly long text storage.

        Args:
            result: Can be a dictionary, list, string or other primary types

        Returns:
            str: Shortened string representation of the result
        """
        try:
            # Convert result to string representation
            if isinstance(result, dict):
                # Shortenize each value in the dictionary
                shortened_dict = {}
                for key, value in result.items():
                    shortened_dict[key] = self._shortenize_if_string(value) if is_shorten else value
                result_str = json.dumps(shortened_dict, indent=4, ensure_ascii=False, default=str)
            elif isinstance(result, (list, tuple)):
                # Shortenize each item in the list/tuple
                shortened_list = [self._shortenize_if_string(item) if is_shorten else item for item in result]
                result_str = json.dumps(shortened_list, indent=4, ensure_ascii=False, default=str)
            elif isinstance(result, str):
                result_str = self._shortenize_if_string(result) if is_shorten else result
            else:
                result_str = str(result)
            return result_str
        except Exception as e:
            # In case of any error, safely return str(result)
            _logger.warning(f"Error in shortenize_result: {e}")
            try:
                return str(result)
            except Exception:
                return "ERROR: Could not convert result to string"

    def error(self, request, error, elapsed_time=0.0):
        parsed_data = self._parse_request_data(request)
        parsed_request = self._parse_request_info(request)
        for record in self:
            record.update({"hit_fail": record.hit_fail + 1})
            self.env["secure.api.stats.line"].create(
                {
                    "stats_id": record.id,
                    "line_type": "error",
                    "endpoint": request.httprequest.url,
                    "method": request.httprequest.method,
                    "data": parsed_data,
                    "request": parsed_request,
                    "error": self.shortenize_result(error, is_shorten=False),
                    "elapsed_time": elapsed_time,
                }
            )
        pass


class SecureApiStatsLine(models.TransientModel):
    _name = "secure.api.stats.line"
    _description = "Secure API Stats Line"

    name = fields.Char(string="Name", compute="_compute_name", store=True)
    stats_id = fields.Many2one("secure.api.stats", string="API Statistics")
    endpoint = fields.Char("Endpoint")
    method = fields.Char("Method")
    line_type = fields.Selection(
        [
            ("success", "Success"),
            ("error", "Error"),
        ],
        string="Response Status",
        default="success",
    )
    data = fields.Text("Data")
    request = fields.Text("Request")
    error = fields.Text("Error")
    elapsed_time = fields.Float("Execution Time (s)", digits=(16, 6))
    result = fields.Text("Result")

    # related fields
    secure_api_id = fields.Many2one(related="stats_id.secure_api_id", store=True, readonly=False, depends=["stats_id.secure_api_id"])
    secure_api_api_action = fields.Selection(related="stats_id.secure_api_api_action", store=True, readonly=False, depends=["stats_id.secure_api_api_action"])
    secure_api_model_ids = fields.Many2many(related="stats_id.secure_api_model_ids")
    secure_api_auth = fields.Selection(related="stats_id.secure_api_auth", store=True, readonly=False, depends=["stats_id.secure_api_auth"])
    secure_api_category_id = fields.Many2one(
        related="stats_id.secure_api_category_id",
        store=True,
        readonly=False,
        depends=["stats_id.secure_api_category_id"],
    )
    secure_api_state = fields.Selection(
        string="API State",
        related="stats_id.secure_api_state",
        store=True,
        readonly=False,
        depends=["stats_id.secure_api_state"],
    )

    @api.depends("line_type")
    def _compute_name(self):
        for record in self:
            record.name = _("Success") if record.line_type == "success" else _("Error")
        pass

