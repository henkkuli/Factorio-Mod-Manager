#!/usr/bin/env python3

from dataclasses import dataclass
import functools
from typing import Any, Dict, Iterable, List, Set, Tuple, no_type_check, override
from resolver import Package, PackageProvider, PackageVersion, Requirement, Version
import requests
import argparse
from pathlib import Path
from urllib.parse import quote
from hashlib import sha1
import json

MOD_PORTAL_URL = 'https://mods.factorio.com'
INTERNAL_MODS = ['base', 'space-age', 'elevated-rails', 'quality']
DEFAULT_FACTORIO_VERSION = Version(2, 0, 28)


@dataclass(frozen=True)
class FactorioModVersion(PackageVersion):
    # mod: 'FactorioMod'
    # version: Version
    # dependencies: Tuple[Requirement, ...]
    package: 'FactorioMod'
    download_url: str
    sha1: str

    def __hash__(self) -> int:
        return hash((self.name, self.version, self.dependencies,
                     self.download_url, self.sha1))


@dataclass(frozen=True)
class FactorioMod(Package):
    # name: str
    releases: Tuple[FactorioModVersion, ...]

    def __init__(self, name: str,
                 versions: Iterable[Tuple[Version, Iterable[Requirement], str,
                                          str]]):
        object.__setattr__(self, 'name', name)
        object.__setattr__(
            self, 'releases',
            tuple(
                FactorioModVersion(self, version, tuple(dependencies), url,
                                   sha1)
                for version, dependencies, url, sha1 in versions))


def load_package(modname: str) -> FactorioMod:
    r = requests.get(f'{MOD_PORTAL_URL}/api/mods/{modname}/full')
    assert r.status_code == 200
    assert r.headers['content-type'].startswith('application/json')
    assert r.encoding == 'utf-8'
    data = r.json()

    assert data['name'] == modname
    versions = [(Version.parse(release['version']), [
        Requirement.parse(dep) for dep in release['info_json']['dependencies']
    ], release['download_url'], release['sha1'])
                for release in data['releases']]

    return FactorioMod(modname, versions)


class FactorioModProvider(PackageProvider):

    def __init__(self, game_version: Version = DEFAULT_FACTORIO_VERSION):
        self.game_version = game_version
        self.package_cache = {}

    def find(self, name: str) -> FactorioMod:
        if name in self.package_cache:
            return self.package_cache[name]

        if name in INTERNAL_MODS:
            return FactorioMod(name, [(self.game_version, [], '', '')])

        print(f'Getting info for mod {name}')
        package = load_package(name)
        self.package_cache[name] = package
        return package

    # Just mark the return type correctly
    @no_type_check
    def resolve(self,
                requirements: List[Requirement]) -> Set[FactorioModVersion]:
        return super().resolve(requirements)


def load_mod_list(file: Path) -> List[Requirement]:
    lines = file.open('r').readlines()
    return [Requirement.parse(line) for line in lines]


@dataclass(frozen=True)
class LockEntry:
    name: str
    version: Version
    download_url: str
    sha1: str


class LockEntryEncoder(json.JSONEncoder):

    @override
    def default(self, o):
        if isinstance(o, LockEntry):
            return vars(o)
        if isinstance(o, Version):
            return str(o)
        return super().default(o)


class LockEntryDecoder(json.JSONDecoder):

    def __init__(self):

        def object_hook(val: Dict[str, Any]) -> LockEntry | Dict[str, Any]:
            if 'name' in val and 'version' in val and 'download_url' in val and 'sha1' in val:
                return LockEntry(name=val['name'],
                                 version=Version.parse(val['version']),
                                 download_url=val['download_url'],
                                 sha1=val['sha1'])
            return val

        return super().__init__(object_hook=object_hook)


def load_lock_file(file: Path) -> List[LockEntry]:
    return LockEntryDecoder().decode(file.open('r').read())


def store_lock_file(file: Path, lock: List[LockEntry]):
    file.open('w').write(LockEntryEncoder().encode(lock))


def update(mods: List[Requirement],
           factorio_version: Version) -> List[LockEntry]:
    provider = FactorioModProvider(factorio_version)
    resolved = provider.resolve(mods)

    resolved = {mod for mod in resolved if mod.name not in INTERNAL_MODS}

    lock: List[LockEntry] = [
        LockEntry(name=mod.name,
                  version=mod.version,
                  download_url=mod.download_url,
                  sha1=mod.sha1) for mod in resolved
    ]
    lock.sort(key=lambda entry: entry.name)

    return lock


def update_command(args):
    lock = update(load_mod_list(args.mods), args.factorio_version)
    store_lock_file(args.lock, lock)


def install_command(args):
    lock: List[LockEntry]
    try:
        lock = load_lock_file(args.lock)
    except FileNotFoundError:
        print('Lock file not found. Generating one.')
        lock = update(load_mod_list(args.mods), args.factorio_version)
        store_lock_file(args.lock, lock)
    except ValueError:
        print('Lock file malformed. Bailing. Please fix it or delete it.')
        exit(1)

    for mod in lock:
        url = f'{MOD_PORTAL_URL}{mod.download_url}?username={quote(args.username)}&token={quote(args.token)}'
        print(f'Downloading {mod.name} {mod.version}')
        r = requests.get(url)
        assert r.status_code == 200
        assert r.headers['content-type'] == 'application/octet-stream'
        data = r.content
        assert sha1(data).hexdigest() == mod.sha1
        open(args.target / f'{mod.name}_{mod.version}.zip', 'wb').write(data)

    # Write a mod list so that the game knows which mods to enable
    modlist = {'mods': [{'name': mod.name, 'enabled': True} for mod in lock]}
    json.dump(modlist, open(args.target / f'mod-list.json', 'w'))


def main():
    parser = argparse.ArgumentParser(
        prog='factorio-mod-manager',
        description='A tool for managing Factorio mods')
    parser.add_argument('--factorio-version',
                        required=False,
                        type=Version.parse,
                        default=DEFAULT_FACTORIO_VERSION)

    parser.add_argument('--mods',
                        type=Path,
                        help='location of the mods file',
                        default=Path('factorio-mods.txt'))
    parser.add_argument('--lock',
                        type=Path,
                        help='location of the mod lock file',
                        default=Path('factorio-mods.lock'))

    parser_group = parser.add_subparsers(title='Command',
                                         help='Command to execute',
                                         required=True)

    update_parser = parser_group.add_parser(
        'update', help='update lock file based on latest data on mod portal')
    update_parser.set_defaults(func=update_command)

    install_parser = parser_group.add_parser(
        'install',
        help=
        'install mods based on lockfile. If no lockfile exists, creates one')
    install_parser.add_argument('--target',
                                type=Path,
                                help='target where mods installed to',
                                default=Path('mods'))
    install_parser.add_argument(
        '--username',
        type=str,
        help='Factorio username; required for download',
        required=True)
    install_parser.add_argument(
        '--token',
        type=str,
        help='Factorio token; can be generated on Factorio.com',
        required=True)
    install_parser.set_defaults(func=install_command)

    args = parser.parse_args()
    args.func(args)


if __name__ == '__main__':
    main()
