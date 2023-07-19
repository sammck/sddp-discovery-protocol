# Copyright (c) 2022 Samuel J. McKelvie
#
# MIT License - See LICENSE file accompanying this package.
#

"""Configuration support for retrieving a secret passphrase."""

from typing import Optional, Dict, TextIO
from ..internal_types import JsonableDict

import keyring

from ..util import full_name_of_type, full_type
from .base import Config

class PassphraseConfig(Config):
  _default_passphrase_cfg: Optional['PassphraseConfig'] = None

  def bake(self):
    default_cfg_data = self.get_template_cfg_property('default_passphrase_cfg', None)
    if not default_cfg_data is None:
      self._default_passphrase_cfg = self._context.load_json_data(default_cfg_data)

  def get_passphrase(self) -> str:
    raise NotImplementedError(f"{full_type(self)} does not implement get_passphrase")

  def set_passphrase(self, s: str):
    raise NotImplementedError(f"{full_type(self)} does not implement set_passphrase")

  def delete_passphrase(self):
    raise NotImplementedError(f"{full_type(self)} does not implement delete_passphrase")

  def passphrase_exists(self) -> bool:
    try:
      self.get_passphrase()
    except KeyError:
      return False

    return True
