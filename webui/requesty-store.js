import { createStore } from "/js/AlpineStore.js";
import { callJsonApi } from "/js/api.js";
import { toastFrontendSuccess } from "/components/notifications/notification-store.js";

export const store = createStore("requesty", {
    models: [], busy: false, search: "", showRejected: false,
    main: "", utility: "", presetName: "Requesty Private", key: "", hasKey: false,
    keyKnown: false, catalogPolicy: "", epoch: 0, ticket: "", testState: "",
    error: "", message: "", createdPreset: "", createdState: "", catalogLoaded: false,
    catalogTime: "", testedAt: 0, now: 0, timer: null,
    async onOpen() {
        this.cleanup();
        this.main = ""; this.utility = ""; this.search = ""; this.showRejected = false;
        this.error = ""; this.message = ""; this.createdPreset = ""; this.createdState = "";
        this.hasKey = false; this.keyKnown = false;
        this.now = Date.now();
        this.timer = setInterval(() => { this.now = Date.now(); }, 30000);
        const epoch = this.epoch;
        this.busy = true;
        try {
            const result = await callJsonApi("plugins/_model_config/api_keys", { action: "get" });
            if (epoch !== this.epoch) return;
            this.hasKey = !!result.keys?.requesty_guarded?.has_key;
            this.keyKnown = true;
        } catch { if (epoch === this.epoch) this.error = "Could not read the saved key status. Reopen settings to retry."; }
        finally { if (epoch === this.epoch) this.busy = false; }
    },
    cleanup() {
        this.epoch++;
        if (this.timer) clearInterval(this.timer);
        this.timer = null; this.busy = false; this.key = "";
        this.models = []; this.catalogPolicy = ""; this.catalogLoaded = false;
        this.catalogTime = ""; this.invalidateTest();
    },
    invalidateTest() { this.ticket = ""; this.testState = ""; this.testedAt = 0; },
    filtered() {
        const query = this.search.trim().toLowerCase();
        return this.models.filter(m => (this.showRejected || m.allowed) && m.id.toLowerCase().includes(query));
    },
    allowed() { return this.models.filter(m => m.allowed); },
    async saveRequirements(context) {
        if (this.busy || context.isSaving || !context.hasUnsavedChanges) return;
        const epoch = this.epoch;
        const snapshot = JSON.stringify(context.settings);
        const project = context.projectName || ""; const profile = context.agentProfileKey || "";
        this.busy = true; context.isSaving = true; this.error = ""; this.message = "";
        this.invalidateTest();
        try {
            const result = await callJsonApi("plugins", { action: "save_config", plugin_name: "requesty",
                project_name: project, agent_profile: profile, settings: JSON.parse(snapshot) });
            if (epoch !== this.epoch) return;
            if (!result.ok) throw new Error(result.error || "Could not save privacy requirements.");
            if (project !== (context.projectName || "") || profile !== (context.agentProfileKey || "")) return;
            context.settingsSnapshotJson = snapshot;
            this.message = "Privacy requirements saved. Continue by loading the model catalog.";
        } catch (e) { if (epoch === this.epoch) this.error = e.message; }
        finally { context.isSaving = false; if (epoch === this.epoch) this.busy = false; }
    },
    catalogCurrent(config) { return this.catalogLoaded && this.catalogPolicy === JSON.stringify(config); },
    testCurrent(config) {
        return !!this.ticket && this.testState === JSON.stringify([config, this.main, this.utility])
            && Math.max(this.now, Date.now()) - this.testedAt < 600000;
    },
    nextStep(config, unsaved = false) {
        if (this.busy) return "Working… Please wait.";
        if (config.require_requesty_zdr) return "Requests are blocked: Requesty organization ZDR cannot currently be verified.";
        if (!this.keyKnown) return "Saved key status is unknown. Reopen settings to retry.";
        if (!this.hasKey) return "Save your Requesty API key to start.";
        if (unsaved) return "Save the privacy requirements before testing or creating a setup.";
        if (!this.catalogCurrent(config)) return "Load models for the current privacy requirements.";
        if (!this.allowed().length) return "No models meet these requirements. Inspect the excluded models for reasons.";
        if (!this.main || !this.utility) return "Choose both the conversation model and the helper model.";
        if (this.createdPreset && this.createdState === JSON.stringify([config, this.main, this.utility]))
            return `Select ${this.createdPreset} under Models in a separate test chat. It has been created, not activated.`;
        if (!this.testCurrent(config)) return "Run the example model test. Changes or expired tests require a new test.";
        if (!this.presetName.trim()) return "Enter a name for your new model setup.";
        return "Ready to create a model setup. It will not be activated automatically.";
    },
    async saveKey() {
        if (this.busy || !this.key.trim()) return;
        const epoch = this.epoch; const key = this.key.trim();
        this.busy = true; this.error = ""; this.message = "";
        this.invalidateTest(); this.models = []; this.catalogPolicy = ""; this.catalogLoaded = false;
        try {
            const result = await callJsonApi("plugins/_model_config/api_keys", { action: "set", keys: { requesty_guarded: key } });
            if (epoch !== this.epoch) return;
            if (!result.ok) throw new Error("Could not save API key.");
            this.hasKey = true; this.keyKnown = true; this.key = "";
            this.message = "API key saved. Load the model catalog to check the connection.";
        } catch (e) { if (epoch === this.epoch) this.error = e.message; }
        finally { if (epoch === this.epoch) this.busy = false; }
    },
    async refresh(config) {
        if (this.busy || !this.hasKey) return;
        const snapshot = JSON.stringify(config); const epoch = this.epoch;
        this.busy = true; this.error = ""; this.message = "";
        this.models = []; this.catalogPolicy = ""; this.catalogLoaded = false; this.invalidateTest();
        try {
            const result = await callJsonApi("plugins/requesty/catalog", { config: JSON.parse(snapshot) });
            if (epoch !== this.epoch || snapshot !== JSON.stringify(config)) return;
            if (!result.ok) throw new Error(result.error || "Could not load the model catalog.");
            this.models = result.models; this.catalogPolicy = snapshot; this.catalogLoaded = true;
            this.catalogTime = new Date().toLocaleString();
            if (!this.allowed().some(m => m.id === this.main)) this.main = "";
            if (!this.allowed().some(m => m.id === this.utility)) this.utility = "";
            this.message = `${this.allowed().length} models meet the selected requirements according to the catalog.`;
        } catch (e) { if (epoch === this.epoch) this.error = e.message; }
        finally { if (epoch === this.epoch) this.busy = false; }
    },
    async createPreset(config, unsaved = false) {
        if (this.busy || unsaved || !this.catalogCurrent(config) || !this.testCurrent(config) || !this.presetName.trim()) return;
        const epoch = this.epoch;
        const payload = { name: this.presetName.trim(), main: this.main, utility: this.utility,
            config: JSON.parse(JSON.stringify(config)), ticket: this.ticket };
        this.busy = true; this.error = ""; this.message = ""; this.invalidateTest();
        try {
            const result = await callJsonApi("plugins/requesty/apply", payload);
            if (epoch !== this.epoch) return;
            if (!result.ok) throw new Error(result.error || "Could not create the model setup.");
            this.createdPreset = result.preset;
            this.createdState = JSON.stringify([payload.config, payload.main, payload.utility]);
            this.message = `Created: ${result.preset}. Not activated. Select this preset under Models in a separate test chat.`;
            toastFrontendSuccess(this.message, "Requesty");
        } catch (e) { if (epoch === this.epoch) this.error = e.message; }
        finally { if (epoch === this.epoch) this.busy = false; }
    },
    async testModels(config, unsaved = false) {
        if (this.busy || unsaved || !this.catalogCurrent(config) || !this.main || !this.utility) return;
        const snapshot = JSON.stringify([config, this.main, this.utility]); const epoch = this.epoch;
        const [policy, main, utility] = JSON.parse(snapshot);
        this.busy = true; this.error = ""; this.message = ""; this.invalidateTest();
        try {
            const result = await callJsonApi("plugins/requesty/validate", { main, utility, config: policy });
            if (epoch !== this.epoch || snapshot !== JSON.stringify([config, this.main, this.utility])) return;
            if (!result.ok) throw new Error(result.error || "Model test failed.");
            this.ticket = result.ticket; this.testState = snapshot; this.testedAt = Date.now(); this.now = this.testedAt;
            this.message = "Example model test passed. This checks technical compatibility, not the provider's actual data practices. You can create the setup now.";
        } catch (e) { if (epoch === this.epoch) this.error = e.message; }
        finally { if (epoch === this.epoch) this.busy = false; }
    },
    async recover() {
        if (this.busy) return;
        const epoch = this.epoch;
        this.busy = true; this.error = ""; this.message = ""; this.invalidateTest();
        try {
            const result = await callJsonApi("plugins/requesty/recover", {});
            if (epoch !== this.epoch) return;
            if (!result.ok) throw new Error(result.error || "Could not undo preset creation.");
            this.createdPreset = ""; this.createdState = ""; this.message = "Last preset creation undone. Check the active model selection.";
        } catch (e) { if (epoch === this.epoch) this.error = e.message; }
        finally { if (epoch === this.epoch) this.busy = false; }
    }
});
