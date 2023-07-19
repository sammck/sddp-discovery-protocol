# Copyright (c) 2022 Samuel J. McKelvie
#
# MIT License - See LICENSE file accompanying this package.
#

"""Configuration support for SqlKvStore."""

from typing import Optional

import os

from ..util import full_type
from .store import KvStoreConfig, KvStore
from ..sql_store import SqlKvStore, SqlConnection
import sqlcipher3 # type: ignore
#import sqlite3

class SqlKvStoreConfig(KvStoreConfig):
  _db_file_name: Optional[str] = None

  def bake(self):
    super().bake()
    self._db_file_name = os.path.abspath(os.path.expanduser(self.get_cfg_property_str('file_name')))

  def open_store(self, create: bool=False, create_only: bool=False, erase: bool=False, passphrase: Optional[str]=None) -> KvStore:
    create = create or create_only
    file_name = self._db_file_name
    assert not file_name is None
    if passphrase is None:
      if not self._passphrase_cfg is None:
        passphrase = self._passphrase_cfg.get_passphrase()

    if os.path.exists(file_name):
      if create_only:
        raise FileExistsError(f"SqlKvStoreConfig: Database file already exists: {file_name}")
      if erase:
        os.remove(file_name)
    else:
      if not create:
        raise FileNotFoundError(f"SqlKvStoreConfig: Database file does not exist: {file_name}")

    db: SqlConnection = sqlcipher3.connect(file_name)
    store = SqlKvStore(store_name=file_name, db=db, passphrase=passphrase)
    store.init_db()
    return store

  def delete_store(self):
    file_name = self._db_file_name
    if not file_name is None:
      os.remove(file_name)
