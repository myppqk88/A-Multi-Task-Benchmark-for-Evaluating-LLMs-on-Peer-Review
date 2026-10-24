#!/usr/bin/env python3
"""Build the simplified adjudication workbook from pilot/merge/, plus readable plain-text materials.

Writes pilot/裁决表_盲评版.xlsx (no drafter identity) and pilot/materials_readable/<task_id>.txt.
With --reveal it instead writes pilot/unblinded/裁决表_揭盲版.xlsx (git-ignored), which adds who
wrote X and Y for each task from pilot/blinding_key.json, so the coordinator can reveal tasks one
at a time after they are adjudicated. Tasks are ordered T2 -> T1 -> T3 (short to long).
"""
import argparse
import json
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.worksheet.datavalidation import DataValidation

ROOT = Path(__file__).resolve().parents[1]
MERGE = ROOT / 'pilot/merge'
INPUTS = ROOT / 'pilot/inputs'
READABLE = ROOT / 'pilot/materials_readable'
WHO = {'A': 'Claude', 'B': 'GPT'}
IMP = {'high': '高', 'medium': '中', 'low': '低'}
LABEL = {'sufficient': '充分', 'partially_sufficient': '部分充分', 'insufficient': '不充分',
         'insufficient_evidence': '证据不足', 'acceptable_under_rubric': '可接受',
         'needs_substantive_revision': '需实质修改'}
ORDER = {'T2': 0, 'T1': 1, 'T3': 2}
FONT, BOLD = Font(name='Arial', size=10), Font(name='Arial', size=10, bold=True)
FILL = PatternFill('solid', start_color='FFFF99')
HEAD = PatternFill('solid', start_color='D9E1F2')
EDGE = Side(style='thin', color='BBBBBB')
BORDER = Border(left=EDGE, right=EDGE, top=EDGE, bottom=EDGE)


def section(title, text):
    return f'\n\n==================== {title} ====================\n\n{text.strip()}\n'


def readable(task_id):
    data = json.loads((INPUTS / task_id / 'input.json').read_text(encoding='utf-8'))
    parts = [f'题号：{task_id}\n（这是模型看到的全部文字材料；图表原图见同名题目文件夹中的图片。）']
    if 'input' in data and 'comment_text' in data['input']:
        parts += [section('审稿意见', data['input']['comment_text']), section('作者回应', data['input']['response_text'])]
    elif 'input' in data:
        parts.append(section('稿件正文', data['input']['manuscript_text']))
        for key, sup in data['input'].get('supplements', {}).items():
            parts.append(section(f'附件 {key}', sup.get('text', '')))
    else:
        m = data['materials']
        for rid, text in m['reviews'].items():
            parts.append(section(f'审稿报告 {rid}', text))
        if m.get('editor_decision'):
            parts.append(section('编辑决定信', m['editor_decision']))
        for rid, text in m['responses'].items():
            parts.append(section(f'作者回应 {rid}', text))
        parts.append(section('修改前稿件', m['manuscript_before']['text']))
        parts.append(section('修改后稿件', m['manuscript_after']['text']))
        for key, sup in m.get('supplements', {}).items():
            parts.append(section(f'附件 {key}', sup.get('text', '')))
    READABLE.mkdir(parents=True, exist_ok=True)
    (READABLE / f'{task_id}.txt').write_text(''.join(parts), encoding='utf-8')


def point_text(p):
    mark = '★ ' if p['origin'] == 'card_author' else ('☆ ' if p['status'] == 'disputed' else '')
    return f"{mark}【{IMP[p['importance']]}】{p['judgment']}"


def label_text(label):
    return f"结论：{LABEL[label['primary']]}"


