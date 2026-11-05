#!/usr/bin/env python3
"""答案之书 1.0：纯标准库。文案由对话生成；脚本负责引文、渲染与本地记录。"""
import argparse
import base64
import collections
import datetime as dt
import html
import json
from pathlib import Path
import re
import sys
import uuid
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
THEMES = ('选择与后悔', '恐惧与焦虑', '关系与冲突', '金钱与安全',
          '意义与虚无', '自我与身份', '时间与消耗', '失败与脆弱')
STATUSES = ('unknown', 'planned', 'done', 'skipped')
FIELDS = set(('date no mode theme issue_key quote title origin gloss context_note '
              'source_mode quote_id source_work source_note source_text dissent '
              'dissent_quote_id dissent_work criterion action question action_status '
              'action_result behavior_unchanged').split())
REQUIRED = ('date', 'theme', 'issue_key', 'quote', 'title', 'origin', 'gloss',
            'context_note', 'source_mode', 'dissent', 'criterion', 'action', 'question')


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def dump(value):
    return json.dumps(value, ensure_ascii=False, indent=2) + '\n'


def valid_date(value):
    if not isinstance(value, str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
        raise ValueError('日期需要 YYYY-MM-DD')
    return dt.date.fromisoformat(value)


def text_field(data, key):
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f'{key} 需要非空纯文本')
    if len(value) > 20000:
        raise ValueError(f'{key} 过长')
    return value


def bank():
    result = {}
    for n, line in enumerate((ROOT / 'quotes/classics.jsonl').read_text(encoding='utf-8').splitlines(), 1):
        if not line.strip():
            continue
        item = json.loads(line)
        key = item['id']
        if key in result:
            raise ValueError(f'原文库重复 ID：{key}，第 {n} 行')
        result[key] = item
    return result


def get_quote(key, quotes):
    if not isinstance(key, str) or key not in quotes:
        raise ValueError(f'原文 ID 不存在：{key!r}')
    q = quotes[key]
    if q.get('verified') is not True or q.get('blocked', False):
        raise ValueError(f'原文不可用：{key}；{q.get("block_reason", "尚未核验")}')
    url = urlsplit(q.get('source_url', ''))
    if url.scheme != 'https' or not url.hostname or url.username or url.password:
        raise ValueError(f'原文来源链接无效：{key}')
    text_field(q, 'original')
    return q


def normalize(data, quotes):
    if not isinstance(data, dict):
        raise ValueError('页面需要 JSON 对象')
    extra = set(data) - FIELDS
    if extra:
        raise ValueError('不支持的字段（不可手写原文或出处）：' + ', '.join(sorted(extra)))
    p = dict(data)
    for key in REQUIRED:
        text_field(p, key)
    valid_date(p['date'])
    if p['theme'] not in THEMES:
        raise ValueError('theme 必须为八主题之一')
    if not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', p['issue_key']) or len(p['issue_key']) > 100:
        raise ValueError('issue_key 使用小写英文、数字和连字符，最多 100 字符')
    p.setdefault('no', '0001')
    p.setdefault('mode', 'dialogue')
    p.setdefault('action_status', 'unknown')
    p.setdefault('action_result', '')
    p.setdefault('behavior_unchanged', None)
    for key in ('no', 'mode', 'action_status'):
        text_field(p, key)
    if p['mode'] not in ('quick', 'dialogue', 'dossier', 'review'):
        raise ValueError('mode 需要 quick/dialogue/dossier/review')
    if p['action_status'] not in STATUSES:
        raise ValueError('无效 action_status')
    if p['behavior_unchanged'] is not None and type(p['behavior_unchanged']) is not bool:
        raise ValueError('behavior_unchanged 需要 true/false/null')
    if not isinstance(p['action_result'], str):
        raise ValueError('action_result 需要文本')
    if p['source_mode'] == 'bank':
        p['_source'] = get_quote(p.get('quote_id'), quotes)
        if any(k in p for k in ('source_work', 'source_note', 'source_text')):
            raise ValueError('bank 模式不能手填转述来源')
    elif p['source_mode'] == 'paraphrase':
        if 'quote_id' in p:
            raise ValueError('paraphrase 模式不能带 quote_id')
        for key in ('source_work', 'source_note', 'source_text'):
            text_field(p, key)
    else:
        raise ValueError('source_mode 需要 bank/paraphrase')
    if 'dissent_quote_id' in p:
        p['_dissent_source'] = get_quote(p['dissent_quote_id'], quotes)
        if p.get('_source', {}).get('work') == p['_dissent_source']['work']:
            raise ValueError('异议书应与主书不同')
        if 'dissent_work' in p:
            raise ValueError('第二条库引文不能手填书名')
    else:
        text_field(p, 'dissent_work')
    return p


