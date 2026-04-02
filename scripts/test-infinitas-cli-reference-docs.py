#!/usr/bin/env python3
import difflib
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / 'src'
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def fail(message):
    print(f'FAIL: {message}', file=sys.stderr)
    raise SystemExit(1)


def main():
    target = ROOT / 'docs' / 'reference' / 'cli-reference.md'
    if not target.exists():
        fail(f'missing CLI reference doc: {target}')

    result = subprocess.run(
        ['uv', 'run', 'python3', '-m', 'infinitas_skill.cli.reference'],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        fail(
            'could not generate CLI reference from maintained toolchain\n'
            f'stdout:\n{result.stdout}\n'
            f'stderr:\n{result.stderr}'
        )

    expected = result.stdout
    actual = target.read_text(encoding='utf-8')
    if actual != expected:
        diff = ''.join(
            difflib.unified_diff(
                actual.splitlines(keepends=True),
                expected.splitlines(keepends=True),
                fromfile=str(target),
                tofile='generated-cli-reference',
            )
        )
        fail(f'CLI reference doc is out of date; regenerate it from code.\n{diff}')

    print('OK: CLI reference doc matches generated argparse output')


if __name__ == '__main__':
    main()
