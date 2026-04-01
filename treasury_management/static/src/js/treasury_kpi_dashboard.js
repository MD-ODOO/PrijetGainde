/** @odoo-module **/

import { Component, onWillStart, onMounted, onWillUnmount, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

const MONTHS = [
    "janvier", "février", "mars", "avril", "mai", "juin",
    "juillet", "août", "septembre", "octobre", "novembre", "décembre",
];

export class TreasuryKpiDashboard extends Component {
    static template = "treasury_management.TreasuryKpiDashboard";

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");

        const currentYear = new Date().getFullYear();
        this.state = useState({
            year: currentYear,
            period: "current",
            view: "all", // all | receipts | payments
            data: null,
            loading: true,
        });

        this.chart = null;

        onWillStart(async () => {
            await this.loadData();
        });

        onMounted(() => this.renderChart());
        onWillUnmount(() => this.destroyChart());
    }

    // ------------------
    // Events
    // ------------------
    async onPeriodChange(ev) {
        const value = ev.target.value;
        const base = new Date().getFullYear();
        this.state.period = value;
        if (value === "current") {
            this.state.year = base;
        } else if (value === "last") {
            this.state.year = base - 1;
        }
        this.state.loading = true;
        await this.loadData();
        this.renderChart();
    }

    async onYearInput(ev) {
        const year = Number(ev.target.value);
        if (!Number.isInteger(year)) return;
        this.state.period = "custom";
        this.state.year = year;
        this.state.loading = true;
        await this.loadData();
        this.renderChart();
    }

    onViewChange(ev) {
        this.state.view = ev.target.value;
        this.renderChart();
    }

    // ------------------
    // Backend call
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
            this.notification.add(
                _t("Impossible de charger le tableau de bord."),
                { type: "danger" }
            );
        } finally {
            this.state.loading = false;
        }
    }

    get paymentTracking() {
        const stats = this.state.data?.payments || {};
        const total = stats.total_count || 0;
        const paid = stats.paid_count || 0;
        const pending = stats.pending_count || 0;
        const overdue = stats.overdue_count || 0;
        const progress = total ? Math.round((paid / total) * 100) : 0;
        return { paid, pending, overdue, progress };
    }

    // ------------------
    // Computed values
    // ------------------
    get summaryCards() {
        const s = this.state.data?.summary || {};
        const p = this.state.data?.payments || {};
        const r = this.state.data?.receipts || {};
        return [
            { key: "receipts_total", label: _t("Encaissements attendus"), value: r.total_amount || 0 },
            { key: "receipts_paid", label: _t("Encaissements perçus"), value: r.paid_amount || 0 },
            { key: "payments_total", label: _t("Décaissements planifiés"), value: p.total_amount || 0 },
            { key: "payments_paid", label: _t("Décaissements payés"), value: p.paid_amount || 0 },
        ];
    }

    get tableRows() {
        const revenue = this.state.data?.series?.revenue || [];
        const expenses = this.state.data?.series?.expenses || [];

        return revenue.map((r, i) => {
            const e = expenses[i] || {};
            return {
                month: MONTHS[(r.label || 1) - 1],
                revenue: r.value || 0,
                expenses: e.value || 0,
                delta: (r.value || 0) - (e.value || 0),
            };
        });
    }

    formatCurrency(amount) {
        const c = this.state.data?.company;
        const symbol = c?.currency_symbol || "";
        const pos = c?.currency_position || "before";

        const value = (amount || 0).toLocaleString(undefined, {
            maximumFractionDigits: 0,
        });

        return pos === "after" ? `${value}${symbol}` : `${symbol}${value}`;
    }

    // ------------------
    // Chart.js
    // ------------------
    renderChart() {
        if (!this.state.data || typeof Chart === "undefined") return;

        const canvas = this.el.querySelector("#treasury-kpi-chart");
        if (!canvas) return;

        this.destroyChart();

        const r = this.state.data.series.revenue || [];
        const e = this.state.data.series.expenses || [];

        this.chart = new Chart(canvas, {
            type: "line",
            data: {
                labels: r.map(m => MONTHS[(m.label || 1) - 1]),
                datasets: [
                    ...(this.state.view !== "payments"
                        ? [{
                            label: _t("Encaissements (facturés)"),
                            data: r.map(m => m.cumulative || 0),
                            tension: 0.25,
                            fill: true,
                        }]
                        : []),
                    ...(this.state.view !== "receipts"
                        ? [{
                            label: _t("Décaissements (factures fournisseurs)"),
                            data: e.map(m => m.cumulative || 0),
                            tension: 0.25,
                            fill: true,
                        }]
                        : []),
                ],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { position: "bottom" },
                },
            },
        });
    }

    destroyChart() {
        if (this.chart) {
            this.chart.destroy();
            this.chart = null;
        }
    }
}

// Register client action (Odoo 18)
registry
    .category("actions")
    .add("treasury_kpi_dashboard", TreasuryKpiDashboard);
