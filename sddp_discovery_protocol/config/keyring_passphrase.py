# Copyright (c) 2022 Samuel J. McKelvie
#
# MIT License - See LICENSE file accompanying this package.
#

"""Configuration support for retrieving a secret passphrase."""

from typing import Optional
from ..internal_types import JsonableDict

import keyring

from ..util import full_name_of_type
from .base import Config
from .passphrase import PassphraseConfig

class KeyringPassphraseConfig(PassphraseConfig):
  _keyring_service: Optional[str] = None
  _keyring_key: Optional[str] = None
  
  def bake(self):
    super().bake()
    self._keyring_service = self.get_cfg_property_str('service')
    self._keyring_key = self.get_cfg_property_str('key')
    default_cfg_data = self.get_cfg_property('default_passphrase_cfg', None)
    if not default_cfg_data is None:
      self._default_passphrase_cfg = self._context.load_json_data(default_cfg_data)

  def get_passphrase(self) -> str:
    assert not self._keyring_service is None
    assert not self._keyring_key is None
    result = keyring.get_password(self._keyring_service, self._keyring_key)
    if result is None:
      if self._default_passphrase_cfg is None:
        raise KeyError(f"KeyringPassphraseConfig: service '{self._keyring_service}', key name '{self._keyring_key}' does not exist")
      else:
        try:
          result = self._default_passphrase_cfg.get_passphrase()
        except KeyError as e:
          raise KeyError(f"KeyringPassphraseConfig: service '{self._keyring_service}', key name '{self._keyring_key}' does not exist") from e

    return result

  def set_passphrase(self, s: str):
    assert not self._keyring_service is None
    assert not self._keyring_key is None
    keyring.set_password(self._keyring_service, self._keyring_key, s)

  def delete_passphrase(self):
    assert not self._keyring_service is None
    assert not self._keyring_key is None
    keyring.delete_password(self._keyring_service, self._keyring_key)
