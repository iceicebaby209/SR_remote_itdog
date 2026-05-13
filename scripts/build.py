#!/usr/bin/env python3
"""Build SR-compatible rule-sets from upstream sources defined in sources.yaml."""
import sys, ipaddress, urllib.request, urllib.error
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / 'dist'
DIST.mkdir(exist_ok=True)

def fetch(url, timeout=30):
    req = urllib.request.Request(url, headers={'User-Agent': 'sr-list-builder/1.0'})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode('utf-8', errors='replace')

def _clean(line):
    s = line.strip()
    if not s or s.startswith(('#', ';', '//')):
        return None
    return s

def convert(content, mode, no_resolve=False):
    seen, out = set(), []
    suffix = ',no-resolve' if no_resolve else ''
    for raw in content.splitlines():
        line = _clean(raw)
        if line is None:
            continue
        if mode == 'passthrough':
            result = line
        elif mode == 'domain_suffix':
            if line.startswith('+.'):
                line = line[2:]
            line = line.lstrip('.')
            if not line or '*' in line:
                continue
            result = f'DOMAIN-SUFFIX,{line}'
        elif mode == 'ip_cidr':
            try:
                ipaddress.ip_network(line, strict=False)
            except ValueError:
                continue
            result = f'IP-CIDR,{line}{suffix}'
        else:
            print(f'  ! unknown mode: {mode}', file=sys.stderr)
            return None
        if result not in seen:
            seen.add(result)
            out.append(result)
    return '\n'.join(out) + '\n'

def main():
    with open(ROOT / 'sources.yaml') as f:
        cfg = yaml.safe_load(f)

    failures = 0
    for src in cfg.get('sources', []):
        name, url, mode = src['name'], src['url'], src['convert']
        nr = src.get('no_resolve', False)
        print(f'>>> {name}')
        try:
            content = fetch(url)
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as e:
            print(f'    FETCH FAILED: {e}', file=sys.stderr)
            failures += 1
            continue
        body = convert(content, mode, nr)
        if body is None:
            failures += 1
            continue
        header = (
            f'# Auto-generated from {url}\n'
            f'# Mode: {mode}{" no-resolve" if nr else ""}\n'
            f'# Do not edit manually. Edit sources.yaml instead.\n'
            f'\n'
        )
        out_path = DIST / f'{name}.list'
        out_path.write_text(header + body, encoding='utf-8')
        print(f'    -> dist/{name}.list ({body.count(chr(10))} rules)')

    if failures:
        print(f'\n{failures} source(s) failed.', file=sys.stderr)
        sys.exit(1)

if __name__ == '__main__':
    main()
