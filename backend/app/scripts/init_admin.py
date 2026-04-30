"""Helper to print bcrypt hash for ADMIN_PASSWORD_HASH env var."""
import argparse
import getpass
import sys

from app.auth.password import hash_password


def build_password_hash(plain: str) -> str:
    return hash_password(plain)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--password", help="Password (omit to read interactively)")
    args = parser.parse_args(argv)
    plain = args.password or getpass.getpass("Admin password: ")
    print(build_password_hash(plain))
    return 0


if __name__ == "__main__":
    sys.exit(main())
