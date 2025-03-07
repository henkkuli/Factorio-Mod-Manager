import pytest
from resolver import Comparison, InconsistentRequirements, Package, Prefix, Requirement, StaticPackageProvider, Version, VersionComparison


@pytest.mark.parametrize('version,parts', [(Version(1), (1, )),
                                           (Version(1, 2), (1, 2)),
                                           (Version([1, 2]), (1, 2))])
def test_version_init(version, parts):
    assert version.parts == parts


@pytest.mark.parametrize(
    's,version',
    [
        ('0.0.0', Version(0, 0, 0)),
        ('0.00.0', Version(0, 0, 0)),
        ('1.2.3', Version(1, 2, 3)),
        ('11.22.333', Version(11, 22, 333)),
        ('65535.65535.65535', Version(65535, 65535, 65535)),
        # Stub version strings
        ('1', Version(1)),
        ('1.2', Version(1, 2)),
        # Extra long version strings
        ('1.2.3.4.5', Version(1, 2, 3, 4, 5)),
    ])
def test_version_parse_valid(s, version):
    assert Version.parse(s) == version


@pytest.mark.parametrize(
    's',
    [
        ' 0.0.0',
        '0.0.0 ',
        'foo.bar.baz',
        '1. 2.3',
        '1.2. 3',
        # Version number out of range
        '-1.2.3',
        '1.-2.3',
        '1.2.65536',
    ])
def test_version_parse_invalid(s):
    with pytest.raises(ValueError):
        Version.parse(s)


def test_version_order():
    # Trailing zeros should not affect the version
    assert Version(1) <= Version(1, 0)
    assert Version(1) >= Version(1, 0)
    assert Version(1) == Version(1, 0)

    assert Version(1) < Version(2)
    assert Version(1) < Version(2, 0)
    assert Version(1, 0) < Version(2)
    assert Version(1, 0) < Version(2, 0)


@pytest.mark.parametrize(
    's,requirement',
    [
        # Examples from documentation
        ('mod-a', Requirement(Prefix.NONE, 'mod-a', None)),
        ('? mod-c > 0.4.3',
         Requirement(Prefix.OPTIONAL, 'mod-c',
                     VersionComparison(Comparison.GT, Version(0, 4, 3)))),
        ('! mod-g', Requirement(Prefix.INCOMPATIBLE, 'mod-g', None)),
        # Documentation just restricts names 'to only consist of alphanumeric characters, dashes and underscores'
        # Let's test some non-ascii letters
        ('! möd', Requirement(Prefix.INCOMPATIBLE, 'möd', None)),
        ('? möd < 1.2.3',
         Requirement(Prefix.OPTIONAL, 'möd',
                     VersionComparison(Comparison.LT, Version(1, 2, 3)))),
        # All prefixes
        ('a', Requirement(Prefix.NONE, 'a', None)),
        ('! a', Requirement(Prefix.INCOMPATIBLE, 'a', None)),
        ('? a', Requirement(Prefix.OPTIONAL, 'a', None)),
        ('(?) a', Requirement(Prefix.HIDDEN_OPTIONAL, 'a', None)),
        ('~ a', Requirement(Prefix.UNORDERED, 'a', None)),
        # All version comparisons
        ('a < 1.2.3',
         Requirement(Prefix.NONE, 'a',
                     VersionComparison(Comparison.LT, Version(1, 2, 3)))),
        ('a <= 1.2.3',
         Requirement(Prefix.NONE, 'a',
                     VersionComparison(Comparison.LE, Version(1, 2, 3)))),
        ('a = 1.2.3',
         Requirement(Prefix.NONE, 'a',
                     VersionComparison(Comparison.EQ, Version(1, 2, 3)))),
        ('a >= 1.2.3',
         Requirement(Prefix.NONE, 'a',
                     VersionComparison(Comparison.GE, Version(1, 2, 3)))),
        ('a > 1.2.3',
         Requirement(Prefix.NONE, 'a',
                     VersionComparison(Comparison.GT, Version(1, 2, 3)))),
        # Extra spaces
        (' mod', Requirement(Prefix.NONE, 'mod', None)),
        ('mod ', Requirement(Prefix.NONE, 'mod', None)),
        ('!  mod', Requirement(Prefix.INCOMPATIBLE, 'mod', None)),
        ('?  mod', Requirement(Prefix.OPTIONAL, 'mod', None)),
        ('?  mod > 1.2.3',
         Requirement(Prefix.OPTIONAL, 'mod',
                     VersionComparison(Comparison.GT, Version(1, 2, 3)))),
        ('mod >  1.2.3',
         Requirement(Prefix.NONE, 'mod',
                     VersionComparison(Comparison.GT, Version(1, 2, 3)))),
        ('mod  < 1.2.3',
         Requirement(Prefix.NONE, 'mod',
                     VersionComparison(Comparison.LT, Version(1, 2, 3)))),
        ('mod < 1.2.3 ',
         Requirement(Prefix.NONE, 'mod',
                     VersionComparison(Comparison.LT, Version(1, 2, 3)))),
        (' mod < 1.2.3',
         Requirement(Prefix.NONE, 'mod',
                     VersionComparison(Comparison.LT, Version(1, 2, 3)))),
        (' mod < 1.2.3 ',
         Requirement(Prefix.NONE, 'mod',
                     VersionComparison(Comparison.LT, Version(1, 2, 3)))),
        # Too few spaces
        ('?mod<1.2.3',
         Requirement(Prefix.OPTIONAL, 'mod',
                     VersionComparison(Comparison.LT, Version(1, 2, 3)))),
        # Mod name contains spaces; these appear in the wild
        ('my mod', Requirement(Prefix.NONE, 'my mod', None)),
        ('?my mod', Requirement(Prefix.OPTIONAL, 'my mod', None)),
        ('? my mod', Requirement(Prefix.OPTIONAL, 'my mod', None)),
        ('my mod > 1.2.3',
         Requirement(Prefix.NONE, 'my mod',
                     VersionComparison(Comparison.GT, Version(1, 2, 3)))),
        # Incompatibility with a version. Not really allowed, but let's be
        # liberal with what we allow.
        ('! mod > 1.2.3', Requirement(Prefix.INCOMPATIBLE, 'mod', None)),
    ])
