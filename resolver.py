from abc import ABCMeta, abstractmethod
from dataclasses import dataclass
from typing import Callable, Dict, Generator, Iterable, List, Optional, Set, Tuple, Union, overload
from enum import Enum
from itertools import takewhile
from collections import ChainMap


class Prefix(Enum):
    NONE = 0
    INCOMPATIBLE = 1
    OPTIONAL = 2
    HIDDEN_OPTIONAL = 3
    UNORDERED = 4

    def __str__(self) -> str:
        s = {
            Prefix.NONE: '',
            Prefix.INCOMPATIBLE: '!',
            Prefix.OPTIONAL: '?',
            Prefix.HIDDEN_OPTIONAL: '(?)',
            Prefix.UNORDERED: '~',
        }
        return s[self]

    def __repr__(self) -> str:
        return str(self)


class Comparison(Enum):
    LT = 1
    LE = 2
    EQ = 3
    GE = 4
    GT = 5

    def __str__(self) -> str:
        s = {
            Comparison.LT: '<',
            Comparison.LE: '<=',
            Comparison.EQ: '=',
            Comparison.GE: '>=',
            Comparison.GT: '>',
        }
        return s[self]

    def __repr__(self) -> str:
        return str(self)


@dataclass(frozen=True)
class Version:
    parts: Tuple[int, ...]

    @overload
    def __init__(self, parts: List[int]) -> None:
        ...

    @overload
    def __init__(self, *args: int) -> None:
        ...

    def __init__(self, parts: Union[List[int], int], *args):
        if len(args) == 0:
            if isinstance(parts, int):
                # Got a singleton input
                parts = [parts]
            elif isinstance(parts, list):
                pass
            else:
                raise ValueError('Invalid first argument')
        else:
            if isinstance(parts, int):
                parts = [parts]
                parts.extend(args)
            else:
                raise ValueError('Invalid first argument')
        object.__setattr__(self, "parts", tuple(parts))

    def __cmp(self, other: "Version",
              comparator: Callable[[List[int], List[int]], bool]):

        def extend(parts: Tuple[int, ...], length: int) -> List[int]:
            return list(parts) + ([0] * (length - len(parts)))

        length = max(len(self.parts), len(other.parts))
        return comparator(extend(self.parts, length),
                          extend(other.parts, length))

    def __lt__(self, other):
        return self.__cmp(other, lambda a, b: a < b)

    def __le__(self, other):
        return self.__cmp(other, lambda a, b: a <= b)

    def __eq__(self, other):
        return self.__cmp(other, lambda a, b: a == b)

    def __ne__(self, other):
        return self.__cmp(other, lambda a, b: a != b)

    def __ge__(self, other):
        return self.__cmp(other, lambda a, b: a >= b)

    def __gt__(self, other):
        return self.__cmp(other, lambda a, b: a > b)

    @staticmethod
    def parse(s: str) -> 'Version':

        def str_to_int(s: str) -> int:
            # By default, int allows spaces, so make sure that the input was really just the number
            if s.strip() != s:
                raise ValueError(f'Extra characters: {s}')
            i = int(s)
            # Version number must be between 0 and 65535
            if i < 0 or i > 65535:
                raise ValueError(f'Out of range: {s}')
            return i

        parts = list(map(str_to_int, s.split('.')))

        return Version(parts)

    def __str__(self) -> str:
        return '.'.join(map(str, self.parts))

    def __repr__(self) -> str:
        return str(self)


@dataclass(frozen=True)
class VersionComparison:
    comparison: Comparison
    version: Version

    def compare(self, version: Version) -> bool:
        cmp = {
            Comparison.LT: Version.__lt__,
            Comparison.LE: Version.__le__,
            Comparison.EQ: Version.__eq__,
            Comparison.GE: Version.__ge__,
            Comparison.GT: Version.__gt__,
        }
        return cmp[self.comparison](version, self.version)


@dataclass(frozen=True)
class Requirement:
    prefix: Prefix
    name: str
    vercomp: Optional[VersionComparison]

    @property
    def is_required(self) -> bool:
        return self.prefix == Prefix.NONE or self.prefix == Prefix.UNORDERED

    def __str__(self) -> str:
        s = []
        if self.prefix != Prefix.NONE:
            s.append(str(self.prefix))
        s.append(self.name)
        if self.vercomp is not None:
            s.append(f'{self.vercomp.comparison} {self.vercomp.version}')
        return ' '.join(s)

    def __repr__(self) -> str:
        return str(self)

    @staticmethod
    def parse(s: str) -> 'Requirement':
        orig = s
        s = s.strip()
        # Parse prefix
        prefix = Prefix.NONE
        if s.startswith('!'):
            s = s[1:]
            prefix = Prefix.INCOMPATIBLE
        elif s.startswith('?'):
            s = s[1:]
            prefix = Prefix.OPTIONAL
        elif s.startswith('(?)'):
            s = s[3:]
            prefix = Prefix.HIDDEN_OPTIONAL
        elif s.startswith('~'):
            s = s[1:]
            prefix = Prefix.UNORDERED

        s = s.lstrip()

        # Parse name
        name = ''.join(takewhile(lambda c: c not in '<=>', s)).strip()
        s = s[len(name):]
        if name == '':
            raise ValueError(f'Invalid requirement string: {orig}')

        s = s.lstrip()

        # Parse version
        vercomp: Optional[VersionComparison] = None
        if s != '':
            comp: Comparison
            if s.startswith('<='):
                comp = Comparison.LE
                s = s[2:]
            elif s.startswith('>='):
                comp = Comparison.GE
                s = s[2:]
            elif s.startswith('<'):
                comp = Comparison.LT
                s = s[1:]
            elif s.startswith('>'):
                comp = Comparison.GT
                s = s[1:]
            elif s.startswith('='):
                comp = Comparison.EQ
                s = s[1:]
            else:
                raise ValueError(f'Invalid requirement string: {orig}')
            s = s.lstrip()
            version = Version.parse(s)
            vercomp = VersionComparison(comp, version)
            if prefix == Prefix.INCOMPATIBLE:
                # Doesn't really make sense. If someone wants to restrict the
                # version to be sufficiently low, they should use < operator.
                vercomp = None

        return Requirement(prefix, name, vercomp)


