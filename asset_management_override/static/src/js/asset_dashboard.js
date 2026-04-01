/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

export class AssetDashboard extends Component {
    static template = "asset_management_override.AssetDashboard";

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");

        this.state = useState({
            data: null,
            loading: true,
        });

        onWillStart(async () => {
            await this.loadData();
        });
    }

    async onRefresh() {
        this.state.loading = true;
        await this.loadData();
    }

    async loadData() {
        try {
            this.state.data = await this.orm.call(
                "asset.dashboard",
                "get_dashboard_data",
                [],
                {}
            );
        } catch (error) {
            console.error(error);
            this.state.data = this._fallbackData();
            this.notification.add(
                _t("Impossible de charger les données du tableau de bord."),
                { type: "warning" }
            );
        } finally {
            this.state.loading = false;
        }
    }

    // ------------------
    // Navigation
    // ------------------
    _openAssets(domain, name) {
        this.action.doAction({
            type: "ir.actions.act_window",
            name: name,
            res_model: "asset.management",
            views: [[false, "list"], [false, "form"]],
            domain: domain,
            context: {},
        });
    }

    onClickKpi(ev) {
        const type = ev.currentTarget.dataset.kpi;
        if (type === "count") {
            this._openAssets([["status", "!=", "destroyed"]], "Actifs en portefeuille");
        } else if (type === "value") {
            this._openAssets([["status", "!=", "destroyed"]], "Valeur globale du parc");
        } else {
            this._openAssets([["status", "=", "assign"]], "Actifs affectés");
        }
    }

    onClickStatus(ev) {
        const { status, label } = ev.currentTarget.dataset;
        this._openAssets([["status", "=", status]], `Actifs — ${label}`);
    }

    onClickLocation(ev) {
        const { locId, locName } = ev.currentTarget.dataset;
        const id = parseInt(locId, 10);
        const domain = id > 0
            ? [["localisation", "=", id]]
            : [["localisation", "=", false]];
        this._openAssets(domain, `Actifs — ${locName}`);
    }

    // ------------------
    // Helpers
    // ------------------
    get affectationRate() {
        const d = this.state.data;
        if (!d || !d.total_assets) return 0;
        const assigned = d.status_data.find(s => s.status === "assign");
        if (!assigned) return 0;
        return Math.round((assigned.count / d.total_assets) * 100);
    }

    get affectationCount() {
        const d = this.state.data;
        if (!d) return 0;
        const assigned = d.status_data.find(s => s.status === "assign");
        return assigned ? assigned.count : 0;
    }

    // SVG donut segments using stroke-dasharray technique.
    // Circle r=54, circumference C = 2π×54 ≈ 339.29
    // SVG is rotated -90deg in CSS so segments start at 12 o'clock.
    get donutSegments() {
        const d = this.state.data;
        if (!d || !d.status_data) return [];
        const total = d.status_data.reduce((s, x) => s + x.count, 0);
        if (!total) return [];

        const C = 2 * Math.PI * 54;
        let acc = 0;

        return d.status_data
            .filter(s => s.count > 0)
            .map(s => {
                const cfg = this.statusConfig(s.status);
                const pct = s.count / total;
                const dash = pct * C;
                const seg = {
                    color: cfg.color,
                    strokeDasharray: `${dash.toFixed(2)} ${(C - dash).toFixed(2)}`,
                    strokeDashoffset: (-acc).toFixed(2),
                    label: cfg.label,
                    count: s.count,
                    pct: Math.round(pct * 100),
                };
                acc += dash;
                return seg;
            });
    }

    rankBadge(idx) {
        if (idx === 0) return { text: "#1", style: "background:#fef9c3; color:#854d0e; border-color:#fde047;" };
        if (idx === 1) return { text: "#2", style: "background:#f1f5f9; color:#475569; border-color:#cbd5e1;" };
        if (idx === 2) return { text: "#3", style: "background:#fff7ed; color:#9a3412; border-color:#fed7aa;" };
        return { text: `#${idx + 1}`, style: "background:#f8fafc; color:#94a3b8; border-color:#e2e8f0;" };
    }

    formatCurrency(amount) {
        const d = this.state.data;
        const symbol = d?.currency_symbol || "FCFA";
        const pos = d?.currency_position || "after";
        const value = (amount || 0).toLocaleString("fr-FR", { maximumFractionDigits: 0 });
        return pos === "after" ? `${value} ${symbol}` : `${symbol} ${value}`;
    }

    formatCompact(amount) {
        if (!amount) return "0";
        if (amount >= 1_000_000_000) return (amount / 1_000_000_000).toLocaleString("fr-FR", { maximumFractionDigits: 1 }) + " Md";
        if (amount >= 1_000_000) return (amount / 1_000_000).toLocaleString("fr-FR", { maximumFractionDigits: 1 }) + " M";
        if (amount >= 1_000) return (amount / 1_000).toLocaleString("fr-FR", { maximumFractionDigits: 0 }) + " K";
        return amount.toLocaleString("fr-FR", { maximumFractionDigits: 0 });
    }

    statusPercent(count) {
        const total = this.state.data?.total_assets || 0;
        if (!total || !count) return 0;
        return Math.round((count / total) * 100);
    }

    locationPercent(count) {
        const total = this.state.data?.total_assets || 0;
        if (!total || !count) return 0;
        return Math.round((count / total) * 100);
    }

    statusConfig(code) {
        const map = {
            draft:        { color: "#64748b", bg: "#f1f5f9", icon: "fa-file-o",   label: "Brouillon"    },
            assign:       { color: "#059669", bg: "#ecfdf5", icon: "fa-user",      label: "Affecté"      },
            in_warehouse: { color: "#2563eb", bg: "#eff6ff", icon: "fa-archive",   label: "Disponible"   },
            repair:       { color: "#d97706", bg: "#fffbeb", icon: "fa-wrench",    label: "Maintenance"  },
            return:       { color: "#0891b2", bg: "#ecfeff", icon: "fa-undo",      label: "Retour"       },
            on_hold:      { color: "#7c3aed", bg: "#f5f3ff", icon: "fa-pause",     label: "En attente"   },
            destroyed:    { color: "#dc2626", bg: "#fef2f2", icon: "fa-sign-out",  label: "Sortie"       },
        };
        return map[code] || { color: "#64748b", bg: "#f1f5f9", icon: "fa-circle", label: code };
    }

    _fallbackData() {
        return {
            total_assets: 0,
            total_value: 0,
            status_data: [],
            location_data: [],
            currency_symbol: "FCFA",
            currency_position: "after",
        };
    }
}

registry.category("actions").add("asset_management_override.asset_dashboard", AssetDashboard);