def document(data):
    quotes = bank()
    if isinstance(data, dict) and 'pages' in data:
        if set(data) != {'chapter_title', 'pages'}:
            raise ValueError('卷宗外层只支持 chapter_title 和 pages')
        title = text_field(data, 'chapter_title')
        if not isinstance(data['pages'], list) or not 2 <= len(data['pages']) <= 3:
            raise ValueError('卷宗需要 2–3 页')
        return title, [normalize(p, quotes) for p in data['pages']]
    p = normalize(data, quotes)
    return p['title'], [p]


def esc(value):
    return html.escape(str(value), quote=True)


def paragraphs(value):
    return ''.join('<p>' + esc(s).replace('\n', '<br>') + '</p>'
                   for s in re.split(r'\n\s*\n', value.strip()))


def quote_html(q):
    original = q['original']
    short = len(original) <= 40
    cite = q.get('cite') or f'《{q["work"]}》{q.get("ref", "")}'
    status = '本版复核' if q.get('checked_in_release') else '随包核验记录'
    speaker = q.get('speaker')
    speaker_note = f'<span class="source-note">文本说话者：{esc(speaker)}</span>' if speaker else ''
    return (f'<details class="original"{" open" if short else ""}><summary>读原文 · {esc(cite)}</summary>'
            f'<div class="original-inner"><blockquote lang="{esc(q.get("language", "zh"))}">{esc(original)}</blockquote>'
            f'<a href="{esc(q["source_url"])}" target="_blank" rel="noopener noreferrer">'
            f'{esc(cite)} · 查看出处 ↗</a><span class="source-note">公版文本 · {status}</span>'
            f'{speaker_note}</div></details>')


def page_html(p, index):
    source = quote_html(p['_source']) if '_source' in p else (
        '<aside class="paraphrase"><span class="label">书意转述 · 未引原文</span>'
        f'<p>{esc(p["source_text"])}</p><span class="source-note">{esc(p["source_work"])} · '
        f'{esc(p["source_note"])}</span></aside>')
    if '_dissent_source' in p:
        other = quote_html(p['_dissent_source'])
        dissent_label = '另一本书，照向另一面'
    else:
        other = f'<p class="source-note">{esc(p["dissent_work"])}'
        other += ' · 书意转述，未引原文</p>' if p['dissent_work'] != '本页的另一个可能' else ' · 本次提出的反例</p>'
        dissent_label = '另一面，也值得读'
    return f'''<article class="reading-page" id="page-{index}">
<header class="masthead"><div>答案之书<span>THE ANSWER BOOK</span></div>
<div class="meta">Nº {esc(p['no'])}<br><time datetime="{p['date']}">{p['date'].replace('-', '.')}</time></div></header>
<section class="hero"><p class="eyebrow">一页，留给此刻的你</p><h1>{esc(p['title']).replace(chr(10), '<br>')}</h1>
<p class="hero-meta">{esc(p['theme'])} <span aria-hidden="true">/</span> {esc({'quick':'快速翻页','dialogue':'一起读','dossier':'这一章','review':'回看'}[p['mode']])}</p></section>
<blockquote class="your-words">{esc(p['quote'])}<cite>你说</cite></blockquote>
<section class="section"><h2 class="label">那句话，从这里来</h2>{paragraphs(p['origin'])}</section>
<section class="section prose">{paragraphs(p['gloss'])}<p class="context-note">{esc(p['context_note'])}</p></section>
{source}<div class="divider" aria-hidden="true"></div>
<section class="section dissent"><h2 class="label">{dissent_label}</h2>{paragraphs(p['dissent'])}{other}</section>
<section class="section criterion"><h2 class="label">给这次选择，一条判据</h2>{paragraphs(p['criterion'])}</section>
<section class="experiment"><h2 class="label">七天，只试这一件</h2>{paragraphs(p['action'])}
<p class="experiment-note">这是一次取样。做完再看，不用现在决定全部。</p></section>
<section class="question"><p class="label">留给你</p>{paragraphs(p['question'])}</section>
<footer class="page-footer"><span>一页书，一次借读。</span><span>判据与实验为本次提出 · {p['date']}</span></footer>
</article>'''