@dataclass(frozen=True)
class PackageVersion:
    package: 'Package'
    version: Version
    dependencies: Tuple[Requirement, ...]

    @property
    def name(self) -> str:
        return self.package.name

    def __str__(self) -> str:
        return f'{self.name}({self.version})'

    def __repr__(self) -> str:
        return str(self)

    def __hash__(self) -> int:
        return hash((self.name, self.version, self.dependencies))


@dataclass(frozen=True)
class Package:
    name: str
    releases: Tuple[PackageVersion, ...]

    def __init__(self, name: str,
                 versions: Iterable[Tuple[Version, Iterable[Requirement]]]):
        object.__setattr__(self, "name", name)
        object.__setattr__(
            self, "releases",
            tuple(
                PackageVersion(self, version, tuple(dependencies))
                for version, dependencies in versions))

    def get(self,
            version: Version,
            default: Optional[PackageVersion] = None
            ) -> Optional[PackageVersion]:
        res = next(pv for pv in self.releases if pv.version == version)
        if res is None:
            return default
        return res

    def __getitem__(self, version: Version) -> PackageVersion:
        res = self.get(version)
        if res is None:
            raise KeyError()
        return res


class PackageProvider(metaclass=ABCMeta):

    @abstractmethod
    def find(self, name: str) -> Package:
        raise NotImplemented

    def resolve(self, requirements: List[Requirement]) -> Set[PackageVersion]:

        def requirement_to_fun(
            req: Requirement, prev: Optional[Callable[[PackageVersion], bool]]
        ) -> Callable[[PackageVersion], bool]:

            def is_compatible(pkgver: PackageVersion) -> bool:
                if prev and not prev(pkgver):
                    return False
                if req.parse == Prefix.INCOMPATIBLE:
                    return req.name != pkgver.name
                # If name doesn't match, then this requirement doesn't affect that package
                if pkgver.name != req.name:
                    return True
                # No version comparison, no restriction
                if req.vercomp is None:
                    return True
                return req.vercomp.compare(pkgver.version)

            return is_compatible

        def search(
            packages: List[Package],
            reqs: ChainMap[str, Callable[[PackageVersion], bool]],
            selected: Dict[str, PackageVersion],
        ) -> Generator[Dict[str, PackageVersion], None, None]:
            # print(f'{[p.name for p in packages]}: {[v for k,v in selected.items()]}')
            if not packages:
                # Check that all requirements have actually been satisfied.
                # If this doesn't hold, then there's a bug in the resolver.
                assert all(
                    reqs.get(s.name, lambda _: True)(s)
                    for s in selected.values())

                yield selected
                return

            package = packages.pop()

            # Filter out incompatible versions and order them from the newest to olders
            versions = list(package.releases)
            versions = filter(reqs.get(package.name, lambda _: True), versions)
            versions = sorted(versions,
                              key=lambda pkgver: pkgver.version,
                              reverse=True)

            # Try all versions until a match is found
            for pkgver in versions:
                # Check that already-selected packages satisfy requirements
                for dep in pkgver.dependencies:
                    if dep.name in selected:
                        if not requirement_to_fun(dep, None)(
                                selected[dep.name]):
                            raise InconsistentRequirements

                # Add new requirements
                newreqs = reqs.new_child({
                    dep.name:
                    requirement_to_fun(dep, reqs.get(dep.name))
                    for dep in pkgver.dependencies
                })
                # Lock the version of this package
                newreqs[package.name] = lambda pv: pv.version == pkgver.version
                # Copy worklist
                newpackages = packages.copy()
                newpackages.extend(
                    self.find(dep.name) for dep in pkgver.dependencies
                    if dep.is_required and not dep.name in selected)
                # Add new version to selected
                newselected = selected.copy()
                newselected[package.name] = pkgver
                try:
                    yield from search(newpackages, newreqs, newselected)
                except InconsistentRequirements:
                    pass

            raise InconsistentRequirements()

        # Create a meta package to act as the root
        root = Package('$root', [(Version(0, 0, 0), requirements)])

        result = next(search([root], ChainMap(), {}))
        if result is None:
            raise InconsistentRequirements()
        # Pop root package
        # assert result.pop().name == '$root'
        del result['$root']

        return set(result.values())


class StaticPackageProvider(PackageProvider):

    def __init__(self, packages: List[Package]):
        self.packages = packages

    def find(self, name: str) -> Package:
        return next(p for p in self.packages if p.name == name)


class InconsistentRequirements(BaseException):
    pass
