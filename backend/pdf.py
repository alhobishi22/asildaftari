from datetime import date
from html import escape
from pathlib import Path
from weasyprint import HTML

FONTS = Path(__file__).resolve().parents[1] / 'frontend' / 'public' / 'fonts'


def fmt(value, symbol='$'):
    return f'{value:,.2f}'.rstrip('0').rstrip('.') + ' ' + symbol


def symbol(settings, code):
    return next((c['symbol'] for c in settings['currencies'] if c['code'] == code), code)


def table(headers, rows, empty=None, totals=None, statement=False):
    heading = '<thead><tr>' + ''.join(f'<th scope="col">{escape(h)}</th>' for h in headers) + '</tr></thead>'
    body = ''.join('<tr>' + ''.join(f'<td>{escape(str(v))}</td>' for v in row) + '</tr>' for row in rows)
    if not rows and empty:
        body = f'<tr><td colspan="{len(headers)}">{escape(empty)}</td></tr>'
    closing = ''
    if totals:
        if statement:
            closing = f'<tfoot><tr><td colspan="2"></td><td colspan="5">{escape(str(totals[2]))}</td><td>{escape(str(totals[-1]))}</td></tr></tfoot>'
        else:
            closing = '<tfoot><tr>' + ''.join(f'<td>{escape(str(v))}</td>' for v in totals) + '</tr></tfoot>'
    return f'<table class="{"statement" if statement else "report"}">{heading}<tbody>{body}</tbody>{closing}</table>'


def kpis(values):
    return '<div class="kpis">' + ''.join(f'<div class="kpi"><small>{escape(label)}</small><strong style="color:{color}"><bdi dir="ltr">{escape(value)}</bdi></strong></div>' for label, value, color in values) + '</div>'


def render(settings, title, body):
    css = f'''@font-face {{font-family:Plex;src:url("{(FONTS / 'IBMPlexSansArabic-Regular.ttf').as_uri()}")}}
    @font-face {{font-family:Plex;src:url("{(FONTS / 'IBMPlexSansArabic-SemiBold.ttf').as_uri()}");font-weight:700}}
    @page {{
        size:A4;margin:24mm 12mm 20mm;
        @top-center {{content:element(page-header);width:210mm;vertical-align:top;padding-top:6mm}}
        @bottom-center {{content:element(page-footer);width:210mm;vertical-align:bottom;padding-bottom:6mm}}
    }}
    *{{box-sizing:border-box}}
    body{{margin:0;font-family:Plex,sans-serif;font-size:11pt;line-height:1.6;color:#0c5c50;direction:rtl}}
    .page-header{{position:running(page-header);width:210mm;padding:0 12mm 5px;border-bottom:1px solid #d6dce1;direction:ltr;font-size:8pt;line-height:1.5;color:#202925;display:flex;justify-content:space-between;align-items:center}}
    .page-header span{{direction:rtl}}
    .page-footer{{position:running(page-footer);width:210mm;padding:7px 12mm 0;border-top:1px solid #d6dce1;font-size:8pt;line-height:1.5;color:#202925;text-align:center}}
    .page-counter{{position:absolute;right:12mm;direction:ltr}}
    .page-counter::after{{content:"Page " counter(page) " of " counter(pages)}}
    h1{{font-size:22pt;line-height:1.35;margin:0 0 10px;font-weight:700}}
    h2{{font-size:17pt;line-height:1.4;margin:16px 0 8px;font-weight:700;break-after:avoid}}
    p{{margin:0 0 14px}}
    .kpis{{display:table;table-layout:fixed;width:100%;border-spacing:7px 0;margin:18px 0 22px;direction:rtl;break-inside:avoid}}
    .kpi{{display:table-cell;width:25%;padding:12px 10px;background:#f8faf9;border:1px solid #dce5e1;border-radius:8px;text-align:right;vertical-align:top}}
    .kpi small{{display:block;font-size:9pt;line-height:1.6;color:#4b5f59}}
    .kpi strong{{display:block;font-size:18pt;line-height:1.4;font-weight:700;margin-top:5px}}
    table{{width:100%;border-collapse:collapse;font-size:11pt;line-height:1.5;direction:rtl}}
    th{{background:#f6faf8;color:#0c5c50;font-weight:700;border-bottom:1.5px solid #0c5c50}}
    td,th{{padding:7px 5px;text-align:right;vertical-align:top;overflow-wrap:anywhere}}
    tbody td{{border-bottom:1px solid #e1e7e4}}
    tbody tr:nth-child(even){{background:#fafcfb}}
    thead{{display:table-header-group}}
    tfoot{{display:table-row-group;background:#f0f6f3;font-weight:700}}
    tfoot td{{border-top:1.5px solid #0c5c50}}
    tr{{break-inside:avoid}}
    .statement{{font-size:8pt;table-layout:fixed;color:#10201c}}
    .statement th,.statement td{{padding:7px 4px}}
    .statement th:nth-child(1){{width:18%}}
    .statement th:nth-child(2){{width:23%}}
    .statement th:nth-child(3){{width:7%}}
    .statement th:nth-child(4),.statement th:nth-child(8){{width:12%}}
    .statement th:nth-child(5){{width:7%}}
    .statement th:nth-child(6){{width:10%}}
    .statement th:nth-child(7){{width:11%}}
    .report td:nth-child(n+2),.statement td:nth-child(4),.statement td:nth-child(6),.statement td:nth-child(7),.statement td:nth-child(8),.statement tfoot td:last-child{{direction:ltr;unicode-bidi:isolate}}
    aside{{background:#f0f6f7;border-right:3px solid #0c5c50;padding:12px;margin-top:18px;font-size:10pt;color:#315e60;break-inside:avoid}}
    '''
    header = f'<header class="page-header"><span>{escape(settings["shopName"])}</span><span>صدر في <bdi dir="ltr">{date.today().isoformat()}</bdi></span></header>'
    footer = '<footer class="page-footer">دفتري — دفتر العملاء والأرصدة<span class="page-counter"></span></footer>'
    markup = f'<!doctype html><html lang="ar" dir="rtl"><head><meta charset="utf-8"><title>{escape(title)}</title><style>{css}</style></head><body>{header}{footer}<h1>{escape(title)}</h1>{body}</body></html>'
    return HTML(string=markup).write_pdf()


