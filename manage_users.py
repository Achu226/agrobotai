"""
Manage AGROBOTAI accounts on the server laptop.

    .venv\\Scripts\\python.exe manage_users.py create-admin        (prompts for username + password)
    .venv\\Scripts\\python.exe manage_users.py create-farmer
    .venv\\Scripts\\python.exe manage_users.py list
    .venv\\Scripts\\python.exe manage_users.py reset-password <username>
    .venv\\Scripts\\python.exe manage_users.py ensure-admin         (used by start.bat on first run)

Administrator accounts can only be created here, on the laptop. The mobile app can only
self-register farmer accounts (and only while ALLOW_FARMER_SIGNUP=true in .env).
Passwords are typed into the terminal (hidden) and stored as salted PBKDF2 hashes.
"""
from __future__ import annotations

import getpass
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from fastapi import HTTPException  # noqa: E402

from src import auth, store  # noqa: E402


def _prompt_new(role: str):
    username = input(f"New {role} username: ").strip()
    full_name = input("Full name (optional): ").strip()
    while True:
        password = getpass.getpass(f"Password (min {auth.MIN_PASSWORD_LEN} chars, hidden): ")
        if password != getpass.getpass("Repeat password: "):
            print("Passwords do not match, try again.")
            continue
        try:
            auth.validate_new_credentials(username, password)
        except HTTPException as exc:
            print(exc.detail)
            if "Username" in exc.detail:
                username = input(f"New {role} username: ").strip()
            continue
        break
    if store.get_user_auth(username):
        sys.exit(f"User '{username}' already exists.")
    user = store.create_user(username, auth.hash_password(password), role, full_name)
    print(f"Created {role} '{user['username']}' (id {user['id']}).")


def main(argv: list[str]) -> int:
    store.migrate()
    cmd = argv[1] if len(argv) > 1 else "help"
    if cmd == "create-admin":
        _prompt_new("admin")
    elif cmd == "create-farmer":
        _prompt_new("farmer")
    elif cmd == "ensure-admin":
        if store.count_admins() == 0:
            print("No administrator account exists yet. Create one now (needed to review scans).")
            _prompt_new("admin")
        else:
            print(f"[OK] {store.count_admins()} administrator account(s) configured.")
    elif cmd == "list":
        for u in store.list_users():
            print(f"{u['id']:>4}  {u['role']:<7} {u['username']:<20} {u['full_name']:<25} scans={u['scan_count']} active={u['is_active']}")
        if not store.list_users():
            print("No users yet.")
    elif cmd == "reset-password" and len(argv) > 2:
        found = store.get_user_auth(argv[2])
        if not found:
            sys.exit(f"No user named '{argv[2]}'.")
        password = getpass.getpass("New password (hidden): ")
        if password != getpass.getpass("Repeat password: "):
            sys.exit("Passwords do not match.")
        auth.validate_new_credentials(found[0]["username"], password)
        store.set_password(found[0]["id"], auth.hash_password(password))
        print("Password updated; existing sessions for this user were signed out.")
    else:
        print(__doc__)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
