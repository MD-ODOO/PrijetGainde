/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { user } from "@web/core/user";

function userSessions (env) {
    const description = _t("Your Session Devices");
    return {
        type: "item",
        id: "user_session",
        description,
        callback: async () => {
            env.services.action.doAction({
                name: description,
                type: "ir.actions.act_window",
                res_model: 'user.session.detail',
                views: [[false, 'list']],
                domain: [['user_id', '=', user.userId]],
            });
        },
        sequence: 41,
    };
}

function userLoginHistory (env) {
    const description = _t("Your Login History");
    return {
        type: "item",
        id: "login_history",
        description,
        callback: async () => {
            env.services.action.doAction({
                name: description,
                type: "ir.actions.act_window",
                res_model: 'user.login.history',
                views: [[false, 'list']],
                domain: [['user_id', '=', user.userId]],
            });
        },
        sequence: 42,
    };
}

registry
    .category("user_menuitems")
    .add("user_sessions", userSessions)
    .add("user_login_history", userLoginHistory)
