# -*- coding: utf-8 -*-
import uuid
import secrets
from datetime import datetime, timezone, timedelta
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

import logging

_logger = logging.getLogger(__name__)

# Try to import PyJWT - it's optional
try:
    import jwt
    JWT_AVAILABLE = True
except ImportError:
    jwt = None
    JWT_AVAILABLE = False
    _logger.warning("PyJWT library not installed. JWT authentication features will be disabled. Install it with: pip install PyJWT")

# JWT Algorithm choices
JWT_ALGORITHMS = [
    ("HS256", "HS256 (HMAC with SHA-256)"),
    ("HS384", "HS384 (HMAC with SHA-384)"),
    ("HS512", "HS512 (HMAC with SHA-512)"),
]


class SecureApiAppToken(models.Model):
    _name = "secure.api.app.token"
    _description = "Secure API 3rd Application Tokens"

    name = fields.Char("Name", required=True)
    app_id = fields.Many2one("secure.api.app", string="Client Application", ondelete="cascade")
    expire_date = fields.Datetime("Expiration Date")
    state = fields.Selection(
        [
            ("active", "Active"),
            ("expired", "Expired"),
        ],
        string="State",
        default="active",
        store=False,
        readonly=True,
        compute="_compute_state",
    )

    @api.model
    def _cron_delete_old_access_token(self):
        records = self.search([("expire_date", "!=", False), ("expire_date", "<", fields.Datetime.now())])
        if records:
            records.unlink()
        pass

    def _compute_state(self):
        for record in self:
            if record.expire_date is not False and record.expire_date < fields.Datetime.now():
                record.state = "expired"
            else:
                record.state = "active"

    @api.model
    def get_3rd_party_app(self, access_token):
        record = self.search([("name", "=", access_token), ("expire_date", ">=", fields.Datetime.now())])
        if record:
            return record.app_id
        else:
            return False


