from datetime import datetime
import importlib.util
from pathlib import Path
import pytest

spec=importlib.util.spec_from_file_location('account',Path(__file__).parents[1]/'helpers/account.py')
account=importlib.util.module_from_spec(spec);spec.loader.exec_module(account)

def test_confirmation_has_date_and_no_technical_verification():
    value=account.confirmation({key:True for key in account.FIELDS})
    assert value['verification']=='user_confirmed'
    assert datetime.fromisoformat(value['confirmed_at']).tzinfo is not None
    assert 'require_requesty_zdr' not in value

@pytest.mark.parametrize('value',[{}, {'eu_gateway':'true'}, {**dict.fromkeys(account.FIELDS,True),'require_requesty_zdr':False}])
def test_invalid_or_policy_override_not_accepted(value):
    with pytest.raises(ValueError):account.confirmation(value)
