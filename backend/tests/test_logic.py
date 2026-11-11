from copy import deepcopy
import pytest
from backend.logic import DEFAULTS, calculate, automatic_commission, exchange_rate, statement, aggregate


@pytest.mark.parametrize('kind,amount,net', [('debt', 20, 21), ('debt', 30, 30.90), ('payment', 20, 19), ('payment', 30, 29.40)])
def test_spec_examples(kind, amount, net):
    fee = automatic_commission(DEFAULTS, {}, kind, 'USDT', amount, 1)
    row = calculate(kind, amount, 'USDT', 1, fee['commissionType'], fee['commissionValue'])
    assert row['netAmount'] == net
    assert row['signedUsd'] == (net if kind == 'debt' else -net)


def test_currency_and_client_override():
    client = {'rates': {'debt': {'USDT': 2}}, 'commissions': {'debt': {'smallUsd': 3, 'byCurrency': {'USDT': 5}}}}
    assert exchange_rate(DEFAULTS, client, 'debt', 'USDT') == 2
    assert automatic_commission(DEFAULTS, client, 'debt', 'USDT', 20, 2)['commissionValue'] == 6
    assert automatic_commission(DEFAULTS, client, 'debt', 'USDT', 60, 2)['commissionValue'] == 5
    for code in ['USD', 'SAR', 'YER']:
        assert automatic_commission(DEFAULTS, client, 'payment', code, 20, 1)['commissionType'] == 'none'


def test_legacy_fixed_fallback_and_manual_commission():
    settings = deepcopy(DEFAULTS)
    settings['commissions']['debt'].update(smallUsd=0, percent=0, byCurrency={'USDT': 0})
    assert automatic_commission(settings, {}, 'debt', 'USDT', 50, 1) == {'commissionType': 'fixed-add', 'commissionValue': 1}
    assert calculate('payment', 100, 'SAR', 4, 'percent-deduct', 2)['usdEquivalent'] == 24.5
    assert calculate('debt', 1.005, 'USD', 1, 'none', 0)['amount'] == 1.01


@pytest.mark.parametrize('amount,rate,kind', [(0, 1, 'debt'), (-5, 1, 'debt'), (1, 0, 'debt'), (1, float('nan'), 'debt'), (1, 1, 'other')])
def test_invalid_calculation(amount, rate, kind):
    with pytest.raises(ValueError):
        calculate(kind, amount, 'USD', rate, 'none', 0)


def test_statement_open_close_currency_void_and_empty():
    def row(kind, amount, day, currency='USD', rate=1, voided=False):
        return {**calculate(kind, amount, currency, rate, 'none', 0), 'type': kind, 'date': day, 'time': '12:00', 'clientId': 'one', 'voided': voided}
    records = [row('debt', 100, '2026-01-01'), row('payment', 20, '2026-02-01'), row('debt', 40, '2026-02-02'), row('debt', 500, '2026-02-03', voided=True), row('debt', 200, '2026-02-04', 'SAR', 4)]
    result = statement(records, '2026-02-01', '2026-02-28')
    assert (result['opening'], result['debts'], result['payments'], result['closing']) == (100, 90, 20, 170)
    assert [x['balance'] for x in result['lines']] == [80, 120, 170]
    assert statement(records, '2026-02-01', '2026-02-28', 'SAR')['closing'] == 200
    assert statement([], '2026-02-01', '2026-02-28')['lines'] == []
    totals = aggregate(records)
    assert totals['count'] == 4 and totals['usd'] == 170
    assert totals['currencies'] == {'USD': 120, 'SAR': 200}


def test_shipped_empty_start_edge():
    r = {**calculate('debt', 10, 'USD', 1, 'none', 0), 'type': 'debt', 'date': '2026-01-01'}
    assert statement([r], '', '')['closing'] == 20
