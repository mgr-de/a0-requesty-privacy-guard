# Single production PII detector

Local Privacy Guard 1.7.4 supplies the sole production text detector: optimized spaCy NER and Regex rules. Requesty Guard 0.6.0 retains its existing routing, local endpoint checks, policy, key ownership and media boundaries. It does not load or choose PII model backends.

Presidio/Nym evaluation branches and measurement evidence remain available on `archive/cpu-pii-evaluation-2026-10-13` in all three repositories. They are reference branches, not runtime/install branches. Production backend controls and optional detector-package installation have been removed from Local Privacy Guard.

The final release is verified with native regression suites, uninstall/reinstall in the provided Agent Zero test installation, preserved original credentials/presets/profile settings/mappings, and a real local Ollama chat. No paid Requesty test is needed for this change. Lifecycle evidence is recorded by the companion local guard release report.
