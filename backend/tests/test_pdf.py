from copy import deepcopy
import pytest
from backend import pdf
from backend.logic import DEFAULTS, aggregate, calculate, statement


@pytest.fixture
def markup(monkeypatch):
    captured = []

    class Document:
        def __init__(self, string):
            captured.append(string)

        def write_pdf(self):
            return b'%PDF-test'

    monkeypatch.setattr(pdf, 'HTML', Document)
    return captured


def row(kind='debt', currency='USDT', amount=20, voided=False):
    return {**calculate(kind, amount, currency, 1, 'none', 0), 'clientId': 'one',
            'type': kind, 'date': '2026-11-11', 'time': '12:00', 'note': '', 'voided': voided}


def test_report_counts_exclude_voided_rows_and_keep_zero_balances(markup):
    rows = [row(), row('payment'), row(currency='USD'), row(voided=True)]
    totals = aggregate(rows)
    assert totals['currencyCounts'] == {'USDT': 2, 'USD': 1}
    pdf.report(DEFAULTS, [{'id': 'one', 'name': 'محمد'}], totals)
    html = markup[0]
    assert '<th scope="col">عدد العمليات</th>' in html
    assert '<td>USDT</td><td>0 ₮</td><td>2</td>' in html
    assert '<td>USD</td><td>20 $</td><td>1</td>' in html
    assert html.count('class="kpi"') == 4
    assert 'Page " counter(page) " of " counter(pages)' in html
    assert html.index('class="page-header"><span>دفتري') < html.index('صدر في')


def test_empty_report_retains_table_headers_and_escapes_identity(markup):
    settings = {**deepcopy(DEFAULTS), 'shopName': '<script>دفتر & شركة</script>'}
    assert aggregate([])['currencyCounts'] == {}
    pdf.report(settings, [], aggregate([]))
    html = markup[0]
    assert '<tbody></tbody>' in html
    assert '<script>' not in html
    assert '&lt;script&gt;دفتر &amp; شركة&lt;/script&gt;' in html
    assert html.count('class="kpi"') == 4


def test_statement_totals_signed_amounts_zero_commission_and_metadata(markup):
    records = [row(), row('payment', amount=5)]
    data = statement(records, '2026-11-01', '2026-11-30')
    pdf.client_statement(DEFAULTS, {'name': 'محمد', 'phone': '770000000'}, data,
                         '2026-11-01', '2026-11-30', 'ALL')
    html = markup[0]
    assert '<td>+20 USDT</td>' in html and '<td>−5 USDT</td>' in html
    assert '<td>—</td>' in html
    assert '<tfoot><tr><td colspan="2"></td><td colspan="5">الرصيد الختامي</td>' in html
    assert '<td>15 $</td></tr></tfoot>' in html
    assert ' · الهاتف: 770000000</p>' in html
    assert html.count('class="kpi"') == 4


def test_empty_statement_retains_eight_columns_and_closing_balance(markup):
    data = statement([], '2026-11-01', '2026-11-30', 'SAR')
    pdf.client_statement(DEFAULTS, {'name': '<عميل>', 'phone': ''}, data, '', '', 'SAR')
    html = markup[0]
    assert '<td>—</td><td>لا حركات في هذه الفترة</td>' in html
    assert '<td>0 ر.س</td></tr></tfoot>' in html
    assert 'الهاتف:' not in html
    assert '&lt;عميل&gt;' in html and '<عميل>' not in html


def test_rendering_failure_is_not_swallowed(monkeypatch):
    class BrokenDocument:
        def __init__(self, string):
            pass

        def write_pdf(self):
            raise RuntimeError('PDF renderer unavailable')

    monkeypatch.setattr(pdf, 'HTML', BrokenDocument)
    with pytest.raises(RuntimeError, match='PDF renderer unavailable'):
        pdf.report(DEFAULTS, [], aggregate([]))