def report(settings, clients, totals):
    title = 'تقرير عام — ' + settings['shopName']
    values = [('إجمالي الديون', fmt(totals['debts']), '#b03428'), ('إجمالي التسديدات', fmt(totals['payments']), '#16804a'), ('الصافي', fmt(totals['usd']), '#10201c'), ('العمولات', fmt(totals['commission']), '#4b5f59')]
    body = f'<p>عدد العمليات المسجّلة: {totals["count"]}</p>' + kpis(values)
    body += '<h2>الأرصدة حسب العملة</h2>' + table(['العملة', 'الصافي', 'عدد العمليات'], [[code, fmt(amount, symbol(settings, code)), totals['currencyCounts'][code]] for code, amount in totals['currencies'].items()])
    ranked = sorted(clients, key=lambda c: abs(totals['byClient'].get(c['id'], {}).get('usd', 0)), reverse=True)
    body += '<h2>أكبر الأرصدة</h2>' + table(['العميل', 'الحالة', 'الرصيد'], [[c['name'], 'عليه' if totals['byClient'][c['id']]['usd'] > 0 else 'له', fmt(abs(totals['byClient'][c['id']]['usd']))] for c in ranked if abs(totals['byClient'].get(c['id'], {}).get('usd', 0)) >= .005][:10])
    return render(settings, title, body)


def client_statement(settings, client, data, start, end, currency):
    unit = '$' if currency == 'ALL' else symbol(settings, currency)
    title = 'كشف حساب — ' + client['name']
    period = 'الفترة: ' + (start or 'من البداية') + ' إلى ' + (end or 'اليوم') + ' · العملة: ' + ('جميع العملات (بالدولار)' if currency == 'ALL' else currency)
    if client.get('phone'):
        period += ' · الهاتف: ' + client['phone']
    body = f'<p>{escape(period)}</p>'
    body += kpis([(label, fmt(data[key], unit), color) for key, label, color in [('opening', 'الرصيد الافتتاحي', '#4b5f59'), ('debts', 'إجمالي الديون', '#b03428'), ('payments', 'إجمالي التسديدات', '#16804a'), ('closing', 'الرصيد الختامي', '#10201c')]])
    rows = []
    for line in data['lines']:
        r = line['record']
        amount = ('+' if r['signedAmount'] > 0 else '−' if r['signedAmount'] < 0 else '') + fmt(abs(r['signedAmount']), r['currency'])
        rows.append([r['date'] + ' · ' + r['time'], r['note'] or ('دين' if r['type'] == 'debt' else 'تسديد'), 'دين' if r['type'] == 'debt' else 'تسديد', amount, r['currency'], fmt(r['commissionAmount'], symbol(settings, r['currency'])) if r['commissionAmount'] else '—', fmt(r['usdEquivalent']), fmt(line['balance'], unit)])
    if not rows:
        rows.append(['—', 'لا حركات في هذه الفترة', '', '', '', '', '', fmt(data['closing'], unit)])
    totals = ['', '', 'الرصيد الختامي', '', '', '', '', fmt(data['closing'], unit)]
    body += table(['التاريخ والوقت', 'البيان', 'النوع', 'المبلغ', 'العملة', 'العمولة', 'المقابل $', 'الرصيد'], rows, totals=totals, statement=True)
    body += '<aside>الأسعار والعمولات مثبّتة عند لحظة تسجيل كل عملية، ولا تتأثر بتغيّر أسعار الصرف لاحقًا.</aside>'
    return render(settings, title, body)