def quote_md(q):
    cite = q.get('cite') or f'《{q["work"]}》{q.get("ref", "")}'
    return (q['original'] + '\n\n' + cite + '\n' + q['source_url'] + '\n'
            + ('本版复核' if q.get('checked_in_release') else '随包核验记录'))


def markdown(title, pages):
    result = [title]
    for p in pages:
        result.extend(['\n' + '─' * 24, f'答案之书 · {p["date"]} · Nº {p["no"]}', p['quote'],
                       '这一页叫：' + p['title'], p['origin'], p['gloss'], p['context_note']])
        result.append(quote_md(p['_source']) if '_source' in p else
                      f'书意转述 · {p["source_work"]}\n{p["source_text"]}\n{p["source_note"]}（未引原文）')
        result.extend(['另一面，也值得读\n' + p['dissent'],
                       quote_md(p['_dissent_source']) if '_dissent_source' in p else p['dissent_work'] + '（未引原文）',
                       '给这次选择，一条判据\n' + p['criterion'], '七天，只试这一件\n' + p['action'],
                       '留给你\n' + p['question'], '判据与实验为本次提出。'])
    return '\n\n'.join(result) + '\n'


def write_new(path, content, force=False):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w' if force else 'x', encoding='utf-8') as f:
        f.write(content)


def render(data, out, force=False):
    title, pages = document(data)
    md = markdown(title, pages)
    nav = ''
    if len(pages) > 1:
        nav = '<nav class="chapter-nav" aria-label="本章目录"><span>' + esc(title) + '</span>'
        nav += ''.join(f'<a href="#page-{i}">{i:02d} · {esc(p["title"])}</a>' for i, p in enumerate(pages, 1)) + '</nav>'
    payload = {'title': esc(title), 'navigation': nav,
               'content': ''.join(page_html(p, i) for i, p in enumerate(pages, 1)),
               'markdown_b64': base64.b64encode(md.encode()).decode()}
    template = (ROOT / 'templates/card.html').read_text(encoding='utf-8')
    output = re.sub(r'\{\{([a-z_0-9]+)\}\}', lambda m: payload[m[1]], template)
    if re.search(r'\{\{(?:title|navigation|content|markdown_b64)\}\}', output):
        raise ValueError('模板占位符未替换')
    out = Path(out)
    if out.suffix.lower() != '.html':
        raise ValueError('--out 应为 .html 文件')
    files = {out: output, out.with_suffix('.md'): md,
             out.with_suffix('.json'): dump({'schema_version': '1.0', 'title': title, 'pages': pages})}
    if not force:
        exists = [str(p) for p in files if p.exists()]
        if exists:
            raise ValueError('已有文件，未覆盖：' + ', '.join(exists))
    for path, value in files.items():
        write_new(path, value, force)
    return [str(p.resolve()) for p in files]


def record(data, home):
    p = normalize(data, bank())
    session = {k: p[k] for k in ('date', 'theme', 'issue_key', 'title', 'action',
                                  'action_status', 'action_result', 'behavior_unchanged')}
    session['id'] = 'AB-' + uuid.uuid4().hex
    session['schema_version'] = '1.0'
    session['created_at'] = dt.datetime.now(dt.timezone.utc).isoformat()
    session['quote_ids'] = [p[k] for k in ('quote_id', 'dissent_quote_id') if k in p]
    write_new(Path(home) / 'sessions' / (session['id'] + '.json'), dump(session))
    return session


def session_path(home, key):
    if not re.fullmatch(r'AB-[0-9a-f]{32}', key):
        raise ValueError('无效 session ID')
    return Path(home) / 'sessions' / (key + '.json')


def update(home, key, status=None, result=None, unchanged=None):
    path = session_path(home, key)
    if path.is_symlink():
        raise ValueError('不更新符号链接记录')
    p = read_json(path)
    if p['id'] != key:
        raise ValueError('记录 ID 不匹配')
    if status is not None:
        if status not in STATUSES:
            raise ValueError('无效动作状态')
        p['action_status'] = status
    if result is not None:
        p['action_result'] = result
    if unchanged is not None:
        p['behavior_unchanged'] = {'yes': True, 'no': False, 'unknown': None}[unchanged]
    p['updated_at'] = dt.datetime.now(dt.timezone.utc).isoformat()
    temp = path.with_suffix('.tmp')
    write_new(temp, dump(p), force=True)
    temp.replace(path)
    return p