def test_requirement_parse_valid(s, requirement):
    assert Requirement.parse(s) == requirement


@pytest.mark.parametrize(
    's',
    [
        # Multiple version requirements
        'mod < 1.2.3 > 4.5.6'
    ])
def test_requirement_parse_invalid(s):
    with pytest.raises(ValueError):
        Requirement.parse(s)


def test_provider_resolve_simple():
    provider = StaticPackageProvider([
        Package('a', [(Version(0, 0, 0), [])]),
        Package('b',
                [(Version(0, 0, 0), [Requirement(Prefix.NONE, 'a', None)])]),
    ])

    assert provider.resolve([Requirement(Prefix.NONE, 'a', None)
                             ]) == {provider.find('a')[Version(0, 0, 0)]}

    assert provider.resolve([Requirement(Prefix.NONE, 'b', None)]) == {
        provider.find('a')[Version(0, 0, 0)],
        provider.find('b')[Version(0, 0, 0)]
    }

    with pytest.raises(InconsistentRequirements):
        provider.resolve([
            Requirement(Prefix.NONE, 'b',
                        VersionComparison(Comparison.GE, Version(1, 0, 0)))
        ])


def test_provider_resolve_optional():
    provider = StaticPackageProvider([
        Package('a', [(Version(0, 0, 0), []), (Version(1, 0, 0), []),
                      (Version(2, 0, 0), [])]),
        Package('b', [(Version(0, 0, 0), [
            Requirement.parse("a >= 0.0.0"),
        ])]),
        Package('c', [(Version(0, 0, 0), [
            Requirement.parse("? a < 2.0.0"),
        ])])
    ])

    assert provider.resolve([Requirement.parse("b")]) == {
        provider.find("a")[Version(2, 0, 0)],
        provider.find("b")[Version(0, 0, 0)],
    }

    assert provider.resolve([Requirement.parse("c")]) == {
        provider.find("c")[Version(0, 0, 0)],
    }

    assert provider.resolve([Requirement.parse("b"),
                             Requirement.parse("c")]) == {
                                 provider.find("a")[Version(1, 0, 0)],
                                 provider.find("b")[Version(0, 0, 0)],
                                 provider.find("c")[Version(0, 0, 0)],
                             }

    assert provider.resolve([Requirement.parse("c"),
                             Requirement.parse("b")]) == {
                                 provider.find("a")[Version(1, 0, 0)],
                                 provider.find("b")[Version(0, 0, 0)],
                                 provider.find("c")[Version(0, 0, 0)],
                             }


def test_provider_newest_incompatible():
    provider = StaticPackageProvider([
        Package('a', [(Version(0, 0, 0), [
            Requirement.parse("b"),
            Requirement.parse("c"),
        ])]),
        Package(
            'b',
            [
                (
                    Version(1, 0, 0),
                    [
                        Requirement.parse("c = 1"),  # Incompatible
                    ]),
                (Version(0, 0, 0), [])
            ]),
        Package('c', [(Version(0, 0, 0), [])]),
    ])

    assert provider.resolve([Requirement.parse("a")]) == {
        provider.find("a")[Version(0, 0, 0)],
        provider.find("b")[Version(0, 0, 0)],
        provider.find("c")[Version(0, 0, 0)],
    }