class SecureApiApp(models.Model):
    _name = "secure.api.app"

    _description = "Secure API 3rd Applications"

    name = fields.Char("Name", required=True)
    auth_type = fields.Selection(
        [
            ("oauth2", "OAuth 2.0 (Opaque Token)"),
            ("jwt", "JWT (JSON Web Token)"),
        ],
        default="oauth2",
        string="Authentication Type",
        required=True,
        help="OAuth 2.0: Generates opaque tokens stored in the database. JWT: Generates stateless JSON Web Tokens.",
    )
    client_id = fields.Char("Client ID", required=True, default=lambda self: str(uuid.uuid4())[:16])
    client_secret = fields.Char("Client Secret", required=True, default=lambda self: secrets.token_urlsafe(24))
    expire_minute = fields.Integer("Access Token Expiry (minutes)", default=30, required=True)

    # JWT-specific fields
    jwt_secret = fields.Char(
        "JWT Secret Key",
        default=lambda self: secrets.token_urlsafe(32),
        help="Secret key used to sign JWT tokens. Keep this confidential!",
    )
    jwt_algorithm = fields.Selection(
        JWT_ALGORITHMS,
        default="HS256",
        string="JWT Algorithm",
        help="Algorithm used to sign JWT tokens.",
    )
    scope_create = fields.Boolean("Create", default=True)
    scope_read = fields.Boolean("Read", default=True)
    scope_update = fields.Boolean("Update", default=True)
    scope_delete = fields.Boolean("Delete", default=True)
    scope_search = fields.Boolean("Search", default=True)
    scope_rpc = fields.Boolean("Call a Method in Class (RPC)", default=True)
    mode = fields.Selection(
        [
            ("test", "Test Mode"),
            ("prod", "Production Mode"),
        ],
        default="test",
        string="Mode",
        required=True,
        help="Enable Test Mode to use the API in a sandbox environment. No real data or actions will be affected. Perfect for testing and development.",
    )
    state = fields.Selection(
        [
            ("enabled", "Enabled"),
            ("disabled", "Disabled"),
        ],
        default="enabled",
        string="State",
        required=True,
    )
    api_ids = fields.Many2many("secure.api", "secure_api_app_secure_api_rel", string="APIs", copy=True)
    endpoint_ids = fields.Many2many(
        "secure.api.endpoint",
        "secure_api_app_secure_api_endpoint_rel",
        string="Endpoints",
        compute="_compute_endpoint_ids",
        readonly=True,
        store=False,
    )
    access_token_ids = fields.One2many("secure.api.app.token", "app_id", string="Access Tokens")

    cmd_token_endpoint = fields.Text("Get Access Token", readonly=True, store=False, compute="_compute_cmd_token_endpoint")
    security_user_id = fields.Many2one(
        "res.users",
        string="Run as User",
        required=True,
        default=lambda self: self.env.user,
        help="The current request will perform using the rights of this user",
    )

    # Computed field to check if PyJWT is available (for UI warning)
    is_jwt_available = fields.Boolean(
        "Is JWT Available",
        compute="_compute_is_jwt_available",
        store=False,
    )

    def _compute_is_jwt_available(self):
        for record in self:
            record.is_jwt_available = JWT_AVAILABLE

    def btn_enable_app(self):
        self.update({"state": "enabled"})
        pass

    def btn_disable_app(self):
        self.update({"state": "disabled"})
        pass

    @api.depends("api_ids", "scope_create", "scope_read", "scope_update", "scope_delete", "scope_search", "scope_rpc")
    def _compute_endpoint_ids(self):
        for record in self:
            scope_names = ["scope_create", "scope_read", "scope_update", "scope_delete", "scope_search", "scope_rpc"]
            scope_arr = [scn.replace("scope_", "").lower() for scn in scope_names if getattr(record, scn)]  # ['create', 'read', 'update', ...]
            eptr_ids = []
            for secure_api in record.api_ids:
                eptr_ids += [endptr.id for endptr in secure_api.endpoint_ids if endptr.api_action in scope_arr]
            record.endpoint_ids = [(6, 0, eptr_ids)]
            pass
        pass

    @api.depends("auth_type", "client_id", "client_secret")
    def _compute_cmd_token_endpoint(self):
        base_url = self.env["ir.config_parameter"].sudo().get_param("web.base.url", default="http://localhost:8069")
        for record in self:
            if record.auth_type == "jwt":
                endpoint = "/api/jwt/token"
            else:
                endpoint = "/api/oauth2/token"
            record.cmd_token_endpoint = (
                "curl -X POST -F client_id="
                + record.client_id
                + " -F client_secret="
                + record.client_secret
                + " "
                + base_url
                + endpoint
            )
        pass

    def get_scope_actions(self):
        self.ensure_one()
        scope_names = ["scope_create", "scope_read", "scope_update", "scope_delete", "scope_search", "scope_rpc"]
        scope_arr = [scn.replace("scope_", "").lower() for scn in scope_names if getattr(self, scn)]
        return scope_arr  # ['create', 'read', 'update', ...]

    # JWT Methods
    def generate_jwt_token(self):
        """Generate a JWT access token for this application."""
        self.ensure_one()
        if not JWT_AVAILABLE:
            raise ValidationError(_("PyJWT library is not installed. Please install it with: pip install PyJWT"))
        if self.auth_type != "jwt":
            raise ValidationError(_("This application does not use JWT authentication."))

        now_utc = datetime.now(timezone.utc)
        expire_seconds = self.expire_minute * 60
        payload = {
            "app_id": self.id,
            "client_id": self.client_id,
            "user_id": self.security_user_id.id,
            "scope": self.get_scope_actions(),
            "iat": now_utc,
            "exp": now_utc + timedelta(seconds=expire_seconds),
        }
        token = jwt.encode(payload, self.jwt_secret, algorithm=self.jwt_algorithm)
        return token

    @api.model
    def validate_jwt_token(self, token):
        """
        Validate a JWT token and return the corresponding app if valid.
        Returns False if the token is invalid or expired.
        """
        if not JWT_AVAILABLE:
            _logger.warning("PyJWT library is not installed. JWT validation is disabled.")
            return False

        # Try to decode without verification first to get the app_id/client_id
        try:
            unverified_payload = jwt.decode(token, options={"verify_signature": False})
        except jwt.DecodeError:
            _logger.warning("JWT decode error: Invalid token format")
            return False

        # Find the app by client_id
        client_id = unverified_payload.get("client_id")
        app_id = unverified_payload.get("app_id")

        if app_id:
            app = self.sudo().browse(app_id)
            if not app.exists() or app.state != "enabled" or app.auth_type != "jwt":
                return False
        elif client_id:
            app = self.sudo().search([
                ("client_id", "=", client_id),
                ("state", "=", "enabled"),
                ("auth_type", "=", "jwt"),
            ], limit=1)
            if not app:
                return False
        else:
            return False

        # Now verify the token with the app's secret
        try:
            jwt.decode(token, app.jwt_secret, algorithms=[app.jwt_algorithm])
            return app
        except jwt.ExpiredSignatureError:
            _logger.warning("JWT token expired for app %s", app.name)
            return False
        except jwt.InvalidTokenError as e:
            _logger.warning("JWT validation error for app %s: %s", app.name, str(e))
            return False

