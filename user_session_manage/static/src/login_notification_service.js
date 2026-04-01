/** @odoo-module **/

import { browser } from "@web/core/browser/browser";
import { registry } from "@web/core/registry";
import { user } from "@web/core/user";


export const loginNotificationService = {
    start(env) {
        browser.addEventListener( "load", () => {
            const current_session = env.services.orm.call("user.session.detail", "get_current_session_of_user", []);
            current_session.then((sessionRes) => {
                const result = env.services.orm.searchRead(
                    "user.session.detail",
                    [["user_id", "=", user.userId], ["session_identifier", "!=", sessionRes]],
                    ["first_activity", "ip_address", "device_platform", "browser", "is_last_login_display"],
                    { order: 'first_activity desc', limit: 1 }
                );
                result.then((res) => {
                    if (res.length > 0) {
                        if (!res[0].is_last_login_display){
                            const message = `IP: ${res[0].ip_address} | Browser: ${res[0].browser} | Timestamp: ${res[0].first_activity} | Device Platform: ${res[0].device_platform}`
                            env.services.notification.add(
                                message,
                                { sticky: true, type: "info",  title: "Your Last Login Information" }
                            );
                            env.services.orm.call("user.session.detail", "mark_last_login_display", [res[0].id], {});
                        }
                    }
                })
            })
        });
    }
    
}

registry.category("services").add("login_notification_service", loginNotificationService, { sequence: 1 });
