# Factorio Mod Manager

A command-line tool for managing Factorio mods with dependency resolution and version locking, intended especially for server admins.

## Why?

Currently the best way to install mods for a server is to install them locally on using the client and then copy the mods folder to the server.
This is both hard to automate and to ensure reproducibility.
This tool solves both of these problems by providing a simple command-line tool for installing mods and a lock file for reproducibility.

## Features

- Automatic dependency resolution
- Lock file for reproducible mod installations
- Integration with Nix package manager

## Installation

```bash
git clone https://github.com/henkkuli/Factorio-Mod-Manager
pip install requests
```

## Usage

### Basic Setup

1. Create a `factorio-mods.txt` file listing your desired mods:
```
DiscoScience          # Any version of DiscoScience
pymodpack >= 3.0.0    # A recent version of Pyanodons
```
The mod list supports [all version selectors supported by Factorio](https://wiki.factorio.com/Tutorial:Mod_structure#dependencies).
In particular, if you want to install a install a specific version of the mod, use `=`, and to install a specific or newer version of the mod, use `>=`.

2. Update the lock file:
```bash
./fmm.py update
```

3. Install mods using your Factorio.com credentials:
```bash
./fmm.py install --username <your-username> --token <your-token>
```
You can find the token on [your Factorio.com profile page](https://factorio.com/profile).

### Nix Integration

For Nix users, use `--nix-prefetch` download the mods to your Nix store instead of storing them in the `mods/` directory.
This allows you to download the mods to the store without storing your secret token in the store in a world-readable format.

```bash
./fmm.py install --username USER --token TOKEN --nix-prefetch
```

## License

Factorio Mod Manager Copyright (C) 2025 Henrik Lievonen
This program comes with ABSOLUTELY NO WARRANTY.
This is free software, and you are welcome to redistribute it
under certain conditions.

Factorio Mod Manager for locking and downloading mods for Factorio game.
Copyright (C) 2025 Henrik Lievonen

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
