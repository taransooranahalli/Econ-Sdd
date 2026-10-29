"""User-operated local setup: hidden keys; no network, order or account requests."""
import argparse
import getpass
import json
import os
import sys
from uuid import UUID

from .config import profile_path
from ..accounts import AccountStore, default_paths, valid_username, AccountError
from ..security import Keyring, VaultError


def main():
    parser = argparse.ArgumentParser(description='Configure personal Alpaca paper market-data access locally; keys are hidden.')
    parser.add_argument('command', choices=['setup'])
    parser.add_argument('--username', required=True, help='Your existing Finance account username')
    parser.add_argument('--replace', action='store_true', help='Replace an existing local Alpaca profile')
    args = parser.parse_args()
    if not sys.stdin.isatty():
        parser.error('Run setup in your own interactive terminal so key input stays hidden.')
    destination = profile_path()
    if destination.exists() and not args.replace:
        parser.error('A profile already exists. Use --replace to replace it deliberately.')
    try:
        login = valid_username(args.username)
        database, key_file = default_paths()
        if not database.exists() or not key_file.exists():
            parser.error('Initialize Finance accounts and create your local account first.')
        store = AccountStore(database, Keyring.load(key_file))
        with store.db() as connection:
            row = connection.execute('SELECT id FROM users WHERE login_index=?', (store.keys.index('username',login),)).fetchone()
        if row is None:
            parser.error('This Finance account was not found. Create it in the local app first.')
        owner = str(UUID(row['id']))
        print('Use Alpaca PAPER API keys. No trading, funding or position synchronization is performed.')
        print('Confirm that your Alpaca agreement permits this personal local display. Public redistribution is separate.')
        if input('Personal display access confirmed? [y/N] ').strip().lower() != 'y':
            parser.exit(0, 'No profile written.\n')
        key = getpass.getpass('Alpaca paper API key (hidden): ').strip()
        secret = getpass.getpass('Alpaca paper secret (hidden): ').strip()
        if not all(8 <= len(value) <= 256 and value.isascii() and value.isalnum() for value in (key,secret)):
            parser.error('Keys must contain 8–256 ASCII letters/digits. No profile written.')
        data = {'schema_version':1,'owner_id':owner,'key':key,'secret':secret,'personal_display_confirmed':True}
        destination.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
        # Write a new private inode before replacing; never follow an existing file symlink.
        temporary = destination.with_name('alpaca.pending')
        descriptor = os.open(temporary, os.O_WRONLY|os.O_CREAT|os.O_EXCL, 0o600)
        try:
            with os.fdopen(descriptor,'w') as stream:
                json.dump(data,stream)
            os.replace(temporary,destination)
        finally:
            temporary.unlink(missing_ok=True)
        print('Private profile saved. Restart Finance and sign in to Stocks. Live access is verified on your first request.')
    except (AccountError, OSError, VaultError):
        parser.exit(1, 'Local setup could not be completed. Check the account storage and private folder permissions.\n')


if __name__ == '__main__':
    main()
