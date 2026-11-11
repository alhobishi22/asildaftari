from datetime import date
from pathlib import Path

from fpdf import FPDF
from fpdf.enums import TableBordersLayout, TableBorderStyle, TableCellStyle
from fpdf.fonts import FontFace

FONTS = Path(__file__).resolve().parents[1] / 'frontend' / 'public' / 'fonts'
PRIMARY = '#0c5c50'


def fmt(value, symbol='$'):
    return f'{value:,.2f}'.rstrip('0').rstrip('.') + ' ' + symbol


def symbol(settings, code):
    return next((c['symbol'] for c in settings['currencies'] if c['code'] == code), code)


def ltr(value):
    return '\u2066' + str(value) + '\u2069'


class TableRules(TableBordersLayout):
    def __init__(self, closing):
        self.closing = closing

    def cell_style_getter(self, row_idx, col_idx, col_pos, num_heading_rows, num_rows, num_col_idx, num_col_pos):
        rule = TableBorderStyle(thickness=.4, color=(12, 92, 80))
        return TableCellStyle(bottom=rule if row_idx < num_heading_rows else True,
                              top=rule if self.closing and row_idx == num_rows - 1 else False)


class Document(FPDF):
    def __init__(self, settings, title):
        super().__init__(format='A4')
        self.shop = settings['shopName']
        self.add_font('Plex', fname=FONTS / 'IBMPlexSansArabic-Regular.ttf')
        self.add_font('Plex', style='B', fname=FONTS / 'IBMPlexSansArabic-SemiBold.ttf')
        self.set_text_shaping(True)
        self.set_margins(12, 24, 12)
        self.set_auto_page_break(True, margin=20)
        self.alias_nb_pages()
        self.set_title(title)
        self.set_author(self.shop)
        self.add_page()
        self.paragraph(title, size=22, bold=True, height=10)
        self.ln(2)

    def paragraph(self, text, size=11, bold=False, height=6, color=PRIMARY):
        self.set_font('Plex', 'B' if bold else '', size)
        self.set_text_color(color)
        self.set_x(self.l_margin)
        self.multi_cell(self.epw, height, text=str(text), align='R', new_x='LMARGIN', new_y='NEXT', wrapmode='CHAR')

    def header(self):
        self.set_font('Plex', size=8)
        self.set_text_color('#202925')
        self.set_xy(12, 6)
        self.cell(self.epw / 2, 5, self.shop, align='L')
        self.cell(self.epw / 2, 5, 'صدر في ' + ltr(date.today().isoformat()), align='R')
        self.set_draw_color('#d6dce1')
        self.set_line_width(.25)
        self.line(0, 13, self.w, 13)
        self.set_xy(self.l_margin, self.t_margin)

    def footer(self):
        self.set_draw_color('#d6dce1')
        self.set_line_width(.25)
        self.line(0, self.h - 13, self.w, self.h - 13)
        self.set_font('Plex', size=8)
        self.set_text_color('#202925')
        self.set_xy(12, self.h - 12)
        self.cell(self.epw, 6, 'دفتري — دفتر العملاء والأرصدة', align='C')
        self.set_xy(12, self.h - 12)
        self.set_text_shaping(False)
        self.cell(self.epw, 6, f'Page {self.page_no()} of {{nb}}', align='R')
        self.set_text_shaping(True)

    def kpis(self, values):
        if self.will_page_break(33):
            self.add_page()
        self.ln(3)
        y = self.y
        gap = 2
        width = (self.epw - gap * 3) / 4
        for index, (label, value, color) in enumerate(values):
            x = self.w - self.r_margin - width - index * (width + gap)
            self.set_fill_color('#f8faf9')
            self.set_draw_color('#dce5e1')
            self.rect(x, y, width, 24, style='DF', round_corners=True, corner_radius=2)
            self.set_xy(x + 2, y + 2)
            self.set_font('Plex', size=9)
            self.set_text_color('#4b5f59')
            self.cell(width - 4, 6, label, align='R')
            self.set_font('Plex', 'B', 18)
            while self.get_string_width(value) > width - 5 and self.font_size_pt > 8:
                self.set_font_size(self.font_size_pt - 1)
            self.set_xy(x + 2, y + 10)
            self.set_text_color(color)
            self.cell(width - 4, 10, value, align='R')
        self.set_xy(self.l_margin, y + 30)

    def heading(self, text):
        if self.will_page_break(28):
            self.add_page()
        self.ln(3)
        self.paragraph(text, size=17, bold=True, height=8)
        self.ln(2)

    def data_table(self, headers, rows, statement=False, closing=None):
        self.set_font('Plex', size=8 if statement else 11)
        self.set_text_color('#10201c' if statement else PRIMARY)
        self.set_draw_color('#dce5e1')
        self.set_line_width(.2)
        widths = list(reversed([18, 23, 7, 12, 7, 10, 11, 12])) if statement else None
        with self.table(col_widths=widths, text_align='R', line_height=4.2 if statement else 5.8,
                        padding=(2, 1.3), wrapmode='CHAR', borders_layout=TableRules(closing is not None),
                        headings_style=FontFace(emphasis='B', color=PRIMARY, fill_color='#f6faf8'),
                        cell_fill_color='#fafcfb', cell_fill_mode='ROWS', v_align='TOP') as table:
            table.row(list(reversed(headers)))
            for values in rows:
                table.row([str(value) for value in reversed(values)])
            if closing is not None:
                row = table.row(style=FontFace(emphasis='B', fill_color='#f0f6f3'))
                row.cell(closing)
                row.cell('الرصيد الختامي', colspan=5)
                row.cell('', colspan=2)

    def notice(self, text):
        self.ln(5)
        self.set_fill_color('#f0f6f7')
        self.set_font('Plex', size=10)
        self.set_text_color('#315e60')
        self.set_x(self.l_margin)
        if self.will_page_break(24):
            self.add_page()
        top = self.y
        self.multi_cell(self.epw, 6, text, align='R', padding=3, fill=True, new_x='LMARGIN', new_y='NEXT')
        self.set_draw_color(PRIMARY)
        self.set_line_width(.8)
        self.line(self.w - self.r_margin, top, self.w - self.r_margin, self.y)


