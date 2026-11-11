from datetime import date
from html import escape
from pathlib import Path
from weasyprint import HTML

FONTS = Path(__file__).resolve().parents[1] / 'frontend' / 'public' / 'fonts'


def fmt(value, symbol='$'):
    return f'{value:,.2f}'.rstrip('0').rstrip('.') + ' ' + symbol


def symbol(settings, code):
    return next((c['symbol'] for c in settings['currencies'] if c['code'] == code), code)


def table(headers, rows, empty='لا أرصدة'):
    return '<table><thead><tr>' + ''.join(f'<th>{escape(h)}</th>' for h in headers) + '</tr></thead><tbody>' + (''.join('<tr>' + ''.join(f'<td>{escape(str(v))}</td>' for v in row) + '</tr>' for row in rows) or f'<tr><td colspan="{len(headers)}">{escape(empty)}</td></tr>') + '</tbody></table>'


def kpis(values):
    return '<div class="kpis">' + ''.join(f'<div><small>{escape(label)}</small><strong style="color:{color}">{escape(value)}</strong></div>' for label, value, color in values) + '</div>'


def render(settings, title, body):
    css = f'''@font-face {{font-family:Plex;src:url("{(FONTS / 'IBMPlexSansArabic-Regular.ttf').as_uri()}")}}
    @font-face {{font-family:Tajawal;src:url("{(FONTS / 'Tajawal-Bold.ttf').as_uri()}");font-weight:700}}
    @page {{size:A4;margin:18mm 12mm;@bottom-center {{content:"دفتري — دفتر العملاء والأرصدة  ·  " counter(page);font-family:Plex;font-size:9px;color:#4b5f59}}}}
    body{{font-family:Plex,sans-serif;color:#10201c;font-size:11px;direction:rtl}}h1,h2,strong{{font-family:Tajawal,Plex}}h1{{font-size:24px;color:#0c5c50}}h2{{font-size:17px;margin-top:22px}}header{{display:flex;justify-content:space-between;border-bottom:2px solid #0c5c50;padding-bottom:12px;color:#4b5f59}}.kpis{{display:flex;gap:8px;margin:20px 0}}.kpis>div{{flex:1;border:1px solid #dce3df;border-radius:8px;padding:12px}}small,strong{{display:block}}strong{{font-size:20px;margin-top:6px}}table{{width:100%;border-collapse:collapse;font-size:10px}}th{{background:#0c5c50;color:white}}td,th{{padding:8px 5px;border:1px solid #dde3df;text-align:right}}tr{{break-inside:avoid}}aside{{background:#f4f1ea;padding:12px;margin-top:18px;border-right:3px solid #ba8428}}'''
    markup = f'<!doctype html><html lang="ar" dir="rtl"><meta charset="utf-8"><style>{css}</style><body><header><b>{escape(settings["shopName"])}</b><span>صدر في {date.today().isoformat()}</span></header><h1>{escape(title)}</h1>{body}</body></html>'
    return HTML(string=markup).write_pdf()


def report(settings, clients, totals):
    title = 'تقرير عام — ' + settings['shopName']
    values = [('إجمالي الديون', fmt(totals['debts']), '#b03428'), ('إجمالي التسديدات', fmt(totals['payments']), '#16804a'), ('الصافي', fmt(totals['usd']), '#10201c'), ('العمولات', fmt(totals['commission']), '#4b5f59')]
    body = f'<p>عدد العمليات المسجّلة: {totals["count"]}</p>' + kpis(values)
    body += '<h2>الأرصدة حسب العملة</h2>' + table(['العملة', 'الصافي'], [[code, fmt(amount, symbol(settings, code))] for code, amount in totals['currencies'].items()])
    ranked = sorted(clients, key=lambda c: abs(totals['byClient'].get(c['id'], {}).get('usd', 0)), reverse=True)
    body += '<h2>أكبر الأرصدة</h2>' + table(['العميل', 'الحالة', 'الرصيد'], [[c['name'], 'عليه' if totals['byClient'][c['id']]['usd'] > 0 else 'له', fmt(abs(totals['byClient'][c['id']]['usd']))] for c in ranked if abs(totals['byClient'].get(c['id'], {}).get('usd', 0)) >= .005][:10], 'لا أرصدة مفتوحة')
    return render(settings, title, body)


def client_statement(settings, client, data, start, end, currency):
    unit = '$' if currency == 'ALL' else symbol(settings, currency)
    title = 'كشف حساب — ' + client['name']
    body = f'<p>{escape("الفترة: " + (start or "من البداية") + " إلى " + (end or "اليوم") + " · العملة: " + ("جميع العملات (بالدولار)" if currency == "ALL" else currency))}</p>'
    if client.get('phone'):
        body += f'<p>الهاتف: {escape(client["phone"])}</p>'
    body += kpis([(label, fmt(data[key], unit), color) for key, label, color in [('opening', 'الرصيد الافتتاحي', '#4b5f59'), ('debts', 'إجمالي الديون', '#b03428'), ('payments', 'إجمالي التسديدات', '#16804a'), ('closing', 'الرصيد الختامي', '#10201c')]])
    rows = []
    for line in data['lines']:
        r = line['record']
        rows.append([r['date'] + ' · ' + r['time'], r['note'] or ('دين' if r['type'] == 'debt' else 'تسديد'), 'دين' if r['type'] == 'debt' else 'تسديد', fmt(r['signedAmount'], symbol(settings, r['currency'])), r['currency'], fmt(r['commissionAmount'], symbol(settings, r['currency'])), fmt(r['usdEquivalent']), fmt(line['balance'], unit)])
    body += table(['التاريخ والوقت', 'البيان', 'النوع', 'المبلغ', 'العملة', 'العمولة', 'المقابل $', 'الرصيد'], rows, 'لا حركات في هذه الفترة')
    body += f'<p><b>الرصيد الختامي: {escape(fmt(data["closing"], unit))}</b></p><aside>الأسعار والعمولات مثبّتة عند لحظة تسجيل كل عملية، ولا تتأثر بتغيّر أسعار الصرف لاحقًا.</aside>'
    return render(settings, title, body)
