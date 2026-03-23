"""Deprecated legacy bootstrap script.

GhostShelf now authenticates against existing Wizarr-linked accounts using the
same username/password users already created upstream. This script no longer
creates synthetic token-based users.
"""


def init_admin():
    """Legacy no-op kept for compatibility with older deployment scripts."""
    print("GhostShelf no longer creates a default token-based admin user.")
    print("Use an existing Wizarr-linked account to sign in to GhostShelf.")
    return None


if __name__ == "__main__":
    init_admin()
