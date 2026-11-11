from copy import deepcopy

import pymupdf
import pytest

from backend import pdf
from backend.logic import DEFAULTS, aggregate, calculate, statement


@pytest.fixture
def documents(monkeypatch):
    captured = []
    original = pdf.Document

    class Document(original):
        def __init__(self, settings, title):
            self.calls = []
            super().__init__(settings, title)
            captured.append(self)

        def kpis(self, values):
            self.calls.append(('kpis', values))
            return super().kpis(values)

        def data_table(self, headers, rows, **options):
            self.calls.append(('table', headers, rows, options))
            return super().data_table(headers, rows, **options)

    monkeypatch.setattr(pdf, 'Document', Document)
    return captured


def row(kind='debt', currency='USDT', amount=20, voided=False):
    return {**calculate(kind, amount, currency, 1, 'none', 0), 'clientId': 'one',
            'type': kind, 'date': '2026-11-11', 'time': '12:00', 'note': '', 'voided': voided}


def parsed(content):
    assert content.startswith(b'%PDF')
    return pymupdf.open(stream=content, filetype='pdf')


def test_report_counts_exclude_voided_rows_and_keep_zero_balances(documents):
    rows = [row(), row('payment'), row(currency='USD'), row(voided=True)]
    totals = aggregate(rows)
    assert totals['currencyCounts'] == {'USDT': 2, 'USD': 1}
    doc = parsed(pdf.report(DEFAULTS, [{'id': 'one', 'name': 'محمد'}], totals))
    kpis, currencies, clients = documents[0].calls
    assert len(kpis[1]) == 4
    assert currencies[1] == ['العملة', 'الصافي', 'عدد العمليات']
    assert currencies[2] == [['USDT', '0 ₮', 2], ['USD', '20 $', 1]]
    assert clients[2] == [['محمد', 'عليه', '20 $']]
    assert 'Page 1 of 1' in doc[0].get_text()
    assert len(doc[0].get_fonts()) >= 2


def test_empty_report_keeps_headers_and_literal_identity(documents):
    settings = {**deepcopy(DEFAULTS), 'shopName': '<script>دفتر & شركة</script>'}
    assert aggregate([])['currencyCounts'] == {}
    doc = parsed(pdf.report(settings, [], aggregate([])))
    assert doc.metadata['title'] == 'تقرير عام — ' + settings['shopName']
    assert all(not call[2] for call in documents[0].calls if call[0] == 'table')
    assert len(documents[0].calls[0][1]) == 4


def test_statement_totals_signed_amounts_zero_commission_and_metadata(documents):
    data = statement([row(), row('payment', amount=5)], '2026-11-01', '2026-11-30')
    doc = parsed(pdf.client_statement(DEFAULTS, {'name': 'محمد', 'phone': '770000000'}, data,
                                      '2026-11-01', '2026-11-30', 'ALL'))
    kpis, table = documents[0].calls
    assert len(kpis[1]) == 4
    assert table[2][0][3] == '+20 USDT'
    assert table[2][1][3] == '−5 USDT'
    assert table[2][0][5] == '—'
    assert table[3] == {'statement': True, 'closing': '15 $'}
    assert '770000000' in doc[0].get_text()
    assert '2026-11-01' in doc[0].get_text()


def test_empty_statement_retains_eight_columns_and_closing_balance(documents):
    data = statement([], '2026-11-01', '2026-11-30', 'SAR')
    doc = parsed(pdf.client_statement(DEFAULTS, {'name': '<عميل>', 'phone': ''}, data, '', '', 'SAR'))
    table = documents[0].calls[1]
    assert len(table[1]) == 8
    assert table[2] == [['—', 'لا حركات في هذه الفترة', '', '', '', '', '', '0 ر.س']]
    assert table[3]['closing'] == '0 ر.س'
    assert doc.metadata['title'] == 'كشف حساب — <عميل>'


def test_multipage_statement_repeats_headers_and_counts():
    records = [{**row(), 'note': 'تفاصيل حوالة العميل الطويلة ' * 3} for _ in range(90)]
    data = statement(records, '', '')
    doc = parsed(pdf.client_statement(DEFAULTS, {'name': 'عميل'}, data, '', '', 'ALL'))
    assert len(doc) > 2
    for index, page in enumerate(doc):
        text = page.get_text()
        assert f'Page {index + 1} of {len(doc)}' in text
        assert 'USDT' in text
        assert '12:00' in text


def test_rendering_failure_is_not_swallowed(monkeypatch):
    def unavailable(*args, **kwargs):
        raise RuntimeError('PDF renderer unavailable')

    monkeypatch.setattr(pdf.Document, 'output', unavailable)
    with pytest.raises(RuntimeError, match='PDF renderer unavailable'):
        pdf.report(DEFAULTS, [], aggregate([]))
