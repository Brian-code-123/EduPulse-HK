"""One-off utility: turn an admin password into a bcrypt hash to paste into
`.streamlit/secrets.toml` (local) or Streamlit Cloud's Secrets manager.

Holds no credentials itself — the password is typed interactively and never
written to this file, so it's safe to keep in the repo.

Usage: python generate_password_hash.py
"""

import getpass

import streamlit_authenticator as stauth


def main() -> None:
    password = getpass.getpass("Admin password to hash: ")
    print("\npassword_hash =", repr(stauth.Hasher.hash(password)))


if __name__ == "__main__":
    main()
