from dataclasses import dataclass
import functools
from typing import Iterable, List, Set, Tuple, no_type_check
from resolver import Package, PackageProvider, PackageVersion, Requirement, Version
import requests
import argparse
from pathlib import Path
from urllib.parse import quote
from hashlib import sha1
import json

MOD_PORTAL_URL = 'https://mods.factorio.com'
INTERNAL_MODS = ['base', 'space-age', 'elevated-rails', 'quality']


@dataclass(frozen=True)
class FactorioModVersion(PackageVersion):
    # mod: 'FactorioMod'
    # version: Version
    # dependencies: Tuple[Requirement, ...]
    package: "FactorioMod"
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
        object.__setattr__(self, "name", name)
        object.__setattr__(
            self, "releases",
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

    def __init__(self, game_version: Version = Version(2, 0, 28)):
        self.game_version = game_version
        self.package_cache = {}

    def find(self, name: str) -> FactorioMod:
        if name in self.package_cache:
            return self.package_cache[name]

        print(f'Getting {name}')
        if name in INTERNAL_MODS:
            return FactorioMod(name, [(self.game_version, [], '', '')])

        package = load_package(name)
        self.package_cache[name] = package
        return package

    # Just mark the return type correctly
    @no_type_check
    def resolve(self,
                requirements: List[Requirement]) -> Set[FactorioModVersion]:
        return super().resolve(requirements)


def main():
    parser = argparse.ArgumentParser(
        prog='factorio-mod-downloader',
        description=
        'Download mods from Factorio Mod Portal to a folder for use on servers'
    )
    parser.add_argument('mods', nargs='*', type=Requirement.parse)
    parser.add_argument('--factorio-version',
                        required=False,
                        type=Version.parse)
    parser.add_argument('--target', type=Path, default=Path('mods'))
    parser.add_argument('--username', type=str, required=True)
    parser.add_argument('--token', type=str, required=True)
    args = parser.parse_args()

    provider = FactorioModProvider(args.factorio_version)
    resolved = provider.resolve(args.mods)

    # Remove internal mods
    resolved = {mod for mod in resolved if mod.name not in INTERNAL_MODS}

    print('Installing the following mods:')
    for mod in resolved:
        print(f'{mod.name}: {mod.version}')

    for mod in resolved:
        url = f'{MOD_PORTAL_URL}{mod.download_url}?username={quote(args.username)}&token={quote(args.token)}'
        print(f'Downloading {mod.name}: {url}')
        r = requests.get(url)
        assert r.status_code == 200
        assert r.headers['content-type'] == 'application/octet-stream'
        data = r.content
        assert sha1(data).hexdigest() == mod.sha1
        open(args.target / f'{mod.name}_{mod.version}.zip', 'wb').write(data)

    # Write a mod list
    modlist = {
        'mods': [{
            'name': mod.name,
            'enabled': True
        } for mod in resolved]
    }
    json.dump(modlist, open(args.target / f'mod-list.json', 'w'))


if __name__ == '__main__':
    main()