def review(home, start, end):
    start_date, end_date = valid_date(start), valid_date(end)
    if start_date > end_date:
        raise ValueError('开始日期晚于结束日期')
    records, invalid = [], []
    for path in sorted((Path(home) / 'sessions').glob('*.json')):
        try:
            if path.is_symlink():
                raise ValueError('跳过符号链接')
            p = read_json(path)
            valid_date(p['date'])
            if session_path(home, p['id']).name != path.name:
                raise ValueError('ID 与文件名不一致')
            if p['theme'] not in THEMES or p['action_status'] not in STATUSES:
                raise ValueError('主题或动作状态无效')
            for field in ('issue_key', 'title', 'action'):
                text_field(p, field)
            if p.get('behavior_unchanged') is not None and type(p['behavior_unchanged']) is not bool:
                raise ValueError('行为状态无效')
            if start <= p['date'] <= end:
                records.append(p)
        except (ValueError, KeyError, TypeError, OSError) as e:
            invalid.append({'file': path.name, 'reason': str(e)})
    records.sort(key=lambda p: (p['date'], p.get('created_at', ''), p['id']))
    groups = collections.defaultdict(list)
    for p in records:
        groups[p['issue_key']].append(p)
    issues = []
    for key, items in groups.items():
        latest = items[-1]
        issues.append({'issue_key': key, 'count': len(items), 'latest': latest,
                       'needs_experiment_review': len(items) >= 3 and latest.get('behavior_unchanged') is True})
    return {'start': start, 'end': end, 'count': len(records),
            'coverage': [records[0]['date'], records[-1]['date']] if records else [],
            'themes': dict(collections.Counter(p['theme'] for p in records)),
            'issues': sorted(issues, key=lambda p: (-p['count'], p['issue_key'])),
            'invalid_records': invalid, 'records': records,
            'scope_note': '只反映指定目录、指定时间窗内已保存的记录，不代表全部生活或全部聊天。'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='cmd', required=True)
    q = sub.add_parser('quotes', help='查可用原文；不会自动判断具体人生选择')
    q.add_argument('--theme', choices=THEMES)
    q.add_argument('--query', default='')
    r = sub.add_parser('render', help='生成 HTML、Markdown、来源快照')
    r.add_argument('--data', required=True)
    r.add_argument('--out', required=True)
    r.add_argument('--force', action='store_true')
    s = sub.add_parser('record', help='获授权后保存最少摘要')
    s.add_argument('--data', required=True)
    s.add_argument('--home', required=True)
    u = sub.add_parser('update', help='仅按用户回报更新实验')
    u.add_argument('--home', required=True)
    u.add_argument('--id', required=True)
    u.add_argument('--status', choices=STATUSES)
    u.add_argument('--result')
    u.add_argument('--unchanged', choices=('yes', 'no', 'unknown'))
    v = sub.add_parser('review', help='统计指定时间窗的真实记录')
    v.add_argument('--home', required=True)
    v.add_argument('--start', required=True)
    v.add_argument('--end', required=True)
    v.add_argument('--out')
    args = parser.parse_args()
    try:
        if args.cmd == 'quotes':
            result = [p for p in bank().values() if p.get('verified') is True and not p.get('blocked')
                      and (not args.theme or args.theme in p.get('theme', []))
                      and args.query.lower() in json.dumps(p, ensure_ascii=False).lower()]
        elif args.cmd == 'render':
            result = {'files': render(read_json(args.data), args.out, args.force)}
        elif args.cmd == 'record':
            result = record(read_json(args.data), args.home)
        elif args.cmd == 'update':
            if args.status is None and args.result is None and args.unchanged is None:
                raise ValueError('至少提供一个需要更新的字段')
            result = update(args.home, args.id, args.status, args.result, args.unchanged)
        else:
            result = review(args.home, args.start, args.end)
            if args.out:
                write_new(args.out, dump(result))
        print(dump(result), end='')
    except (ValueError, KeyError, TypeError, OSError) as e:
        print('错误：' + str(e), file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    sys.exit(main())
