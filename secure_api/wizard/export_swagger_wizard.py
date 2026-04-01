# -*- coding: utf-8 -*-
import base64
import json
import re
from urllib.parse import urlparse
from odoo import api, fields, models, tools, _

import logging

_logger = logging.getLogger(__name__)


class ExportSwaggerWizard(models.TransientModel):
    _name = "export.swagger.wizard"
    _description = "Export Swagger Wizard"

    name = fields.Char("Title", required=True, default="APIs")
    description = fields.Text("Description")
    version = fields.Char("Version", required=True, default="1.0.0")
    content = fields.Binary("Swagger Content")

    def download_swagger_spec(self):
        ids = self.env.context["active_ids"]  # selected record ids
        secure_api_records = self.env["secure.api"].browse(ids)
        swagger_spec_str = self.generate_swagger_spec_from_records(
            title=self.name,
            description=self.description,
            version=self.version,
            secure_api_records=secure_api_records,
        )
        self.content = base64.b64encode(swagger_spec_str.encode("utf-8")).decode("utf-8")
        return {
            "type": "ir.actions.act_url",
            "url": f"/web/content/export.swagger.wizard/{self.id}/content/{self.name}.swagger.json?download=true",
            "target": "self",
            "close": True,
        }

    def generate_swagger_spec_from_records(self, title, description, version, secure_api_records):
        """Generate Swagger spec from secure.api records."""
        apis = secure_api_records.generate_api_json()
        return self.generate_swagger_spec(title, description, version, apis)

    def generate_swagger_spec(self, title, description, version, apis):
        """
        Generate a Swagger/OpenAPI 3.0 specification JSON string containing multiple APIs.

        :param title: Title of the API specification
        :param description: Description of the API specification
        :param version: Version of the API specification
        :param apis: Dictionary of APIs grouped by folder name
        :return: JSON string representing the OpenAPI 3.0 specification
        """
        base_url = self.env["ir.config_parameter"].sudo().get_param("web.base.url", default="http://localhost:8069")

        # Parse base URL to get server info
        parsed_url = urlparse(base_url)

        swagger_spec = {
            "openapi": "3.0.3",
            "info": {
                "title": title or "API Documentation",
                "description": description or "",
                "version": version or "1.0.0",
            },
            "servers": [
                {
                    "url": base_url,
                    "description": "API Server",
                }
            ],
            "paths": {},
            "tags": [],
            "components": {
                "schemas": {},
                "securitySchemes": {
                    "bearerAuth": {
                        "type": "http",
                        "scheme": "bearer",
                        "bearerFormat": "JWT",
                    },
                    "apiKeyAuth": {
                        "type": "apiKey",
                        "in": "header",
                        "name": "Authorization",
                    },
                },
            },
        }

        # Create tags from folder names
        for folder_name in apis.keys():
            swagger_spec["tags"].append({
                "name": folder_name,
                "description": f"APIs for {folder_name}",
            })

        # Process each API endpoint
        for folder_name, api_list in apis.items():
            for api in api_list:
                url = api.get("url", "")
                method = api.get("method", "GET").lower()

                # Extract path from URL (remove base URL)
                if base_url in url:
                    path = url.replace(base_url, "")
                else:
                    # Extract path from full URL
                    parsed = urlparse(url)
                    path = parsed.path

                # Convert path parameters from {{param}} format to {param} format for OpenAPI
                path = re.sub(r"\{\{(\w+)\}\}", r"{\1}", path)

                # Initialize path if not exists
                if path not in swagger_spec["paths"]:
                    swagger_spec["paths"][path] = {}

                # Build operation object
                # Create unique operationId by combining method, path, and name
                operation_id_path = re.sub(r"[^a-zA-Z0-9]", "_", path).strip("_")
                operation_id_name = api.get('name', '').replace(' ', '_').lower()
                operation_id = f"{method}_{operation_id_path}_{operation_id_name}"
                # Remove consecutive underscores and clean up
                operation_id = re.sub(r"_+", "_", operation_id).strip("_")

                operation = {
                    "tags": [folder_name],
                    "summary": api.get("name", ""),
                    "description": api.get("description", ""),
                    "operationId": operation_id,
                    "parameters": [],
                    "responses": {
                        "200": {
                            "description": "Successful response",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                    }
                                }
                            },
                        },
                        "400": {
                            "description": "Bad request",
                        },
                        "401": {
                            "description": "Unauthorized",
                        },
                        "404": {
                            "description": "Not found",
                        },
                        "500": {
                            "description": "Internal server error",
                        },
                    },
                    "security": [
                        {"bearerAuth": []},
                        {"apiKeyAuth": []},
                    ],
                }

                # Extract path parameters
                path_params = re.findall(r"\{(\w+)\}", path)
                is_secure_record_id = api.get("is_secure_record_id", False)
                for param in path_params:
                    # Determine parameter type: "id" is string if is_secure_record_id is True, otherwise integer
                    if param == "id":
                        param_type = "string" if is_secure_record_id else "integer"
                    else:
                        param_type = "string"
                    operation["parameters"].append({
                        "name": param,
                        "in": "path",
                        "required": True,
                        "schema": {
                            "type": param_type,
                        },
                        "description": f"The {param} parameter",
                    })

                # Add query parameters for GET requests
                if method == "get":
                    # Add common query parameters for search/list operations
                    if "search" in api.get("name", "").lower() or "list" in path.lower():
                        operation["parameters"].extend([
                            {
                                "name": "domain",
                                "in": "query",
                                "required": False,
                                "schema": {"type": "string"},
                                "description": "Domain filter for records",
                            },
                            {
                                "name": "offset",
                                "in": "query",
                                "required": False,
                                "schema": {"type": "integer", "default": 0},
                                "description": "Number of records to skip",
                            },
                            {
                                "name": "limit",
                                "in": "query",
                                "required": False,
                                "schema": {"type": "integer", "default": 80},
                                "description": "Maximum number of records to return",
                            },
                            {
                                "name": "order",
                                "in": "query",
                                "required": False,
                                "schema": {"type": "string"},
                                "description": "Order by field (e.g., 'name asc, id desc')",
                            },
                        ])

                # Set requestBody based on HTTP method
                if method in ["post", "put", "patch"]:
                    operation["requestBody"] = {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {},
                                }
                            }
                        },
                    }

                swagger_spec["paths"][path][method] = operation

        return json.dumps(swagger_spec, indent=2)

