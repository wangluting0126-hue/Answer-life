#!/usr/bin/env python3
"""离线检查真实风险边界；临时记录不会污染安装包或个人历史。"""
import ast
import copy
import json
from pathlib import Path
import re
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
import answer_book as ab
import score_dialogues as evaluation


class BehaviorChecks(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name)
        self.p = ab.read_json(ab.ROOT / 'examples/career.json')

    def test_examples_and_exports(self):
        for path in sorted((ab.ROOT / 'examples').glob('*.json')):
            paths = ab.render(ab.read_json(path), self.path / (path.stem + '.html'))
            self.assertEqual(len(paths), 3)
            text = Path(paths[0]).read_text()
            self.assertNotIn('{{content}}', text)
            self.assertIn('id="download"', text)
            self.assertTrue(Path(paths[1]).read_text().strip())

    def test_missing_quote_cannot_bypass_bank(self):
        del self.p['quote_id']
        with self.assertRaises(ValueError):
            ab.document(self.p)

    def test_unknown_quote_rejected(self):
        self.p['quote_id'] = 'not-a-quote'
        with self.assertRaises(ValueError):
            ab.document(self.p)

    def test_blocked_marginal_note_rejected(self):
        self.p['quote_id'] = 'apology-30e'
        with self.assertRaisesRegex(ValueError, '不可用'):
            ab.document(self.p)

    def test_truthy_is_not_verified(self):
        q = copy.deepcopy(ab.bank()['lunyu-2-12'])
        q['verified'] = 'true'
        with self.assertRaises(ValueError):
            ab.get_quote(q['id'], {q['id']: q})

    def test_handwritten_original_and_source_rejected(self):
        for key in ('original', 'source_url', 'cite', 'works'):
            p = dict(self.p, **{key: '伪造'})
            with self.assertRaises(ValueError):
                ab.document(p)

    def test_dissent_cannot_bypass_bank(self):
        self.p['dissent_quote_id'] = 'not-a-quote'
        with self.assertRaises(ValueError):
            ab.document(self.p)

    def test_user_html_is_inert(self):
        attack = '<script>alert(1)</script><img src=x onerror=alert(1)>'
        self.p['quote'] = attack
        self.p['title'] = attack
        self.p['gloss'] = attack
        out = self.path / 'escaped.html'
        ab.render(self.p, out)
        text = out.read_text()
        self.assertNotIn(attack, text)
        self.assertIn('&lt;script&gt;', text)

    def test_non_https_source_is_rejected(self):
        q = copy.deepcopy(ab.bank()['lunyu-2-12'])
        q['source_url'] = 'javascript:alert(1)'
        with self.assertRaises(ValueError):
            ab.get_quote(q['id'], {q['id']: q})

    def test_no_silent_overwrite(self):
        out = self.path / 'page.html'
        ab.render(self.p, out)
        before = out.read_text()
        with self.assertRaises(ValueError):
            ab.render(dict(self.p, title='另一个标题'), out)
        self.assertEqual(before, out.read_text())

    def test_paraphrase_without_fake_quote(self):
        self.p.pop('quote_id')
        self.p.update(source_mode='paraphrase', source_work='本页借读',
                      source_note='没有适切原文，以下为本次提出的视角', source_text='先做一次小范围观察。')
        out = self.path / 'paraphrase.html'
        ab.render(self.p, out)
        self.assertIn('书意转述 · 未引原文', out.read_text())

    def test_unknown_status_is_not_nonaction(self):
        for n in range(3):
            ab.record(dict(self.p, date=f'2026-11-0{n+1}'), self.path)
        result = ab.review(self.path, '2026-11-01', '2026-11-30')
        self.assertEqual(result['count'], 3)
        self.assertFalse(result['issues'][0]['needs_experiment_review'])

    def test_repeated_issue_needs_explicit_unchanged(self):
        ids = [ab.record(dict(self.p, date=f'2026-11-0{n+1}'), self.path)['id'] for n in range(3)]
        ab.update(self.path, ids[-1], unchanged='yes')
        result = ab.review(self.path, '2026-11-01', '2026-11-30')
        self.assertTrue(result['issues'][0]['needs_experiment_review'])
        ab.update(self.path, ids[-1], status='done', result='获得三份回复', unchanged='no')
        result = ab.review(self.path, '2026-11-01', '2026-11-30')
        self.assertFalse(result['issues'][0]['needs_experiment_review'])
        self.assertEqual(result['issues'][0]['latest']['action_result'], '获得三份回复')

    def test_same_theme_different_issue_is_not_recurrence(self):
        for n in range(3):
            ab.record(dict(self.p, issue_key=f'issue-{n}', behavior_unchanged=True), self.path)
        result = ab.review(self.path, '2026-11-01', '2026-11-30')
        self.assertEqual(len(result['issues']), 3)
        self.assertFalse(any(x['needs_experiment_review'] for x in result['issues']))

    def test_date_window_excludes_old_and_future_records(self):
        for date in ('2026-10-31', '2026-11-05', '2026-12-01'):
            ab.record(dict(self.p, date=date), self.path)
        result = ab.review(self.path, '2026-11-01', '2026-11-05')
        self.assertEqual(result['count'], 1)
        self.assertEqual(result['coverage'], ['2026-11-05', '2026-11-05'])

    def test_corrupt_record_is_disclosed(self):
        session = ab.record(self.p, self.path)
        (self.path / 'sessions' / 'broken.json').write_text('{bad json')
        result = ab.review(self.path, '2026-11-01', '2026-11-30')
        self.assertEqual(result['count'], 1)
        self.assertEqual(len(result['invalid_records']), 1)

    def test_no_raw_quote_saved_to_history(self):
        session = ab.record(self.p, self.path)
        self.assertNotIn('quote', session)
        self.assertNotIn(self.p['quote'], ab.dump(session))

    def test_record_update_rejects_path(self):
        with self.assertRaises(ValueError):
            ab.update(self.path, '../../elsewhere', status='done')

    def test_record_retry_is_idempotent_after_update(self):
        first = ab.record(self.p, self.path)
        ab.update(self.path, first['id'], status='done', result='已取得回复')
        retry = ab.record(self.p, self.path)
        self.assertEqual(retry['id'], first['id'])
        self.assertEqual(retry['action_status'], 'done')
        self.assertEqual(ab.review(self.path, '2026-11-01', '2026-11-30')['count'], 1)

    def test_assessment_schema_rejects_unsupported_claim_slots(self):
        self.p['assessment'] = {'facts': ['真实事实'], 'certainty': 0.99}
        with self.assertRaises(ValueError):
            ab.document(self.p)

    def test_assessment_is_exported_and_escaped(self):
        self.p['assessment'] = {'facts': ['<img src=x onerror=alert(1)>'],
                                'possibilities': ['待验证'], 'unknowns': [], 'next_check': '先对照一项要求'}
        out = self.path / 'assessment.html'
        ab.render(self.p, out)
        self.assertIn('这一页依据什么', out.read_text())
        self.assertIn('&lt;img', out.read_text())
        self.assertIn('先对照一项要求', out.with_suffix('.md').read_text())

    def test_reminder_timezone_and_uid(self):
        a = ab.reminder(self.p, '2026-11-12', '20:30', 'Asia/Shanghai')
        b = ab.reminder(self.p, '2026-11-12', '20:30', 'Asia/Shanghai')
        self.assertIn('DTSTART:20261112T123000Z', a)
        self.assertIn('BEGIN:VALARM', a)
        self.assertEqual(re.search(r'UID:([^\r]+)', a)[1], re.search(r'UID:([^\r]+)', b)[1])

    def test_reminder_unicode_folding_and_injection(self):
        self.p['action'] = '中文很长' * 60 + '\r\nBEGIN:VEVENT,伪事件;\\尾'
        out = ab.reminder(self.p, '2026-11-12', '20:30', 'Asia/Shanghai')
        self.assertEqual(out.count('\r\nBEGIN:VEVENT\r\n'), 1)
        self.assertTrue(all(len(line.encode('utf-8')) <= 75 for line in out.split('\r\n')))
        unfolded = out.replace('\r\n ', '')
        self.assertIn('\\nBEGIN:VEVENT\\,', unfolded)

    def test_invalid_reminder_inputs(self):
        for day, at, zone in [('2026-11-04', '20:30', 'UTC'), ('2026-11-12', '24:00', 'UTC'),
                              ('2026-11-12', '20:30', 'No/Such_Zone')]:
            with self.assertRaises(ValueError):
                ab.reminder(self.p, day, at, zone)

    def test_nonexistent_dst_time(self):
        with self.assertRaises(ValueError):
            ab.reminder(dict(self.p, date='2026-03-01'), '2026-03-08', '02:30', 'America/New_York')

    def test_bookmark_needs_no_network_or_state_storage(self):
        out = self.path / 'bookmark.html'
        ab.render(self.p, out)
        text = out.read_text()
        self.assertIn('夹一枚书签', text)
        self.assertNotIn('localStorage', text)
        self.assertNotIn('fetch(', text)

    def test_eval_template_cannot_pass_as_results(self):
        spec = evaluation.load(evaluation.CASES)
        with self.assertRaises(ValueError):
            evaluation.summarize(spec, evaluation.template(spec))

    def test_eval_requires_complete_coverage(self):
        spec = evaluation.load(evaluation.CASES)
        with self.assertRaises(ValueError):
            evaluation.summarize(spec, {'cases': []})

    def test_eval_reports_hard_fail_even_with_high_total(self):
        spec = evaluation.load(evaluation.CASES)
        data = evaluation.template(spec)
        for row in data['cases']:
            row.update(response='合成测试回应', notes='仅测试计分器，不是模型评测')
            row['scores'] = {d: 2 for d in spec['dimensions']}
        data['cases'][0]['scores']['source_honesty'] = 0
        result = evaluation.summarize(spec, data)
        self.assertEqual(result['cases_reviewed'], len(spec['cases']))
        self.assertEqual(result['hard_fail_cases'], [data['cases'][0]['id']])

    def test_library_and_theme_routes(self):
        quotes = ab.bank()
        self.assertEqual(len(quotes), 57)
        self.assertEqual(sum(bool(q.get('blocked')) for q in quotes.values()), 1)
        theme_doc = (ab.ROOT / 'references/themes.md').read_text()
        ids = re.findall(r'\b(?:lunyu|daodejing|zhuangzi|mozi|apology|hamlet)-[a-z0-9-]+', theme_doc)
        for key in ids:
            ab.get_quote(key, quotes)
        for theme in ab.THEMES:
            self.assertTrue(any(theme in q['theme'] and not q.get('blocked') for q in quotes.values()))

    def test_python_and_local_links(self):
        for path in (ab.ROOT / 'scripts').glob('*.py'):
            ast.parse(path.read_text(), filename=str(path))
        for path in ab.ROOT.rglob('*.md'):
            for target in re.findall(r'\]\(([^)]+)\)', path.read_text()):
                if not target.startswith(('http:', 'https:', '#')):
                    self.assertTrue((path.parent / target.split('#')[0]).exists(), f'{path}: {target}')


if __name__ == '__main__':
    unittest.main(verbosity=2)
