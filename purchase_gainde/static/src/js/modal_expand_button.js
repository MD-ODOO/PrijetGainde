/** @odoo-module **/

import { user } from "@web/core/user";

function hideExpandButtons() {
    for (const el of document.querySelectorAll(".o_expand_button, .modal-header .o_expand_button")) {
        el.style.display = "none";
    }
}

async function init() {
    const isSystemAdmin = await user.hasGroup("base.group_system");
    if (isSystemAdmin) {
        return;
    }

    hideExpandButtons();

    const observer = new MutationObserver(() => {
        hideExpandButtons();
    });

    observer.observe(document.body, {
        childList: true,
        subtree: true,
    });
}

init();
