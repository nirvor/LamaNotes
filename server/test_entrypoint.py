import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


class EntrypointTests(unittest.TestCase):
    def setUp(self):
        self.shell = shutil.which('sh')
        if not self.shell and os.name == 'nt':
            candidate = Path(os.environ.get('ProgramFiles', 'C:/Program Files')) / 'Git/bin/sh.exe'
            if candidate.is_file():
                self.shell = str(candidate)
        if not self.shell:
            self.skipTest('A POSIX shell is required to execute the container entrypoint.')

    def run_entrypoint(self, uid, gid, forwarded=None, legacy=False):
        with tempfile.TemporaryDirectory(prefix='lamanotes-entrypoint-') as directory:
            root = Path(directory)
            bin_dir = root / 'mock bin'
            bin_dir.mkdir()
            scripts = {
                'id': 'case "$1" in -u) echo "$TEST_UID";; -g) echo "$TEST_GID";; esac',
                'chown': 'printf "CHOWN:%s\\n" "$@"',
                'python': 'printf "ARG:%s\\n" "$@"',
                'runner': 'printf "RUNNER:%s\\n" "$1"; shift; exec "$@"',
            }
            for name, body in scripts.items():
                script = bin_dir / name
                script.write_text('#!/bin/sh\n' + body + '\n', encoding='utf-8', newline='\n')
                script.chmod(0o755)
            source = Path(__file__).resolve().parents[1] / 'entrypoint.sh'
            entrypoint = root / 'entrypoint.sh'
            # Docker normalizes checkout line endings in the same way.
            entrypoint.write_text(source.read_text(encoding='utf-8'), encoding='utf-8', newline='\n')
            env = dict(os.environ)
            for key in ('LAMANOTES_HOST', 'LAMANOTES_PORT', 'LAMANOTES_PATH',
                        'FLATNOTES_HOST', 'FLATNOTES_PORT', 'FLATNOTES_PATH',
                        'FORWARDED_ALLOW_IPS'):
                env.pop(key, None)
            prefix = 'FLATNOTES' if legacy else 'LAMANOTES'
            env.update({
                'TEST_BIN': bin_dir.as_posix(),
                'EXEC_TOOL': (bin_dir / 'runner').as_posix(),
                'PUID': '1000', 'PGID': '1001', 'TEST_UID': str(uid), 'TEST_GID': str(gid),
                prefix + '_HOST': '127.0.0.2', prefix + '_PORT': '8090',
                prefix + '_PATH': '/data with spaces',
            })
            if forwarded is not None:
                env['FORWARDED_ALLOW_IPS'] = forwarded
            command = 'PATH="$(cd "$TEST_BIN" && pwd):$PATH"; export PATH; exec sh "$1"'
            result = subprocess.run([self.shell, '-c', command, 'entrypoint-test', entrypoint.as_posix()],
                                    cwd=root, env=env, capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
            return result.stdout.splitlines()

    def test_proxy_argument_is_one_unquoted_argv_value(self):
        for uid, gid in ((0, 0), (1000, 1001)):
            for setting in (None, '', '10.0.4.4', '127.0.0.1,10.0.4.4', '*'):
                with self.subTest(uid=uid, setting=setting):
                    lines = self.run_entrypoint(uid, gid, setting)
                    self.assertEqual([line[4:] for line in lines if line.startswith('ARG:')], [
                        '-m', 'uvicorn', 'main:app', '--app-dir', 'server',
                        '--host', '127.0.0.2', '--port', '8090', '--proxy-headers',
                        '--forwarded-allow-ips', setting or '127.0.0.1',
                    ])

    def test_root_preserves_uid_gid_and_path_as_single_arguments(self):
        lines = self.run_entrypoint(0, 0)
        self.assertEqual([line for line in lines if line.startswith('RUNNER:')], ['RUNNER:1000:1001'])
        self.assertEqual([line for line in lines if line.startswith('CHOWN:')], [
            'CHOWN:-R', 'CHOWN:1000:1001', 'CHOWN:/data with spaces',
        ])

    def test_non_root_skips_permission_changes_and_keeps_legacy_environment(self):
        for uid, gid in ((1000, 1001), (0, 1001)):
            with self.subTest(uid=uid, gid=gid):
                lines = self.run_entrypoint(uid, gid, legacy=True)
                self.assertFalse(any(line.startswith(('RUNNER:', 'CHOWN:')) for line in lines))
                args = [line[4:] for line in lines if line.startswith('ARG:')]
                self.assertEqual(args[args.index('--host') + 1], '127.0.0.2')
                self.assertEqual(args[args.index('--port') + 1], '8090')


if __name__ == '__main__':
    unittest.main()
