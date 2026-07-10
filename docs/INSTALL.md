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

### Self update

```bash
python3 install.py --repo .
python3 install.py --self --update
```

Use the self-update flow from the repository root when you are updating the kit from itself.

## Layout rule

`adapters/shared/skills/` is the source of truth for shared skills. `install.py --self --update` is the distribution path. In v0.2, only frame-* skills remain in the shared skill set.
