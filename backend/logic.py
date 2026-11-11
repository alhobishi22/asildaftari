from copy import deepcopy
from decimal import Decimal, ROUND_FLOOR
import math

DEFAULTS = {
    'shopName': 'دفتري', 'shopPhone': '',
    'currencies': [{'code': 'USD', 'name': 'دولار أمريكي', 'symbol': '$'},
                   {'code': 'SAR', 'name': 'ريال سعودي', 'symbol': 'ر.س'},
                   {'code': 'YER', 'name': 'ريال يمني', 'symbol': 'ر.ي'},
                   {'code': 'USDT', 'name': 'تيثر', 'symbol': '₮'}],
    'rates': {'debt': {'USD': 1, 'SAR': 3.8, 'YER': 535, 'USDT': 1},
              'payment': {'USD': 1, 'SAR': 3.79, 'YER': 530, 'USDT': 1}},
    'commissions': {kind: {'mode': 'tiered', 'smallUsd': 1, 'threshold': 30,
                          'percent': percent, 'fixed': 1, 'currencies': ['USDT'],
                          'byCurrency': {'USDT': percent}}
                    for kind, percent in [('debt', 3), ('payment', 2)]}}


def number(value, default=0):
    if value is None or value == '':
        return default
    result = float(value)
    if not math.isfinite(result):
        raise ValueError('أدخل رقمًا صالحًا')
    return result


def rounded(value, places=2):
    scale = Decimal(10) ** places
    return float((Decimal(str(value)) * scale + Decimal('.5')).to_integral_value(rounding=ROUND_FLOOR) / scale)


def exchange_rate(settings, client, kind, currency):
    override = number((client or {}).get('rates', {}).get(kind, {}).get(currency))
    return override if override > 0 else number(settings.get('rates', {}).get(kind, {}).get(currency), 1) or 1


def commission_rule(settings, client, kind):
    rule = deepcopy(DEFAULTS['commissions'][kind])
    for source in [settings.get('commissions', {}).get(kind, {}),
                   (client or {}).get('commissions', {}).get(kind, {})]:
        for key, value in source.items():
            if key == 'byCurrency':
                rule[key].update({k: number(v) for k, v in value.items() if v is not None and v != ''})
            elif value is not None and value != '':
                rule[key] = value
    rule['mode'], rule['currencies'] = 'tiered', ['USDT']
    return rule


def automatic_commission(settings, client, kind, currency, amount, rate):
    rule = commission_rule(settings, client, kind)
    direction = 'add' if kind == 'debt' else 'deduct'
    if currency not in rule['currencies']:
        return {'commissionType': 'none', 'commissionValue': 0}
    usd = number(amount) / rate
    if 0 < usd < number(rule['threshold']) and number(rule['smallUsd']) > 0:
        return {'commissionType': f'fixed-{direction}', 'commissionValue': rounded(number(rule['smallUsd']) * rate, 4)}
    percent = number(rule.get('byCurrency', {}).get(currency), number(rule['percent']))
    if percent > 0:
        return {'commissionType': f'percent-{direction}', 'commissionValue': rounded(percent, 4)}
    if number(rule['fixed']) > 0:
        return {'commissionType': f'fixed-{direction}', 'commissionValue': rounded(rule['fixed'], 4)}
    return {'commissionType': 'none', 'commissionValue': 0}


def calculate(kind, amount, currency, rate, commission_type, commission_value):
    if kind not in ['debt', 'payment']:
        raise ValueError('نوع العملية غير صالح')
    amount, rate, value = number(amount), number(rate), max(0, number(commission_value))
    if amount <= 0:
        raise ValueError('أدخل مبلغًا أكبر من صفر')
    if rate <= 0:
        raise ValueError('سعر الصرف يجب أن يكون أكبر من صفر')
    if commission_type not in ['none', 'fixed-add', 'fixed-deduct', 'percent-add', 'percent-deduct']:
        raise ValueError('نوع العمولة غير صالح')
    fee = value if commission_type.startswith('fixed') else amount * value / 100 if commission_type.startswith('percent') else 0
    net = rounded(amount + (-fee if commission_type.endswith('deduct') else fee))
    usd = rounded(net / rate, 4)
    sign = 1 if kind == 'debt' else -1
    return dict(amount=rounded(amount), currency=currency, exchangeRate=rate,
                commissionType=commission_type, commissionValue=value,
                commissionAmount=rounded(fee), netAmount=net, usdEquivalent=usd,
                signedAmount=rounded(sign * net), signedUsd=rounded(sign * usd, 4),
                commissionUsd=rounded(fee / rate, 4))


def statement(records, start, end, currency='ALL'):
    eligible = [r for r in records if not r.get('voided') and (currency == 'ALL' or r['currency'] == currency)]
    def delta(r):
        return r['signedUsd'] if currency == 'ALL' else r['netAmount'] * (1 if r['type'] == 'debt' else -1)
    opening = sum(delta(r) for r in eligible if not start or r['date'] < start)
    period = sorted([r for r in eligible if (not start or r['date'] >= start) and (not end or r['date'] <= end)], key=lambda r: (r['date'], r.get('time', ''), r.get('createdAt', '')))
    balance, lines = opening, []
    for row in period:
        balance += delta(row)
        lines.append({'record': row, 'delta': delta(row), 'balance': rounded(balance, 4)})
    total = lambda kind: rounded(sum((r['usdEquivalent'] if currency == 'ALL' else r['netAmount']) for r in period if r['type'] == kind), 4)
    return dict(opening=rounded(opening, 4), closing=rounded(balance, 4), debts=total('debt'), payments=total('payment'), lines=lines)


def aggregate(records):
    result = dict(byClient={}, currencies={}, currencyCounts={}, usd=0, commission=0, count=0, debts=0, payments=0, monthly={})
    for row in records:
        if row.get('voided'):
            continue
        client = result['byClient'].setdefault(row['clientId'], {'usd': 0, 'currencies': {}})
        for target in [client['currencies'], result['currencies']]:
            target[row['currency']] = rounded(target.get(row['currency'], 0) + row['signedAmount'], 4)
        client['usd'] = rounded(client['usd'] + row['signedUsd'], 4)
        result['currencyCounts'][row['currency']] = result['currencyCounts'].get(row['currency'], 0) + 1
        result['usd'] += row['signedUsd']
        result['commission'] += row['commissionUsd']
        result['debts' if row['type'] == 'debt' else 'payments'] += row['usdEquivalent']
        month = result['monthly'].setdefault(row['date'][:7], {'debt': 0, 'payment': 0})
        month[row['type']] = rounded(month[row['type']] + row['usdEquivalent'], 4)
        result['count'] += 1
    for key in ['usd', 'commission', 'debts', 'payments']:
        result[key] = rounded(result[key], 4)
    return result
