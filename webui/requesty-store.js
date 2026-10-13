import { createStore } from "/js/AlpineStore.js";
import { callJsonApi } from "/js/api.js";
import { toastFrontendSuccess } from "/components/notifications/notification-store.js";

export const store = createStore("requesty", {
    account: {}, accountSettings: {eu_gateway:false,requesty_zdr:false,provider_zdr:false,approved_eu_models:false},
    async loadAccount() {
        const epoch=this.epoch;
        const result=await callJsonApi('plugins/requesty/account',{...this.scopePayload()});
        if(epoch!==this.epoch)return;
        this.account=result.account || {};
        this.accountSettings={eu_gateway:false,requesty_zdr:false,provider_zdr:false,approved_eu_models:false,...this.account.settings};
    },
    async confirmAccount() {
        if(this.busy)return;
        const epoch=this.epoch;this.busy=true;
        try {
            const result=await callJsonApi('plugins/requesty/account',{action:'set',settings:{...this.accountSettings},...this.scopePayload()});
            if(epoch!==this.epoch)return;
            if(!result.ok)throw new Error(result.error);
            this.account=result.account;
            toastFrontendSuccess('Account settings recorded as user-confirmed, not technically verified.','A0 Privacy Model Gateway');
        } catch(e) {if(epoch===this.epoch)this.error=e.message;}
        finally {if(epoch===this.epoch)this.busy=false;}
    },
    instanceActive:false, nativePresets:false, models: [], busy: false, search: "", showRejected: false, showProviders: false,
    main: "", utility: "", presetName: "A0 Privacy Private", key: "", hasKey: false,
    keyKnown: false, catalogPolicy: "", epoch: 0, ticket: "", testState: "",
    error: "", message: "", createdPreset: "", createdState: "", catalogLoaded: false,
    catalogTime: "", testedAt: 0, now: 0, timer: null,
    scope: null, active: false, requirementsSaved: false, savedMain: "", savedUtility: "",
    scopePayload() { return this.scope || {}; },
    chatProfile() { return globalThis.Alpine?.store('chats')?.selectedContext?.agent_profile || ''; },
    async configureProfile(context, profile) {
        if (this.busy || context.isLoading || context.isSaving || !profile) return;
        if (!(context.agentProfiles || []).some(item => item.key === profile)) return;
        context.agentProfileKey = profile;
        await context.onScopeChanged();
    },
    setScope(context) {
        const next = {project_name:context.projectName || "",agent_profile:context.agentProfileKey || ""};
        if (JSON.stringify(next) !== JSON.stringify(this.scope)) this.onOpen(context);
    },
    async onOpen(context = {}) {
        this.cleanup();
        this.scope = {project_name:context.projectName || "",agent_profile:context.agentProfileKey || ""};
        this.main = ""; this.utility = ""; this.search = ""; this.showRejected = false;
        this.error = ""; this.message = ""; this.createdPreset = ""; this.createdState = "";
        this.hasKey = false; this.keyKnown = false;
        if (!this.scope.agent_profile) { this.error = "Choose one agent profile in the toolbar first. No global settings or keys will be changed."; return; }
        this.now = Date.now();
        this.timer = setInterval(() => { this.now = Date.now(); }, 30000);
        const epoch = this.epoch;
        this.busy = true;
        try {
            const result = await callJsonApi("plugins/requesty/key", { action: "get", ...this.scopePayload() });
            if (epoch !== this.epoch) return;
            if (!result.ok) throw new Error(result.error || "Could not read profile key status.");
            this.hasKey = !!result.has_key; this.createdPreset = result.setup || ""; this.active = !!result.active;
            this.instanceActive=!!result.instance_protection;
            this.nativePresets=!!result.native_presets;
            this.savedMain = result.main || ""; this.savedUtility = result.utility || "";
            this.main = this.savedMain; this.utility = this.savedUtility;
            this.presetName = this.createdPreset || "A0 Privacy Private";
            this.requirementsSaved = !!result.requirements_saved;
            this.keyKnown = true;
            await this.loadAccount();
        } catch { if (epoch === this.epoch) this.error = "Could not read the saved key status. Reopen settings to retry."; }
        finally { if (epoch === this.epoch) this.busy = false; }
    },
    cleanup() {
        this.account={};this.accountSettings={eu_gateway:false,requesty_zdr:false,provider_zdr:false,approved_eu_models:false};
        this.epoch++;
        if (this.timer) clearInterval(this.timer);
        this.timer = null; this.busy = false; this.key = ""; this.hasKey = false; this.keyKnown = false; this.active = false; this.requirementsSaved = false;
        this.models = []; this.catalogPolicy = ""; this.catalogLoaded = false;
        this.savedMain = ""; this.savedUtility = "";
        this.catalogTime = ""; this.invalidateTest();
    },
    invalidateTest() { this.ticket = ""; this.testState = ""; this.testedAt = 0; },
    filtered() {
        const query = this.search.trim().toLowerCase();
        return this.models.filter(m => (this.showRejected || m.allowed) && m.id.toLowerCase().includes(query));
    },
    allowed() { return this.models.filter(m => m.allowed); },
    choices() {
        const eligible=this.allowed();
        const hasShort=eligible.some(m=>!m.id.includes('/'));
        return eligible.filter(m=>this.showProviders || !hasShort || !m.id.includes('/') || m.id===this.main || m.id===this.utility);
    },
    async saveRequirements(context) {
        if (this.busy || context.isSaving || (!context.hasUnsavedChanges && this.requirementsSaved) || !context.agentProfileKey) return;
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
            this.requirementsSaved = true;
            this.message = "Privacy requirements saved for this profile.";
        } catch (e) { if (epoch === this.epoch) this.error = e.message; }
        finally { context.isSaving = false; if (epoch === this.epoch) this.busy = false; }
    },
    catalogCurrent(config) { return this.catalogLoaded && this.catalogPolicy === JSON.stringify(config); },
    testCurrent(config) {
        return !!this.ticket && this.testState === JSON.stringify([config, this.main, this.utility])
            && Math.max(this.now, Date.now()) - this.testedAt < 600000;
    },
    nextStep(config, unsaved = false) {
        if (!this.scope?.agent_profile) return "Choose one agent profile in the settings toolbar first.";
        if (this.busy) return "Working… Please wait.";
        if (this.active) return "This profile uses its Requesty setup. To change models, load the catalog below. Other profiles keep their own models and keys.";
        if (config.require_requesty_zdr) return "Requests are blocked: Requesty organization ZDR cannot currently be verified.";
        if (!this.keyKnown) return "Saved key status is unknown. Reopen settings to retry.";
        if (!this.hasKey) return "Save your Requesty API key to start.";
        if (unsaved || !this.requirementsSaved) return "Save the privacy requirements for this profile before testing or creating a setup.";
        if (!this.catalogCurrent(config)) return "Load models for the current privacy requirements.";
        if (!this.allowed().length) return "No models meet these requirements. Inspect the excluded models for reasons.";
        if (!this.main || !this.utility) return "Choose both the conversation model and the helper model.";
        if (this.createdPreset && this.createdState === JSON.stringify([config, this.main, this.utility]))
            return `Activate ${this.createdPreset} for this profile when ready. It has been created, not activated.`;
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
            const result = await callJsonApi("plugins/requesty/key", { action: "set", key, ...this.scopePayload() });
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
            const result = await callJsonApi("plugins/requesty/catalog", { config: JSON.parse(snapshot), ...this.scopePayload() });
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
        if (this.busy || unsaved || !this.requirementsSaved || !this.catalogCurrent(config) || !this.testCurrent(config) || !this.presetName.trim()) return;
        const epoch = this.epoch;
        const payload = { name: this.presetName.trim(), main: this.main, utility: this.utility,
            config: JSON.parse(JSON.stringify(config)), ticket: this.ticket, ...this.scopePayload() };
        this.busy = true; this.error = ""; this.message = ""; this.invalidateTest();
        try {
            const result = await callJsonApi("plugins/requesty/apply", payload);
            if (epoch !== this.epoch) return;
            if (!result.ok) throw new Error(result.error || "Could not create the model setup.");
            this.createdPreset = result.preset;
            this.active = !!result.activated;
            this.savedMain = payload.main; this.savedUtility = payload.utility;
            this.createdState = JSON.stringify([payload.config, payload.main, payload.utility]);
            this.message = `Created: ${result.preset}. Not activated. Activate it here for the selected profile.`;
            toastFrontendSuccess(this.message, "A0 Privacy Model Gateway");
        } catch (e) { if (epoch === this.epoch) this.error = e.message; }
        finally { if (epoch === this.epoch) this.busy = false; }
    },
    async testModels(config, unsaved = false) {
        if (this.busy || unsaved || !this.requirementsSaved || !this.catalogCurrent(config) || !this.main || !this.utility) return;
        const snapshot = JSON.stringify([config, this.main, this.utility]); const epoch = this.epoch;
        const [policy, main, utility] = JSON.parse(snapshot);
        this.busy = true; this.error = ""; this.message = ""; this.invalidateTest();
        try {
            const result = await callJsonApi("plugins/requesty/validate", { main, utility, config: policy, ...this.scopePayload() });
            if (epoch !== this.epoch || snapshot !== JSON.stringify([config, this.main, this.utility])) return;
            if (!result.ok) throw new Error(result.error || "Model test failed.");
            this.ticket = result.ticket; this.testState = snapshot; this.testedAt = Date.now(); this.now = this.testedAt;
            this.message = "Example model test passed. This checks technical compatibility, not the provider's actual data practices. You can create the setup now.";
        } catch (e) { if (epoch === this.epoch) this.error = e.message; }
        finally { if (epoch === this.epoch) this.busy = false; }
    },
    async activate() {
        if (this.busy || !this.createdPreset || !this.scope?.agent_profile) return;
        const epoch = this.epoch; this.busy = true; this.error = "";
        try {
            const result = await callJsonApi("plugins/requesty/activate", {active:true,...this.scopePayload()});
            if (epoch !== this.epoch) return;
            if (!result.ok) throw new Error(result.error || "Could not activate profile setup.");
            this.active = true; this.message = "Requesty setup activated for this profile only.";
        } catch(e) { if (epoch === this.epoch) this.error = e.message; }
        finally { if (epoch === this.epoch) this.busy = false; }
    },
    async recover() {
        if (this.busy) return;
        const epoch = this.epoch;
        this.busy = true; this.error = ""; this.message = ""; this.invalidateTest();
        try {
            const result = await callJsonApi("plugins/requesty/recover", this.scopePayload());
            if (epoch !== this.epoch) return;
            if (!result.ok) throw new Error(result.error || "Could not undo preset creation.");
            this.active = false; this.message = "Profile setup deactivated. Native model settings apply again.";
        } catch (e) { if (epoch === this.epoch) this.error = e.message; }
        finally { if (epoch === this.epoch) this.busy = false; }
    }
});
