/** @odoo-module */

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component, onWillUnmount } from "@odoo/owl";

/**
 * Widget OWL pour le scan de code-barres dans le formulaire d'inventaire.
 *
 * - Bouton caméra : utilise BarcodeDetector API (Chrome/Edge/Samsung) ou
 *   l'input file capture="environment" en fallback.
 * - Handler global : s'enregistre sur le service barcode d'Odoo pour
 *   intercepter les scans de l'app mobile AVANT que le module stock
 *   ne les traite (message "produit n'existe pas").
 */
class AssetInventoryBarcodeHandler extends Component {
    static template = "asset_management_override.AssetInventoryBarcodeHandler";
    static props = { record: Object, "*": true };

    setup() {
        this.notification = useService("notification");
        this.orm = useService("orm");
        this._unregister = null;

        // Enregistrement sur le service barcode Odoo (priorité haute)
        try {
            const barcodeService = useService("barcode");
            if (typeof barcodeService.add === "function") {
                // Odoo 17+ API : add(callback, {sequence})
                this._unregister = barcodeService.add(
                    (barcode) => this._handleGlobalBarcode(barcode),
                    { sequence: 1 }   // Séquence faible = priorité haute
                );
            } else if (barcodeService.bus) {
                // API bus alternative
                const handler = ({ detail }) => {
                    this._handleGlobalBarcode(detail.barcode || detail);
                };
                barcodeService.bus.addEventListener("barcode_scanned", handler);
                this._unregister = () =>
                    barcodeService.bus.removeEventListener("barcode_scanned", handler);
            }
        } catch (_e) {
            // Service non disponible — le champ barcode_scan reste actif
        }

        onWillUnmount(() => {
            if (this._unregister) {
                this._unregister();
                this._unregister = null;
            }
        });
    }

    /**
     * Intercepte les scans globaux (app mobile, douchette USB, etc.)
     * Retourne true si on prend en charge le barcode (bloque la propagation
     * vers le handler stock).
     */
    async _handleGlobalBarcode(barcode) {
        const state = this.props.record.data.state;
        const recordId = this.props.record.resId || this.props.record.data.id;
        if (state !== "in_progress" || !recordId) {
            return false; // On ne gère pas, laisser passer
        }
        await this._processBarcode(recordId, barcode);
        return true; // Barcode traité, ne pas propager au handler stock
    }

    async _processBarcode(recordId, barcode) {
        if (!barcode) return;
        try {
            const result = await this.orm.call(
                "asset.inventory",
                "action_scan_barcode",
                [[recordId], barcode]
            );
            if (result.status === "found") {
                this.notification.add(`✓ ${result.name} ajouté`, {
                    type: "success",
                    sticky: false,
                });
                await this.props.record.load();
            } else if (result.status === "duplicate") {
                this.notification.add(`"${result.name}" est déjà dans l'inventaire.`, {
                    type: "warning",
                    sticky: false,
                });
            } else if (result.status === "destroyed") {
                this.notification.add(`"${result.name}" est en statut Sorti — exclu de l'inventaire.`, {
                    type: "warning",
                    sticky: false,
                });
            } else {
                this.notification.add(`Actif non trouvé : ${result.barcode || barcode}`, {
                    type: "warning",
                    sticky: false,
                });
            }
        } catch (e) {
            this.notification.add(e.data?.message || "Erreur lors du scan.", {
                type: "danger",
            });
        }
    }

    /**
     * Bouton caméra — ouvre le scanner Odoo (viseur temps réel).
     * Fallback : BarcodeDetector + capture photo si le module n'est pas dispo.
     */
    async onCameraClick() {
        const recordId = this.props.record.resId || this.props.record.data.id;
        if (!recordId) {
            this.notification.add(
                "Sauvegardez d'abord la session avant de scanner.",
                { type: "warning" }
            );
            return;
        }

        // 1. Essayer le scanner Odoo natif (viseur caméra en temps réel)
        try {
            const { scanBarcode } = await import("@web/core/barcode/barcode_scanner");
            const barcode = await scanBarcode(this.env);
            if (barcode) {
                await this._processBarcode(recordId, barcode);
            }
            return;
        } catch (_e) {
            // Module non disponible ou annulation — on continue avec le fallback
        }

        // 2. Fallback : BarcodeDetector + getUserMedia (viseur temps réel manuel)
        if ("BarcodeDetector" in window && navigator.mediaDevices) {
            await this._scanWithLiveCamera(recordId);
            return;
        }

        // 3. Dernier recours : capture photo
        await this._scanWithPhoto(recordId);
    }

