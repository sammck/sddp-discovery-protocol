# Copyright (c) 2022 Samuel J. McKelvie
#
# MIT License - See LICENSE file accompanying this package.
#

"""Configuration support for KvStore."""

from typing import Optional

from ..util import full_type
from .base import Config
from .passphrase import PassphraseConfig
from ..store import KvStore

class KvStoreConfig(Config):
  _passphrase_cfg: Optional[PassphraseConfig] = None

  def bake(self) -> None:
    context = self.get_context()
    passphrase_cfg_data = self.get_template_cfg_property('passphrase_cfg', None)
    if not passphrase_cfg_data is None:
      self._passphrase_cfg = context.load_json_data(passphrase_cfg_data, required_type=PassphraseConfig)

  def open_store(self, create: bool=False, create_only: bool=False, erase: bool=False, passphrase: Optional[str]=None) -> KvStore:
    raise NotImplementedError(f"{full_type(self)} does not implement open_store")

  def delete_store(self) -> None:
    raise NotImplementedError(f"{full_type(self)} does not implement delete_store")

  def get_passphrase(self) -> Optional[str]:
    result: Optional[str]
    if self._passphrase_cfg is None:
      result = None
    else:
      result = self._passphrase_cfg.get_passphrase()
    return result
