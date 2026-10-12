"""User attestation only. Never used by the technical route policy."""
from datetime import datetime,timezone

FIELDS=('eu_gateway','requesty_zdr','provider_zdr','approved_eu_models')

def confirmation(value):
    if not isinstance(value,dict) or set(value)!=set(FIELDS) or any(type(v) is not bool for v in value.values()):
        raise ValueError('Confirm each account setting separately.')
    return {'settings':value,'confirmed_at':datetime.now(timezone.utc).isoformat(),
            'verification':'user_confirmed' if all(value.values()) else 'user_reported_incomplete'}
