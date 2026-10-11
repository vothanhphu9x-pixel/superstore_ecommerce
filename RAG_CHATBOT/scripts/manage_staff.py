from __future__ import annotations

import argparse
import getpass
import sys

from core.internal_auth import (
    STAFF_ROLES,
    change_staff_password,
    change_staff_role,
    create_staff_user,
    list_staff_users,
    set_staff_active,
)


def _password_twice() -> str:
    password = getpass.getpass("Password: ")
    confirmation = getpass.getpass("Confirm password: ")

    if password != confirmation:
        raise ValueError("Passwords do not match")

    if len(password) < 12:
        raise ValueError("Password must contain at least 12 characters")

    return password


def command_add(args: argparse.Namespace) -> None:
    password = _password_twice()

    user = create_staff_user(
        email=args.email,
        name=args.name,
        role=args.role,
        password=password,
        replace=args.replace,
    )

    print(
        f"Saved staff user: {user['email']} "
        f"({user['role']}, active={user['active']})"
    )


def command_list(_: argparse.Namespace) -> None:
    users = list_staff_users()

    if not users:
        print("No staff users found")
        return

    print(
        f"{'EMAIL':35} {'ROLE':12} {'ACTIVE':8} "
        f"{'VERSION':8} NAME"
    )

    for user in users:
        print(
            f"{user['email']:35} "
            f"{user['role']:12} "
            f"{str(user['active']):8} "
            f"{user['auth_version']:<8} "
            f"{user['name']}"
        )


def command_password(args: argparse.Namespace) -> None:
    password = _password_twice()
    change_staff_password(args.email, password)
    print(f"Password changed: {args.email}")


def command_role(args: argparse.Namespace) -> None:
    change_staff_role(args.email, args.role)
    print(f"Role changed: {args.email} -> {args.role}")


def command_enable(args: argparse.Namespace) -> None:
    set_staff_active(args.email, True)
    print(f"Staff user enabled: {args.email}")


def command_disable(args: argparse.Namespace) -> None:
    set_staff_active(args.email, False)
    print(f"Staff user disabled: {args.email}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Manage internal staff accounts"
    )

    subparsers = parser.add_subparsers(
        dest="command",
        required=True,
    )

    add_parser = subparsers.add_parser("add")
    add_parser.add_argument("email")
    add_parser.add_argument("--name", required=True)
    add_parser.add_argument(
        "--role",
        required=True,
        choices=sorted(STAFF_ROLES),
    )
    add_parser.add_argument("--replace", action="store_true")
    add_parser.set_defaults(handler=command_add)

    list_parser = subparsers.add_parser("list")
    list_parser.set_defaults(handler=command_list)

    password_parser = subparsers.add_parser("password")
    password_parser.add_argument("email")
    password_parser.set_defaults(handler=command_password)

    role_parser = subparsers.add_parser("role")
    role_parser.add_argument("email")
    role_parser.add_argument(
        "role",
        choices=sorted(STAFF_ROLES),
    )
    role_parser.set_defaults(handler=command_role)

    enable_parser = subparsers.add_parser("enable")
    enable_parser.add_argument("email")
    enable_parser.set_defaults(handler=command_enable)

    disable_parser = subparsers.add_parser("disable")
    disable_parser.add_argument("email")
    disable_parser.set_defaults(handler=command_disable)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    try:
        args.handler(args)
    except (ValueError, RuntimeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())