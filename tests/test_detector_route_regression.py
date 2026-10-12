"""Optional CPU detectors do not widen the permitted local model endpoints."""
from types import SimpleNamespace
from usr.plugins.requesty.helpers.runtime_guard import is_local_route


def test_cpu_detector_has_no_route_privileges():
    wrapper = SimpleNamespace(a0_model_conf=SimpleNamespace(api_base='http://127.0.0.1:11434'))
    for backend in ('local', 'presidio', 'nym'):
        assert is_local_route(wrapper, {'pii_backend': backend})
        assert not is_local_route(wrapper, {'api_base': 'https://example.invalid', 'pii_backend': backend})
        assert not is_local_route(wrapper, {'api_base': 'http://user:pass@127.0.0.1:11434', 'pii_backend': backend})
