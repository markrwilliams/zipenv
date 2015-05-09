from contextlib import contextmanager
import zipfile
import pkgutil
import os
import subprocess
import textwrap
import tempfile
import logging
import common
import shutil

logger = logging.getLogger(__name__)


class TemporaryVirtualenv(object):

    def __init__(self, path):
        self.path = path

    def in_venv(self, *cmd):
        return [os.path.join(self.path, 'bin', cmd[0])] + list(cmd[1:])

    def cmd(self, args, stdin=None):
        cmd = subprocess.Popen(args,
                               stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE,
                               stdin=subprocess.PIPE)
        stdout, stderr = cmd.communicate(stdin)
        logger.debug('%r stdout:\n%s\n', args, stdout)
        logger.debug('%r stderr:\n%s\n', args, stderr)
        if cmd.returncode:
            raise subprocess.CalledProcessError(cmd.returncode, cmd)
        return stdout, stderr

    def create(self):
        logger.info('creating virtualenv in %s', self.path)
        self.cmd(['virtualenv', self.path])

    def install_requirements(self, *requirements):
        logger.info('installing requirements %r', requirements)
        self.cmd(self.in_venv('pip', 'install', *requirements))

    def determine_site_packages(self):
        program = '''\
        import sys
        for s in sys.path:
            if 'site-packages' in s:
                print s
        '''

        stdout, _ = self.cmd(self.in_venv('python'),
                             stdin=textwrap.dedent(program))
        return stdout.splitlines()


class ZipEnv(object):

    def __init__(self, venv, path):
        self.path = path
        self.venv = venv
        self.site_packages_manager = common.ManagesSitePackages(path)

    def copy_site_packages(self):
        self.site_packages_manager.copy_site_packages(self.venv)

    def entry_point_to_import(self, entry_point):
        module, callable_point = entry_point.split(':')
        return 'import %s\n%s.%s()' % (module, module, callable_point)

    def establish_main(self, entry_point):
        common = pkgutil.get_data(__name__, 'common.py')

        main = os.path.join(self.path, '__main__.py')

        with open(main, 'w') as f:
            f.write(common)
            f.write('\n\n')
            f.write('_replace_zipimporter()')
            f.write('\n\n')
            f.write(self.entry_point_to_import(entry_point))
            f.write('\n\n')

    def finish(self, output):
        zipped = zipfile.ZipFile(output, 'w')

        for root, _, files in os.walk(self.path):
            for fn in files:
                src = os.path.join(root, fn)
                dst = common.relpath(self.path, src)
                zipped.write(src, dst)


@contextmanager
def tmpdir():
    directory = tempfile.mkdtemp()
    try:
        yield directory
    finally:
        shutil.rmtree(directory)


def run(requirements, entry_point, output):
    with tmpdir() as venv_path:
        venv = TemporaryVirtualenv(venv_path)
        venv.create()
        venv.install_requirements(*requirements)

        with tmpdir() as zip_path:
            zipped = ZipEnv(venv, zip_path)
            zipped.copy_site_packages()
            zipped.establish_main(entry_point)
            zipped.finish(output)
