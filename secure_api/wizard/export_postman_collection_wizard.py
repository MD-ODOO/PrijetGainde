# -*- coding: utf-8 -*-
import base64
import json
from odoo import api, fields, models, tools, _

import logging

_logger = logging.getLogger(__name__)


class ExportPostmanCollectionWizard(models.TransientModel):
    _name = "export.postman.collection.wizard"
    _description = "Export Postman Collection Wizard"

    name = fields.Char("Name", required=True, default="APIs")
    description = fields.Text("Description")
    content = fields.Binary("Postman Collection Content")

    def download_postman_collection(self):
        ids = self.env.context["active_ids"]  # selected record ids
        secure_api_records = self.env["secure.api"].browse(ids)
        postman_collection_str = self.generate_postman_collection_from_records(
            name=self.name,
            description=self.description,
            secure_api_records=secure_api_records,
        )
        self.content = base64.b64encode(postman_collection_str.encode("utf-8")).decode("utf-8")
        return {
            "type": "ir.actions.act_url",
            "url": f"/web/content/export.postman.collection.wizard/{self.id}/content/{self.name}.postman_collection.json?download=true",
            "target": "self",
            "close": True,
        }

    def generate_postman_collection_from_records(self, name, description, secure_api_records):
        """Generate Postman collection from secure.api records."""
        apis = secure_api_records.generate_api_json()
        return self.generate_postman_collection(name, description, apis)

    def generate_postman_collection(self, name, description, apis):
        """
        Generate a Postman Collection JSON string containing multiple APIs.

        :param name: Name of the Postman Collection
        :param description: Description of the Postman Collection
        :param apis: List of APIs, where each API is a dictionary with keys:
                    - 'name': Name of the API
                    - 'method': HTTP method (e.g., 'GET', 'POST')
                    - 'url': URL of the API endpoint
                    - 'headers': Dictionary of headers (optional)
                    - 'body': Request body (optional, can be a dictionary or string)
                    - 'description': Description of the API (optional)
        :return: JSON string representing the Postman Collection
        """
        collection = {
            "info": {
                "name": name,
                "description": description,
                "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json",
            },
            "item": [],
        }

        for folder_name, api_list in apis.items():
            folder = {"name": folder_name, "item": []}

            for api in api_list:
                request = {
                    "method": api.get("method"),
                    "header": [{"key": k, "value": v} for k, v in api.get("headers", {}).items()],
                    "url": {
                        "raw": api.get("url"),
                        "protocol": api.get("url").split(":")[0] if "://" in api.get("url") else "http",
                        "host": api.get("url").split("://")[1].split("/")[0].split(":")[0],
                        "path": (api.get("url").split("://")[1].split("/")[1:] if "/" in api.get("url").split("://")[1] else []),
                    },
                }

                if api.get("body"):
                    request["body"] = {
                        "mode": "raw",
                        "raw": json.dumps(api["body"]) if isinstance(api["body"], dict) else api["body"],
                    }

                if api.get("description"):
                    request["description"] = api["description"]

                folder["item"].append({"name": api["name"], "request": request, "response": []})

            collection["item"].append(folder)

        return json.dumps(collection, indent=4)