def write_row(ws, row, values, fill_from, bold_cols=()):
    for col, value in enumerate(values, 1):
        cell = ws.cell(row=row, column=col, value=value)
        cell.font = BOLD if col in bold_cols else FONT
        cell.border = BORDER
        cell.alignment = Alignment(wrap_text=True, vertical='top')
        if col >= fill_from:
            cell.fill = FILL


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--reveal', action='store_true')
    args = parser.parse_args()
    key = json.loads((ROOT / 'pilot/blinding_key.json').read_text())['tasks'] if args.reveal else {}
    merged = [json.loads(p.read_text(encoding='utf-8')) for p in MERGE.glob('*_*.json')]
    merged.sort(key=lambda m: (ORDER[m['X']['task']], m['task_id']))

    wb = Workbook()
    guide = wb.active
    guide.title = '说明'
    lines = [
        ('怎么做（只有三步）', True),
        ('1. 打开这道题的材料：pilot/materials_readable/题号.txt', False),
        ('2. 每一行，X 和 Y 是两位起草者对同一个问题的说法。对照材料，在黄色"选择"列选：X对 / Y对 / 都对 / 都不对。', False),
        ('3. 只有选"都不对"时，在"备注"写一句正确说法。每题做完，在该题第一行填用时（分钟）。', False),
        ('', False),
        ('小提示', True),
        ('· 只有一方提出的问题（另一方显示"—"）：问题成立就选那一方"对"，不成立选"都不对"。', False),
        ('· 标 ★ 的是没有审稿人来源、起草者自己发现的问题，请对照原文核实。', False),
        ('· 结论行：选你同意的那一方；都不同意就选"都不对"并在备注写你的结论。', False),
        ('· 题目按从短到长排：先做回应评价（T2），再做原稿评审（T1），最后做修订评审（T3）。', False),
    ]
    for i, (text, bold) in enumerate(lines, 1):
        guide.cell(row=i, column=1, value=text).font = Font(name='Arial', size=11, bold=bold)
    guide.column_dimensions['A'].width = 100

    ws = wb.create_sheet('裁决表')
    heads = ['题号', '材料文件', 'X 的说法', 'Y 的说法', '选择', '备注', '本题用时(分)']
    if args.reveal:
        heads[2:2] = ['X 是', 'Y 是']
    fill_from = heads.index('选择') + 1
    write_row(ws, 1, heads, len(heads) + 1, bold_cols=range(1, len(heads) + 1))
    for col in range(1, len(heads) + 1):
        ws.cell(row=1, column=col).fill = HEAD
    row = 2
    for m in merged:
        task = m['task_id']
        readable(task)
        xs = {p['id']: p for p in m['X']['reference_points']}
        ys = {p['id']: p for p in m['Y']['reference_points']}
        rows = []
        for group in m['suggested_alignment']:
            x_text = '\n'.join(point_text(xs[i]) for i in group['x'].split(';') if i) or '—'
            y_text = '\n'.join(point_text(ys[i]) for i in group['y'].split(';') if i) or '—'
            rows.append((x_text, y_text))
        if m['X']['task'] != 'T1':
            rows.append((label_text(m['X']['label_reference']), label_text(m['Y']['label_reference'])))
        for x_text, y_text in rows:
            values = [task, f'materials_readable/{task}.txt', x_text, y_text, '', '', '']
            if args.reveal:
                values[2:2] = [WHO[key[task]['X']], WHO[key[task]['Y']]]
            write_row(ws, row, values, fill_from)
            row += 1
    widths = [13, 26, 62, 62, 12, 30, 10]
    if args.reveal:
        widths[2:2] = [8, 8]
    for col, width in enumerate(widths, 1):
        ws.column_dimensions[chr(64 + col)].width = width
    ws.freeze_panes = ws.cell(row=2, column=fill_from - 2)
    choice = DataValidation(type='list', formula1='"X对,Y对,都对,都不对"', allow_blank=True)
    ws.add_data_validation(choice)
    col = chr(64 + fill_from)
    choice.add(f'{col}2:{col}{row - 1}')
    wb.active = 0
    out = ROOT / ('pilot/unblinded/裁决表_揭盲版.xlsx' if args.reveal else 'pilot/裁决表_盲评版.xlsx')
    out.parent.mkdir(parents=True, exist_ok=True)
    wb.save(out)
    print(out.relative_to(ROOT), row - 2, 'rows')


if __name__ == '__main__':
    main()
