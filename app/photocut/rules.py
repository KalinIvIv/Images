"""
Shared site rules (rules.json), normally kept in a folder synced for the whole team
(Google Drive for desktop, OneDrive, network drive).

{
  "version": 1,
  "sites": {
    "lg.com": {
      "gallery": "CSS selector of the product gallery",
      "exclude": ["substring of image URLs to skip"],
      "include": ["substring an image URL must contain"],
      "rewrite": [{"find": "regex", "replace": "text"}],
      "minSize": 400,
      "updatedBy": "name", "updatedAt": "ISO time"
    }
  }
}

Sites are keyed by domain without 'www.'. A rule for 'lg.com' also applies to
'www.lg.com' and every localisation path (/za/, /uk/...).
"""

import json
import os
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path

RULE_KEYS = {'gallery', 'exclude', 'include', 'rewrite', 'minSize', 'note'}


def empty():
    return {'version': 1, 'sites': {}}


def normalize_domain(domain):
    domain = domain.lower().strip().strip('.')
    return domain[4:] if domain.startswith('www.') else domain


def load(path):
    if not path:
        return empty()
    try:
        with open(path, encoding='utf-8') as f:
            data = json.load(f)
    except FileNotFoundError:
        return empty()
    if not isinstance(data, dict) or not isinstance(data.get('sites'), dict):
        raise ValueError(f'{path} is not a PhotoCut rules file')
    return data


def match(rules, hostname):
    """Return (domain, rule) for the most specific rule matching hostname."""
    parts = normalize_domain(hostname).split('.')
    for i in range(max(1, len(parts) - 1)):
        domain = '.'.join(parts[i:])
        if domain in rules['sites']:
            return domain, rules['sites'][domain]
    return None, None


def clean_rule(rule):
    out = {k: v for k, v in rule.items() if k in RULE_KEYS and v not in (None, '', [])}
    for key in ('exclude', 'include'):
        if key in out:
            out[key] = sorted({str(s) for s in out[key] if str(s).strip()})
    return out


def save_site(path, domain, rule, user=''):
    """
    Merge one site's rule into the shared file without losing other people's edits:
    re-read, change only this domain, write a temp file, atomic rename, keep a .bak.
    rule=None removes the site.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    domain = normalize_domain(domain)

    for attempt in range(3):
        try:
            data = load(path)
            break
        except (OSError, ValueError):
            # Sync clients sometimes hold the file briefly; retry before giving up.
            if attempt == 2:
                raise
            time.sleep(0.3)

    if rule is None:
        data['sites'].pop(domain, None)
    else:
        entry = clean_rule(rule)
        entry['updatedBy'] = user
        entry['updatedAt'] = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
        data['sites'][domain] = entry
    data['sites'] = dict(sorted(data['sites'].items()))

    if path.exists():
        shutil.copyfile(path, path.with_name(path.name + '.bak'))
    tmp = path.with_name(path.name + '.tmp')
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding='utf-8')
    os.replace(tmp, path)
    return data
