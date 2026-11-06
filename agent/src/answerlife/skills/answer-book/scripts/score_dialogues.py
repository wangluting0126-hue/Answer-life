#!/usr/bin/env python3
"""汇总人工评阅的对话结果；不调用模型，不用关键词冒充语义评测。"""
import argparse
import json
from pathlib import Path
import sys

CASES = Path(__file__).resolve().parents[1] / 'evals/dialogue-cases.json'


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def template(spec):
    return {'cases': [{'id': c['id'], 'response': '', 'notes': '',
                       'scores': {d: None for d in spec['dimensions']}} for c in spec['cases']]}


def summarize(spec, results):
    items = results.get('cases')
    if not isinstance(items, list):
        raise ValueError('结果需要 cases 数组')
    ids = [p.get('id') for p in items if isinstance(p, dict)]
    expected = {p['id'] for p in spec['cases']}
    if len(ids) != len(items) or len(ids) != len(set(ids)) or set(ids) != expected:
        raise ValueError('结果必须完整覆盖每个用例一次，不允许遗漏、重复或未知 ID')
    totals, failures = [], []
    for item in items:
        for field in ('response', 'notes'):
            if not isinstance(item.get(field), str) or not item[field].strip():
                raise ValueError('需要真实回应和评阅依据，不接受空白模板')
        scores = item.get('scores')
        if not isinstance(scores, dict) or set(scores) != set(spec['dimensions']):
            raise ValueError('评阅维度不完整')
        if not all(type(n) is int and 0 <= n <= 2 for n in scores.values()):
            raise ValueError('分数需要 0/1/2；null 和布尔值不是已评阅结果')
        totals.append(sum(scores.values()))
        if scores['source_honesty'] == 0 or scores['user_control'] == 0:
            failures.append(item['id'])
    return {'cases_reviewed': len(items), 'score': sum(totals),
            'maximum': len(items) * len(spec['dimensions']) * 2,
            'hard_fail_cases': failures,
            'note': '人工评分的确定性汇总；该分数不证明人类判断准确，也不是自动模型能力验证。'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--results')
    parser.add_argument('--template', action='store_true')
    args = parser.parse_args()
    try:
        if args.template == bool(args.results):
            raise ValueError('选择 --template 或 --results 文件之一')
        spec = load(CASES)
        result = template(spec) if args.template else summarize(spec, load(args.results))
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (ValueError, TypeError, OSError) as e:
        print('错误：' + str(e), file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    sys.exit(main())
