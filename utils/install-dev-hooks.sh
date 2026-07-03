#!/bin/sh
set -eu

repo_root="$(git rev-parse --show-toplevel)"
hook_dir="$repo_root/.git/hooks"
hook_path="$hook_dir/pre-push"

mkdir -p "$hook_dir"

if [ -f "$hook_path" ] && ! grep -q "utils/audit_guard.py" "$hook_path"; then
  mv "$hook_path" "$hook_path.bak"
fi

cat > "$hook_path" <<'EOF'
#!/bin/sh
set -eu

repo_root="$(git rev-parse --show-toplevel)"
exec python3 "$repo_root/utils/audit_guard.py" --repo "$repo_root"
EOF

chmod +x "$hook_path"
printf '%s\n' "Installed pre-push audit guard at $hook_path"
