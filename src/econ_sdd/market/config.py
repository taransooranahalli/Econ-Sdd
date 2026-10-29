"""Private local profile; never expose keys via status, repr or browser forms."""
import json
from pathlib import Path
import stat
from uuid import UUID
from .alpaca import Profile, unique_object


def profile_path():
    from ..accounts import default_paths
    return default_paths()[1].parent/'alpaca.json'


def load_profile(path=None):
    path = Path(path) if path else profile_path()
    if not path.exists():
        return None, False
    try:
        info = path.lstat()
        if path.is_symlink() or not stat.S_ISREG(info.st_mode) or info.st_size > 16384 or stat.S_IMODE(info.st_mode)&0o077:
            raise ValueError
        data = json.loads(path.read_text(), object_pairs_hook=unique_object)
        if set(data) != {'schema_version','owner_id','key','secret','personal_display_confirmed'} or type(data['schema_version']) is not int or data['schema_version'] != 1 or data['personal_display_confirmed'] is not True:
            raise ValueError
        owner = str(UUID(data['owner_id']))
        for name in ('key','secret'):
            if not isinstance(data[name], str) or not 8 <= len(data[name]) <= 256 or not data[name].isascii() or not data[name].isalnum():
                raise ValueError
        return Profile(owner, data['key'], data['secret']), False
    except (ValueError, OSError, TypeError, KeyError, AttributeError):
        return None, True
