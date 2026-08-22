#!/usr/bin/env python3
"""Fetch a score from the bundled corpus or a verified online source and parse it.

Every scheme below was fetched and parsed successfully on music21 10.5.0.

    python fetch_score.py bach/bwv66.6                       # bundled corpus (offline)
    python fetch_score.py corpus:beethoven/opus18no1 --movement 2
    python fetch_score.py humdrum:craigsapp/bach-370-chorales/kern/chor001.krn
    python fetch_score.py humdrum:ccarh/essen-folksong-collection@main/europa/deutschl/altdeu1/deut3773.krn
    python fetch_score.py kernscores:osu/classical/bach/inventions/inven01.krn
    python fetch_score.py session:182                        # thesession.org Irish tune
    python fetch_score.py jrp:Jos2721                        # Josquin Research Project
    python fetch_score.py mfiles:mozart-symphony40-1         # free classical MIDI
    python fetch_score.py mutopia:BachJS/BWV772/bach-invention-01/bach-invention-01.mid
    python fetch_score.py https://any.host/whatever.mxl      # any parseable URL
    python fetch_score.py --search "composer=bach numberOfParts=4"   # offline corpus search

    --out out.mxl    write the parsed score back out (format from extension)
    --json           machine-readable summary
    --raw            print the fetched bytes to stdout instead of parsing
    --no-key         skip key analysis (fast; analysis dominates runtime on big scores)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import sys
import tempfile
import urllib.parse
import urllib.request

from music21 import converter, corpus, stream

UA = 'Mozilla/5.0 (compatible; music21-fetch_score/1.0)'
CACHE = pathlib.Path(os.environ.get('M21_FETCH_CACHE',
                                    pathlib.Path(tempfile.gettempdir()) / 'm21fetch'))

# scheme -> (description, example)
SCHEMES = {
    'corpus': ('bundled music21 corpus, no network', 'corpus:bach/bwv66.6'),
    'humdrum': ('raw file from any GitHub repo, @branch optional (default master)',
                'humdrum:craigsapp/joplin/kern/maple.krn'),
    'kernscores': ('kernscores.stanford.edu ksdata CGI (kern.humdrum.org mirror)',
                   'kernscores:osu/classical/bach/inventions/inven01.krn'),
    'session': ('thesession.org tune JSON -> ABC; append /N to pick setting N',
                'session:182/2'),
    'jrp': ('Josquin Research Project Humdrum by JRP id', 'jrp:Jos2721'),
    'mfiles': ('mfiles.co.uk free classical MIDI by slug', 'mfiles:mozart-symphony40-1'),
    'mutopia': ('mutopiaproject.org /ftp path', 'mutopia:BachJS/BWV772/x/x.mid'),
    'url': ('any http(s) URL music21 can parse', 'url:https://host/file.krn'),
}

# thesession.org key names -> ABC K: field
SESSION_KEYS = {
    'major': '', 'minor': 'min', 'dorian': 'dor', 'mixolydian': 'mix',
}
# thesession.org tune type -> (M:, L:)
SESSION_METERS = {
    'reel': ('4/4', '1/8'), 'jig': ('6/8', '1/8'), 'slip jig': ('9/8', '1/8'),
    'hornpipe': ('4/4', '1/8'), 'polka': ('2/4', '1/8'), 'slide': ('12/8', '1/8'),
    'waltz': ('3/4', '1/8'), 'barndance': ('4/4', '1/8'), 'strathspey': ('4/4', '1/8'),
    'three-two': ('3/2', '1/8'), 'mazurka': ('3/4', '1/8'), 'march': ('4/4', '1/8'),
}


# ---------------------------------------------------------------- transport


def http_get(url: str, *, cache: bool = True) -> bytes:
    """GET with a browser UA, cached on disk by URL hash. Raises urllib errors."""
    key = hashlib.sha1(url.encode()).hexdigest()[:16]
    blob = CACHE / key
    if cache and blob.exists():
        return blob.read_bytes()
    req = urllib.request.Request(url, headers={'User-Agent': UA})
    with urllib.request.urlopen(req, timeout=90) as fh:
        data = fh.read()
    if cache:
        CACHE.mkdir(parents=True, exist_ok=True)
        blob.write_bytes(data)
    return data


def parse_bytes(data: bytes, suffix: str) -> stream.Score:
    """converter.parse needs a real extension for binary formats (.mxl, .mid)."""
    tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
    tmp.write(data)
    tmp.close()
    try:
        return converter.parse(tmp.name)
    finally:
        os.unlink(tmp.name)


# ---------------------------------------------------------------- resolvers
# Each returns (score, provenance_url).


def from_corpus(spec: str, movement: int | None, number: int | None):
    kwargs = {}
    if movement is not None:
        kwargs['movementNumber'] = movement
    if number is not None:
        kwargs['number'] = number
    return corpus.parse(spec, **kwargs), f'corpus:{spec}'


def from_github(spec: str):
    """owner/repo[@branch]/path/to/file.krn  ->  raw.githubusercontent.com"""
    repo_part, _, path = spec.partition('/')[0], None, None
    owner, rest = spec.split('/', 1)
    repo, _, path = rest.partition('/')
    branch = 'master'
    if '@' in repo:
        repo, branch = repo.split('@', 1)
    if not path:
        raise ValueError('humdrum: needs owner/repo[@branch]/path/to/file')
    url = (f'https://raw.githubusercontent.com/{owner}/{repo}/{branch}/'
           + urllib.parse.quote(path))
    try:
        data = http_get(url)
    except urllib.error.HTTPError as exc:               # default-branch fallback
        if exc.code != 404 or '@' in spec:
            raise
        url = url.replace(f'/{branch}/', '/main/', 1)
        data = http_get(url)
    return parse_bytes(data, pathlib.PurePosixPath(path).suffix or '.krn'), url


def from_kernscores(spec: str):
    """dir/path/file.krn -> the ksdata CGI on the Stanford mirror."""
    p = pathlib.PurePosixPath(spec)
    url = ('http://kernscores.stanford.edu/cgi-bin/ksdata'
           f'?l={p.parent}&file={p.name}&f=kern')
    text = http_get(url).decode('utf-8', 'replace')
    if not text.lstrip().startswith(('**', '!!')):
        raise ValueError(f'kernscores returned non-Humdrum ({len(text)}B): {text[:80]!r}')
    return converter.parse(text, format='humdrum'), url


def from_session(spec: str):
    """thesession.org/tunes/<id>[/<setting index>] -> ABC with a synthesised header."""
    tune_id, _, which = spec.partition('/')
    idx = int(which) if which else 0
    url = f'https://thesession.org/tunes/{int(tune_id)}?format=json'
    meta = json.loads(http_get(url))
    setting = meta['settings'][idx]
    raw_key = setting['key']                            # e.g. 'Dmajor', 'Edorian'
    for mode, abbr in SESSION_KEYS.items():
        if raw_key.endswith(mode):
            abc_key = raw_key[: -len(mode)] + abbr
            break
    else:
        abc_key = raw_key
    metre, unit = SESSION_METERS.get(meta.get('type', ''), ('4/4', '1/8'))
    body = setting['abc'].replace('!', '\n')            # site uses ! as a line break
    abc = (f"X:1\nT:{meta['name']}\nR:{meta.get('type','')}\n"
           f'M:{metre}\nL:{unit}\nK:{abc_key}\n{body}\n')
    return converter.parse(abc, format='abc'), f"{url} (setting {setting['id']})"


def from_jrp(spec: str):
    url = f'https://josquin.stanford.edu/data?a=humdrum&f={urllib.parse.quote(spec)}'
    text = http_get(url).decode('utf-8', 'replace')
    return converter.parse(text, format='humdrum'), url


def from_mfiles(spec: str):
    slug = spec[:-4] if spec.endswith('.mid') else spec
    url = f'https://www.mfiles.co.uk/downloads/{slug}.mid'
    return parse_bytes(http_get(url), '.mid'), url


def from_mutopia(spec: str):
    url = f"https://www.mutopiaproject.org/ftp/{spec.lstrip('/')}"
    return parse_bytes(http_get(url), pathlib.PurePosixPath(spec).suffix or '.mid'), url


def from_url(url: str):
    suffix = pathlib.PurePosixPath(urllib.parse.urlparse(url).path).suffix
    return parse_bytes(http_get(url), suffix or '.xml'), url


def resolve_url(source: str) -> str:
    """The URL a source would be fetched from -- for --raw. Errors on corpus:."""
    scheme, sep, rest = source.partition(':')
    if not sep or scheme not in SCHEMES:
        if source.startswith(('http://', 'https://')):
            return source
        raise ValueError(f'--raw needs a URL-backed source, not {source!r}')
    if scheme == 'corpus':
        raise ValueError('--raw is meaningless for corpus: (the file is already local)')
    if scheme == 'humdrum':
        owner, rest2 = rest.split('/', 1)
        repo, _, path = rest2.partition('/')
        branch = 'master'
        if '@' in repo:
            repo, branch = repo.split('@', 1)
        return (f'https://raw.githubusercontent.com/{owner}/{repo}/{branch}/'
                + urllib.parse.quote(path))
    if scheme == 'kernscores':
        p = pathlib.PurePosixPath(rest)
        return ('http://kernscores.stanford.edu/cgi-bin/ksdata'
                f'?l={p.parent}&file={p.name}&f=kern')
    if scheme == 'session':
        return f"https://thesession.org/tunes/{int(rest.partition('/')[0])}?format=json"
    if scheme == 'jrp':
        return f'https://josquin.stanford.edu/data?a=humdrum&f={urllib.parse.quote(rest)}'
    if scheme == 'mfiles':
        return f"https://www.mfiles.co.uk/downloads/{rest.removesuffix('.mid')}.mid"
    if scheme == 'mutopia':
        return f"https://www.mutopiaproject.org/ftp/{rest.lstrip('/')}"
    return rest


def resolve(source: str, *, movement=None, number=None):
    scheme, sep, rest = source.partition(':')
    if sep and scheme in SCHEMES:
        if scheme == 'corpus':
            return from_corpus(rest, movement, number)
        if scheme == 'humdrum':
            return from_github(rest)
        if scheme == 'kernscores':
            return from_kernscores(rest)
        if scheme == 'session':
            return from_session(rest)
        if scheme == 'jrp':
            return from_jrp(rest)
        if scheme == 'mfiles':
            return from_mfiles(rest)
        if scheme == 'mutopia':
            return from_mutopia(rest)
        return from_url(rest)
    if source.startswith(('http://', 'https://')):
        return from_url(source)
    if os.path.exists(source):
        return converter.parse(source), os.path.abspath(source)
    return from_corpus(source, movement, number)        # bare corpus path


# ---------------------------------------------------------------- summary


def summarize(sc, *, analyze_key: bool = True) -> dict:
    if isinstance(sc, stream.Opus):
        sc = sc.scores[0]
    parts = list(sc.parts) if hasattr(sc, 'parts') else []
    measures = len(parts[0].getElementsByClass(stream.Measure)) if parts \
        else len(sc.getElementsByClass(stream.Measure))
    tss = sc.recurse().getElementsByClass('TimeSignature')
    md = sc.metadata
    out = {
        'title': (md.title or md.movementName) if md else None,
        'composer': md.composer if md else None,
        'parts': len(parts),
        'partNames': [str(p.partName or p.partAbbreviation or p.id) for p in parts][:12],
        'measures': measures,
        'notes': len(sc.recurse().notes),
        'timeSignature': tss[0].ratioString if tss else None,
        'quarterLength': float(sc.highestTime),
    }
    out['key'] = str(sc.analyze('key')) if analyze_key else None
    return out


def one_line(info: dict, provenance: str) -> str:
    return (f"{info['title'] or '(untitled)'} | {info['parts']} parts | "
            f"{info['measures']} bars | {info['key'] or 'key n/a'} | "
            f"{info['timeSignature'] or '?'} | {info['notes']} notes | {provenance}")


# ---------------------------------------------------------------- corpus search


def corpus_search(expr: str, limit: int) -> int:
    """--search "composer=bach numberOfParts=4 timeSignature=3/4" (offline)."""
    bundle = None
    for token in expr.split():
        field, sep, query = token.partition('=')
        if not sep:
            field, query = None, token
        if query.isdigit():
            query = int(query)
        bundle = (corpus.search(query, field=field) if bundle is None
                  else bundle.search(query, field=field))
    if bundle is None:
        print('empty search', file=sys.stderr)
        return 1
    print(f'{len(bundle)} matches')
    for entry in list(bundle)[:limit]:
        print(f'  {entry.sourcePath}'
              + (f'  #{entry.number}' if entry.number is not None else ''))
    return 0


# ---------------------------------------------------------------- cli


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('source', nargs='?', help='scheme:spec, URL, file path, or corpus path')
    ap.add_argument('--movement', type=int, default=None, help='corpus movement number')
    ap.add_argument('--number', type=int, default=None, help='opus member (ABC multi-tune)')
    ap.add_argument('--out', default=None, help='write the score out (format from extension)')
    ap.add_argument('--json', action='store_true')
    ap.add_argument('--raw', action='store_true', help='dump fetched bytes, do not parse')
    ap.add_argument('--no-key', action='store_true', help='skip key analysis')
    ap.add_argument('--no-cache', action='store_true')
    ap.add_argument('--search', default=None, help='offline corpus search expression')
    ap.add_argument('--limit', type=int, default=20)
    ap.add_argument('--schemes', action='store_true', help='list supported source schemes')
    args = ap.parse_args(argv)

    if args.schemes:
        for name, (desc, example) in SCHEMES.items():
            print(f'{name:11s} {desc}\n            e.g. {example}')
        return 0
    if args.search:
        return corpus_search(args.search, args.limit)
    if not args.source:
        ap.error('need a source (or --search / --schemes)')

    if args.no_cache:
        global http_get
        _inner = http_get
        http_get = lambda url, **kw: _inner(url, cache=False)  # noqa: E731

    if args.raw:
        try:
            url = resolve_url(args.source)
        except ValueError as exc:
            print(exc, file=sys.stderr)
            return 2
        sys.stdout.buffer.write(http_get(url, cache=not args.no_cache))
        return 0

    try:
        sc, provenance = resolve(args.source, movement=args.movement, number=args.number)
    except Exception as exc:                                  # noqa: BLE001
        print(f'FETCH FAILED {type(exc).__name__}: {exc}', file=sys.stderr)
        return 2

    info = summarize(sc, analyze_key=not args.no_key)
    info['source'] = provenance
    if args.out:
        sc.write(fmt=None, fp=args.out)
        info['written'] = args.out
    print(json.dumps(info, indent=2) if args.json else one_line(info, provenance))
    return 0


if __name__ == '__main__':
    sys.exit(main())
