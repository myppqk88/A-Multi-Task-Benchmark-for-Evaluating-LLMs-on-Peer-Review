#!/usr/bin/env python3
"""Run pilot tasks on Claude models through the Claude Code CLI in print mode, with no tools.

Each call gets a neutral system prompt and one user message: the task's input.json as text, then
every page image it references, each preceded by a caption naming its input_field and page so the
model can cite it. The CLI runs in an empty temporary directory with tools, MCP servers and
settings disabled, so the model sees only the task material. Pilot only: the formal run uses the
API directly with fixed parameters. Raw transcripts and parsed answers go to pilot/runs/<model>/.
Usage: python3 scripts/run_pilot_models.py --models opus sonnet haiku [--tasks ...] [--jobs 6]
"""
import argparse
import base64
import json
import re
import subprocess
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INPUTS = ROOT / 'pilot/inputs'
RUNS = ROOT / 'pilot/runs'
SYSTEM = ('You are taking part in a research evaluation of scientific peer-review judgement. Follow the '
          'instruction in the task exactly and use only the material supplied. Reply with one JSON object '
          'that conforms to output_schema and nothing else.')


def images(obj, pointer=''):
    """Yield (input_field, page_label, file) for every image entry in the input."""
    if isinstance(obj, dict):
        f = obj.get('file') or obj.get('path')
        if isinstance(f, str) and f.endswith('.png'):
            yield pointer.rsplit('/', 1)[0], obj.get('page_label', ''), f
            return
        for k, v in obj.items():
            yield from images(v, f'{pointer}/{k}')
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from images(v, f'{pointer}/{i}')


def message(task_id):
    task_dir = INPUTS / task_id
    data = json.loads((task_dir / 'input.json').read_text(encoding='utf-8'))
    content = [{'type': 'text', 'text': 'TASK INPUT (input.json):\n' + json.dumps(data, ensure_ascii=False, indent=1)}]
    for field, label, f in images(data):
        page = re.sub(r'\D', '', label) or label
        content.append({'type': 'text', 'text': f'[page image] input_field={field.lstrip("/")} page={page} file={f}'})
        content.append({'type': 'image', 'source': {'type': 'base64', 'media_type': 'image/png',
                                                     'data': base64.b64encode((task_dir / f).read_bytes()).decode()}})
    return {'type': 'user', 'message': {'role': 'user', 'content': content}}


def parse_answer(text):
    text = text.strip()
    fence = re.search(r'```(?:json)?\s*(\{.*\})\s*```', text, re.S)
    if fence:
        text = fence.group(1)
    start, end = text.find('{'), text.rfind('}')
    try:
        return json.loads(text[start:end + 1]), None
    except (ValueError, json.JSONDecodeError) as exc:
        return None, str(exc)


def run(model, task_id, timeout):
    out_dir = RUNS / model
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / f'{task_id}.json'
    if target.is_file() and json.loads(target.read_text()).get('answer') is not None:
        return task_id, model, 'cached'
    payload = json.dumps(message(task_id), ensure_ascii=False) + '\n'
    cmd = ['claude', '-p', '--model', model, '--input-format', 'stream-json', '--output-format', 'stream-json',
           '--verbose', '--tools', '', '--system-prompt', SYSTEM, '--strict-mcp-config', '--setting-sources', '',
           '--no-session-persistence', '--max-turns', '1']
    for attempt in (1, 2):
        started = time.time()
        with tempfile.TemporaryDirectory() as empty:
            proc = subprocess.run(cmd, input=payload, capture_output=True, text=True, cwd=empty, timeout=timeout)
        events = [json.loads(line) for line in proc.stdout.splitlines() if line.startswith('{')]
        init = next((e for e in events if e.get('type') == 'system' and e.get('subtype') == 'init'), {})
        result = next((e for e in events if e.get('type') == 'result'), {})
        served = sorted({e['message'].get('model') for e in events if e.get('type') == 'assistant' and e.get('message')})
        text = result.get('result', '') or ''
        answer, error = parse_answer(text) if text else (None, proc.stderr[-500:] or 'no result')
        record = {'task_id': task_id, 'model_alias': model, 'model_init': init.get('model'), 'models_served': served,
                  'attempt': attempt, 'seconds': round(time.time() - started, 1), 'is_error': result.get('is_error'),
                  'usage': result.get('usage'), 'stop_reason': result.get('stop_reason'),
                  'raw_text': text, 'answer': answer, 'parse_error': error}
        target.write_text(json.dumps(record, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
        if answer is not None:
            return task_id, model, 'ok'
    return task_id, model, f'failed: {error}'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--models', nargs='+', default=['opus', 'sonnet', 'haiku'])
    parser.add_argument('--tasks', nargs='*')
    parser.add_argument('--jobs', type=int, default=6)
    parser.add_argument('--timeout', type=int, default=1800)
    args = parser.parse_args()
    manifest = json.loads((INPUTS / 'manifest.json').read_text())['items']
    tasks = args.tasks or [m['task_id'] for m in manifest]
    jobs = [(m, t) for t in tasks for m in args.models]
    with ThreadPoolExecutor(args.jobs) as pool:
        for task_id, model, status in pool.map(lambda j: run(j[0], j[1], args.timeout), jobs):
            print(model, task_id, status, flush=True)


if __name__ == '__main__':
    main()
