/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

export class TreasuryKpiDashboardV2 extends Component {
    static template = "treasury_management.TreasuryKpiDashboardV2";

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");

        const currentYear = new Date().getFullYear();
        this.state = useState({
            period: "last", // matches screenshot
            year: currentYear - 1,
            view: "all", // all | receipts | payments
            data: null,
            loading: true,
        });

        onWillStart(async () => {
            await this.loadData();
        });
    }

    // ------------------
    // Events
    // ------------------
    async onPeriodChange(ev) {
        const value = ev.target.value;
        const base = new Date().getFullYear();
        this.state.period = value;
        this.state.year = value === "current" ? base : value === "last" ? base - 1 : this.state.year;
        this.state.loading = true;
        await this.loadData();
    }

    async onYearChange(ev) {
        const year = Number(ev.target.value);
        if (!Number.isInteger(year)) return;
        this.state.period = "custom";
        this.state.year = year;
        this.state.loading = true;
        await this.loadData();
    }

    onViewChange(ev) {
        this.state.view = ev.target.value;
    }

    // ------------------
    // Backend
    // ------------------
    async loadData() {
        try {
            this.state.data = await this.orm.call(
                "treasury.kpi",
                "get_dashboard_data",
                [],
                { year: this.state.year }
            );
        } catch (error) {
            console.error(error);
            // Soft fallback with zeros to avoid blank dashboard
            this.state.data = this._fallbackData();
            this.notification.add(_t("Impossible de charger les données, affichage des indicateurs à zéro."), { type: "warning" });
        } finally {
            this.state.loading = false;
        }
    }

    // ------------------
    // Computed helpers
    // ------------------
    get paymentTracking() {
        const stats = this.state.data?.payments || {};
        const total = stats.total_count || 0;
        const paid = stats.paid_count || 0;
        const overdue = stats.overdue_count || 0;
        const pending = Math.max(total - paid - overdue, stats.pending_count || 0);
        const progress = total ? Math.round((paid / total) * 100) : 0;
        return { paid, pending, overdue, progress };
    }

    get receiptTracking() {
        const stats = this.state.data?.receipts || {};
        const total = stats.total_count || 0;
        const paid = stats.paid_count || 0;
        const overdue = stats.overdue_count || 0;
        const pending = Math.max(total - paid - overdue, stats.pending_count || 0);
        const progress = total ? Math.round((paid / total) * 100) : 0;
        return { paid, pending, overdue, progress };
    }

    formatCurrency(amount) {
        const c = this.state.data?.company;
        const symbol = c?.currency_symbol || "";
        const pos = c?.currency_position || "before";
        const value = (amount || 0).toLocaleString(undefined, { maximumFractionDigits: 0 });
        return pos === "after" ? `${value}${symbol}` : `${symbol}${value}`;
    }

    get cards() {
        const r = this.state.data?.receipts || {};
        const p = this.state.data?.payments || {};
        return [
            {
                key: "receipts_total",
                label: _t("Encaissements attendus"),
                value: r.total_amount || 0,
                note: "",
            },
            {
                key: "receipts_paid",
                label: _t("Encaissements perçus"),
                value: r.paid_amount || 0,
                note: `${_t("Taux")}: ${(r.paid_rate || 0)}%`,
            },
            {
                key: "payments_total",
                label: _t("Décaissements prévus"),
                value: p.total_amount || 0,
                note: "",
            },
            {
                key: "payments_paid",
                label: _t("Décaissements payés"),
                value: p.paid_amount || 0,
                note: `${_t("Taux")}: ${(p.paid_rate || 0)}%`,
            },
        ];
    }

    _fallbackData() {
        return {
            company: { currency_symbol: " ", currency_position: "after" },
            payments: { total_amount: 0, paid_amount: 0, total_count: 0, paid_count: 0, overdue_count: 0, pending_count: 0, paid_rate: 0 },
            receipts: { total_amount: 0, paid_amount: 0, total_count: 0, paid_count: 0, overdue_count: 0, pending_count: 0, paid_rate: 0 },
        };
    }
}

registry.category("actions").add("treasury_kpi_dashboard_v2", TreasuryKpiDashboardV2);
