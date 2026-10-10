import { createStore } from "/js/AlpineStore.js";
import { callJsonApi } from "/js/api.js";
import { toastFrontendError, toastFrontendSuccess } from "/components/notifications/notification-store.js";

export const store = createStore("requesty", {
    models: [], busy: false, search: "", showRejected: false,
    main: "", utility: "", presetName: "Requesty Private", key: "", hasKey: false,
    catalogPolicy: "", epoch: 0, ticket: "", testState: "",
    async onOpen() {
        this.epoch++;
        this.models = []; this.main = ""; this.utility = ""; this.catalogPolicy = ""; this.ticket = "";
        try {
            const result = await callJsonApi("plugins/_model_config/api_keys", { action: "get" });
            this.hasKey = !!result.keys?.requesty_guarded?.has_key;
        } catch { toastFrontendError("Could not load API key status.", "Requesty"); }
    },
    cleanup() { this.epoch++; this.key = ""; this.models = []; },
    filtered() {
        const query = this.search.toLowerCase();
        return this.models.filter(m => (this.showRejected || m.allowed) && m.id.toLowerCase().includes(query));
    },
    async saveKey() {
        if (this.busy || !this.key.trim()) return;
        this.busy = true;
        try {
            const result = await callJsonApi("plugins/_model_config/api_keys", { action: "set", keys: { requesty_guarded: this.key.trim() } });
            if (!result.ok) throw new Error("Could not save API key.");
            this.hasKey = true; this.key = ""; this.models = []; this.catalogPolicy = "";
            toastFrontendSuccess("Requesty API key saved.", "Requesty");
        } catch (e) { toastFrontendError(e.message, "Requesty"); }
        finally { this.busy = false; }
    },
    async refresh(config) {
        if (this.busy) return;
        const snapshot = JSON.stringify(config); const epoch = this.epoch;
        this.busy = true; this.models = []; this.catalogPolicy = "";
        try {
            const result = await callJsonApi("plugins/requesty/catalog", { config: JSON.parse(snapshot) });
            if (epoch !== this.epoch || snapshot !== JSON.stringify(config)) return;
            if (!result.ok) throw new Error(result.error);
            this.models = result.models; this.catalogPolicy = snapshot;
            const allowed = this.models.filter(m => m.allowed);
            if (!allowed.some(m => m.id === this.main)) this.main = "";
            if (!allowed.some(m => m.id === this.utility)) this.utility = "";
        } catch (e) { toastFrontendError(e.message, "Requesty"); }
        finally { this.busy = false; }
    },
    async createPreset(config) {
        if (this.busy || this.catalogPolicy !== JSON.stringify(config) || !this.ticket || this.testState !== JSON.stringify([config, this.main, this.utility])) return;
        this.busy = true;
        try {
            const ticket = this.ticket; this.ticket = "";
            const result = await callJsonApi("plugins/requesty/apply", { name: this.presetName, main: this.main, utility: this.utility, config, ticket });
            if (!result.ok) throw new Error(result.error);
            toastFrontendSuccess(`Preset ${result.preset} created. Select it under Models for a test chat. Embeddings are preserved; the separate Vision slot is disabled.`, "Requesty");
        } catch (e) { toastFrontendError(e.message, "Requesty"); }
        finally { this.busy = false; }
    },
    async testModels(config) {
        if (this.busy || !this.main || !this.utility) return;
        this.busy = true; this.ticket = "";
        const snapshot = JSON.stringify([config, this.main, this.utility]); const epoch = this.epoch;
        try {
            const result = await callJsonApi("plugins/requesty/validate", { main: this.main, utility: this.utility, config });
            if (epoch !== this.epoch || snapshot !== JSON.stringify([config, this.main, this.utility])) return;
            if (!result.ok) throw new Error(result.error);
            this.ticket = result.ticket; this.testState = snapshot;
            toastFrontendSuccess("Synthetic model tests passed. You can now create the preset.", "Requesty");
        } catch (e) { toastFrontendError(e.message, "Requesty"); }
        finally { this.busy = false; }
    },
    async recover() {
        if (this.busy) return;
        this.busy = true;
        try {
            const result = await callJsonApi("plugins/requesty/recover", {});
            if (!result.ok) throw new Error(result.error);
            toastFrontendSuccess("Last preset creation undone. Check the active model selection.", "Requesty");
        } catch (e) { toastFrontendError(e.message, "Requesty"); }
        finally { this.busy = false; }
    }
});