def report(settings, clients, totals):
    doc = Document(settings, 'تقرير عام — ' + settings['shopName'])
    doc.paragraph(f'عدد العمليات المسجّلة: {totals["count"]}')
    doc.kpis([('إجمالي الديون', fmt(totals['debts']), '#b03428'),
              ('إجمالي التسديدات', fmt(totals['payments']), '#16804a'),
              ('الصافي', fmt(totals['usd']), '#10201c'),
              ('العمولات', fmt(totals['commission']), '#4b5f59')])
    doc.heading('الأرصدة حسب العملة')
    doc.data_table(['العملة', 'الصافي', 'عدد العمليات'],
                   [[code, fmt(amount, symbol(settings, code)), totals['currencyCounts'][code]]
                    for code, amount in totals['currencies'].items()])
    ranked = sorted(clients, key=lambda c: abs(totals['byClient'].get(c['id'], {}).get('usd', 0)), reverse=True)
    doc.heading('أكبر الأرصدة')
    doc.data_table(['العميل', 'الحالة', 'الرصيد'],
                   [[c['name'], 'عليه' if totals['byClient'][c['id']]['usd'] > 0 else 'له',
                     fmt(abs(totals['byClient'][c['id']]['usd']))] for c in ranked
                    if abs(totals['byClient'].get(c['id'], {}).get('usd', 0)) >= .005][:10])
    return bytes(doc.output())


def client_statement(settings, client, data, start, end, currency):
    unit = '$' if currency == 'ALL' else symbol(settings, currency)
    doc = Document(settings, 'كشف حساب — ' + client['name'])
    period = 'الفترة: ' + (ltr(start) if start else 'من البداية') + ' إلى ' + (ltr(end) if end else 'اليوم') + ' · العملة: ' + ('جميع العملات (بالدولار)' if currency == 'ALL' else currency)
    if client.get('phone'):
        period += ' · الهاتف: ' + client['phone']
    doc.paragraph(period)
    doc.kpis([(label, fmt(data[key], unit), color) for key, label, color in [
        ('opening', 'الرصيد الافتتاحي', '#4b5f59'), ('debts', 'إجمالي الديون', '#b03428'),
        ('payments', 'إجمالي التسديدات', '#16804a'), ('closing', 'الرصيد الختامي', '#10201c')]])
    rows = []
    for line in data['lines']:
        r = line['record']
        amount = ('+' if r['signedAmount'] > 0 else '−' if r['signedAmount'] < 0 else '') + fmt(abs(r['signedAmount']), r['currency'])
        rows.append([r['date'] + ' · ' + r['time'], r['note'] or ('دين' if r['type'] == 'debt' else 'تسديد'),
                     'دين' if r['type'] == 'debt' else 'تسديد', amount, r['currency'],
                     fmt(r['commissionAmount'], symbol(settings, r['currency'])) if r['commissionAmount'] else '—',
                     fmt(r['usdEquivalent']), fmt(line['balance'], unit)])
    if not rows:
        rows.append(['—', 'لا حركات في هذه الفترة', '', '', '', '', '', fmt(data['closing'], unit)])
    doc.data_table(['التاريخ والوقت', 'البيان', 'النوع', 'المبلغ', 'العملة', 'العمولة', 'المقابل $', 'الرصيد'],
                   rows, statement=True, closing=fmt(data['closing'], unit))
    doc.notice('الأسعار والعمولات مثبّتة عند لحظة تسجيل كل عملية، ولا تتأثر بتغيّر أسعار الصرف لاحقًا.')
    return bytes(doc.output())