    /**
     * Viseur temps réel avec BarcodeDetector et getUserMedia.
     * Capture chaque frame sur un canvas (plus fiable sur mobile que detect(video)).
     */
    async _scanWithLiveCamera(recordId) {
        let stream;
        try {
            stream = await navigator.mediaDevices.getUserMedia({
                video: { facingMode: "environment", width: { ideal: 1280 }, height: { ideal: 720 } },
            });
        } catch (_e) {
            this.notification.add("Accès à la caméra refusé.", { type: "warning" });
            await this._scanWithPhoto(recordId);
            return;
        }

        // Overlay plein écran
        const overlay = document.createElement("div");
        overlay.style.cssText =
            "position:fixed;inset:0;background:#000;z-index:9999;display:flex;" +
            "flex-direction:column;align-items:center;justify-content:center;gap:12px;";

        const video = document.createElement("video");
        video.autoplay = true;
        video.playsInline = true;
        video.muted = true;
        video.style.cssText = "width:100%;max-width:480px;border-radius:8px;display:block;";
        video.srcObject = stream;

        const label = document.createElement("div");
        label.textContent = "Pointez le code-barres vers la caméra";
        label.style.cssText = "color:#fff;font-size:15px;text-align:center;padding:0 16px;";

        const btn = document.createElement("button");
        btn.textContent = "✕  Annuler";
        btn.style.cssText =
            "padding:12px 36px;font-size:16px;background:#e53935;" +
            "color:#fff;border:none;border-radius:8px;cursor:pointer;";

        overlay.appendChild(video);
        overlay.appendChild(label);
        overlay.appendChild(btn);
        document.body.appendChild(overlay);

        // Canvas hors-écran pour capturer chaque frame
        const canvas = document.createElement("canvas");
        const ctx = canvas.getContext("2d");

        const detector = new window.BarcodeDetector({
            formats: ["code_128", "code_39", "code_93", "ean_13", "ean_8", "upc_a", "upc_e", "qr_code"],
        });

        let resolved = false;
        const cleanup = () => {
            if (resolved) return;
            resolved = true;
            stream.getTracks().forEach((t) => t.stop());
            if (overlay.parentNode) document.body.removeChild(overlay);
        };
        btn.onclick = cleanup;

        const tick = async () => {
            if (resolved) return;
            // Attendre que la vidéo soit prête
            if (video.readyState >= 2 && video.videoWidth > 0) {
                canvas.width = video.videoWidth;
                canvas.height = video.videoHeight;
                ctx.drawImage(video, 0, 0);
                try {
                    // Détecter depuis le canvas (image fixe) — beaucoup plus fiable sur mobile
                    const barcodes = await detector.detect(canvas);
                    if (barcodes.length > 0) {
                        cleanup();
                        await this._processBarcode(recordId, barcodes[0].rawValue);
                        return;
                    }
                } catch (_e) {}
            }
            // 150ms entre chaque tentative (~6 fps, stable sur mobile)
            setTimeout(tick, 150);
        };

        // Attendre 800ms après le premier frame pour que la caméra se stabilise (autofocus)
        video.onloadedmetadata = () => setTimeout(tick, 800);
    }

    /** Capture photo + BarcodeDetector (fallback ultime). */
    async _scanWithPhoto(recordId) {
        const input = document.createElement("input");
        input.type = "file";
        input.accept = "image/*";
        input.capture = "environment";
        input.onchange = async () => {
            const file = input.files && input.files[0];
            if (!file) return;
            if (!("BarcodeDetector" in window)) {
                this.notification.add(
                    "Scanner non supporté par ce navigateur.",
                    { type: "warning" }
                );
                return;
            }
            try {
                const detector = new window.BarcodeDetector({
                    formats: ["code_128", "code_39", "ean_13", "ean_8", "qr_code"],
                });
                const img = await createImageBitmap(file);
                const barcodes = await detector.detect(img);
                if (barcodes.length > 0) {
                    await this._processBarcode(recordId, barcodes[0].rawValue);
                } else {
                    this.notification.add("Aucun code-barres détecté. Réessayez.", {
                        type: "warning",
                    });
                }
            } catch (_e) {
                this.notification.add("Erreur lors de la détection.", { type: "danger" });
            }
        };
        input.click();
    }
}

registry.category("view_widgets").add("asset_inventory_barcode_handler", {
    component: AssetInventoryBarcodeHandler,
});
