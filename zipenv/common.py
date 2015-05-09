import sys
import os
import imp
import tempfile
import shutil
import zipfile
from zipimport import zipimporter


def relpath(parent, path):
    relpath = path.replace(parent, '')
    if relpath.startswith('/'):
        relpath = relpath[1:]
    return relpath


class ManagesSitePackages(object):
    SITE_PACKAGES_FILE = 'site_packages.txt'

    def __init__(self, path, opener=None):
        self.path = path
        self.site_packages_file = os.path.join(self.path,
                                               self.SITE_PACKAGES_FILE)
        self.open = opener or open

    def open_site_packages_file(self, mode='r'):
        return self.open(self.site_packages_file, mode)

    def _copy_tree_to_nested_targed(self, src, dst):
        parent = os.path.dirname(dst)
        if parent:
            os.makedirs(parent)
        shutil.copytree(src, dst)

    def copy_site_packages(self, temporary_venv):
        site_packages_directories = temporary_venv.determine_site_packages()
        relative_site_packages_directories = []

        for site_packages in site_packages_directories:
            path = relpath(temporary_venv.path, site_packages)
            target = os.path.join(self.path, path)
            self._copy_tree_to_nested_targed(site_packages, target)
            relative_site_packages_directories.append(path)

        self._writelines(relative_site_packages_directories)

    def _writelines(self, site_packages_directories):
        with self.open_site_packages_file('w') as f:
            for site_packages in site_packages_directories:
                f.write(site_packages + '\n')

    def readlines(self):
        with self.open_site_packages_file() as f:
            for line in f:
                yield line.strip()


class ZipImporterLoadsExtension(object):

    def __init__(self, archive, get_data, module_path):
        self.archive = archive
        self.get_data = get_data
        self.module_path = module_path

    def load_module(self, fullname):
        with tempfile.NamedTemporaryFile() as f:
            f.write(self.get_data(self.module_path))
            f.flush()

            module = imp.load_dynamic(fullname, f.name)
            module.__file__ = os.path.join(self.archive, self.module_path)
            return module


class ZipImporterFindsExtensions(zipimporter):
    EXTENSION_EXTS = [suffix
                      for suffix, _, kind in imp.get_suffixes()
                      if kind == imp.C_EXTENSION]

    def __call__(self, path):
        directory = os.path.join(self.archive, self.prefix)
        if path == self.archive:
            path = directory

        if path.startswith(directory):
            return self.__class__(path)

        raise ImportError

    def find_module(self, fullname, path=None):
        finder = super(ZipImporterFindsExtensions,
                       self).find_module(fullname, path)
        if finder is None:
            return self.find_so(fullname, path)
        return finder

    def find_so(self, fullname, path):
        _, _, module_path_no_ext = fullname.rpartition('.')

        path = path or [self.prefix]

        for possible_path in path:
            possible_path = relpath(self.archive, possible_path)
            module_path_no_ext = os.path.join(possible_path,
                                              module_path_no_ext)
            for ext in self.EXTENSION_EXTS:
                module_path = module_path_no_ext + ext
                if module_path in self._files:
                    return ZipImporterLoadsExtension(self.archive,
                                                     self.get_data,
                                                     module_path)


def _replace_zipimporter():
    zip_path = os.path.dirname(__file__)
    manager = ManagesSitePackages(path='',
                                  opener=zipfile.ZipFile(zip_path).open)

    sys.path_hooks = [ZipImporterFindsExtensions(os.path.join(zip_path,
                                                              site_packages))
                      for site_packages in manager.readlines()]
    sys.path_importer_cache.pop(zip_path)
