# Installation

[Documentation index](README.md)

## Requirements

- Python 3.13 or newer.
- A local checkout of this repository.
- uv, or pip in a Python virtual environment.
- Network access for DNS resolution and outbound SMTP connections on TCP port 25.

The runtime dependencies are `dnspython` and `validators`. Installing the project
also installs these dependencies. The CLI uses Python's built-in `smtplib` for SMTP.

Some networks restrict outbound port 25. A working internet connection alone
does not establish that SMTP checks can run; see [troubleshooting](troubleshooting.md).

## Install with uv

Run these commands from the repository root:

```sh
uv sync --locked
uv run addrck --help
```

This creates the project environment in `.venv`, installs addrck and its
development dependencies, and uses the versions recorded in `uv.lock`.
The repository's `.python-version` selects Python 3.13 by default.

To install and run only the runtime dependencies:

```sh
uv sync --locked --no-dev
uv run --no-dev addrck --help
```

Keep `--no-dev` on subsequent `uv run` commands if you want to avoid installing
the development group. The other guides use the default uv environment.

## Install with pip

Using Python 3.13 or newer, run from the repository root on a POSIX shell:

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install .
addrck --help
```

On Windows, activate the environment with `.venv\Scripts\Activate.ps1` in
PowerShell instead. The pip installation installs the command and runtime
dependencies; it does not use `uv.lock` or install the development group.

## Check your installation

`addrck --help` should show two positional arguments, `sender` and `recipient`,
and the `--verbose` and `--timeout` options. With uv, prefix the command with
`uv run` so it runs inside the project environment.

Help does not perform DNS lookups or connect to an SMTP server. To run an actual
check, follow the [usage guide](usage.md).
