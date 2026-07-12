# Install

v0.2 keeps the installer focused on the remaining frame-* skill family and the shared runtime scaffolding.

## Profiles

### Full

```bash
python3 install.py --repo /path/to/repository
```

### Routing

```bash
python3 install.py --repo /path/to/repository --profile routing
```

The routing profile installs the frame-* skills and the files needed for local routing and audit checks. It does not install the removed loop-control skills, OKF engine artifacts, or old v0.1 role docs.

### Global dispatcher

Install a `loopeng` command that dispatches to the nearest managed repository:

```bash
python3 install.py --install-command
python3 install.py --install-command /custom/bin
```

The dispatcher searches upward from the current directory for `loopeng/__main__.py` and runs that repository's `loopeng.py` (falling back to `python3 -m loopeng` if the launcher is absent). It does not modify shell startup files. An existing command is preserved and causes exit 2; use `--force` to replace it. If the destination directory is not on `PATH`, the installer reports that fact without editing any rc file.

### Self update

```bash
python3 install.py --repo .
python3 install.py --self --update
```

Use the self-update flow from the repository root when you are updating the kit from itself.

## Layout rule

`adapters/shared/skills/` is the source of truth for shared skills. `install.py --self --update` is the distribution path. In v0.2, only frame-* skills remain in the shared skill set.
