/** @odoo-module **/

import { ErrorDialog } from "@web/core/errors/error_dialogs";
import { patch } from "@web/core/utils/patch";
import { rpc } from "@web/core/network/rpc";
import { user } from "@web/core/user";

let configLoaded = false;
let enableJsMask = true;
let genericMessage = "Une erreur est survenue. Merci de contacter l'administrateur.";

async function loadConfig() {
    if (configLoaded) {
        return;
    }
    configLoaded = true;
    try {
        const enableValue = await rpc("/web/dataset/call_kw/ir.config_parameter/get_param", {
            model: "ir.config_parameter",
            method: "get_param",
            args: ["secure_error_handling.enable_js_mask", "True"],
            kwargs: {},
        });
        enableJsMask = enableValue !== "False";

        const messageValue = await rpc("/web/dataset/call_kw/ir.config_parameter/get_param", {
            model: "ir.config_parameter",
            method: "get_param",
            args: ["secure_error_handling.generic_message", genericMessage],
            kwargs: {},
        });
        if (messageValue) {
            genericMessage = messageValue;
        }
    } catch (error) {
        console.error("Failed to load secure error handling config:", error);
    }
}

patch(ErrorDialog.prototype, {
    async setup() {
        await super.setup(...arguments);
        await loadConfig();
        let isSystemUser = false;
        try {
            isSystemUser = await user.hasGroup("base.group_system");
        } catch {
            isSystemUser = false;
        }

        if (enableJsMask && this.props.traceback && !isSystemUser) {
            this.props.traceback = null;
            this.props.message = genericMessage;
        }
    },
});
