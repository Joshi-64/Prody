"""Regression: Turso Hrana pipeline rejects float args sent as strings (HTTP 400 -> /dashboard 500)."""
import json
from decimal import Decimal

import db


def test_float_arg_is_json_number():
    a = db._turso_arg(1.5)
    assert a == {'type': 'float', 'value': 1.5}
    assert isinstance(json.loads(json.dumps(a))['value'], float)


def test_decimal_arg_is_float_number():
    assert db._turso_arg(Decimal('2.5')) == {'type': 'float', 'value': 2.5}


def test_int_arg_stays_string():
    assert db._turso_arg(7) == {'type': 'integer', 'value': '7'}


def test_milestone_insert_payload_types():
    # hours_at in record_milestones is a float; all args must be Hrana-valid
    for v in (3, 'Sprout', 0.0, 12.25, None):
        a = db._turso_arg(v)
        if a['type'] == 'float':
            assert isinstance(a['value'], float)
        elif a['type'] in ('integer', 'text'):
            assert isinstance(a['value'], str)
