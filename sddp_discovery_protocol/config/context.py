# Copyright (c) 2022 Samuel J. McKelvie
#
# MIT License - See LICENSE file accompanying this package.
#

"""Configuration context."""

from tty import CFLAG
from typing import Optional, Dict, Any, TYPE_CHECKING, TextIO, Type, TypeVar, overload

from ..util import full_name_of_type, full_type, hash_pathname as g_hash_pathname
from ..internal_types import Jsonable, JsonableDict

if TYPE_CHECKING:
  from .base import Config

import os
import json
from collections import UserDict
from copy import copy, deepcopy
from string import Template
import importlib
import hashlib

class ConfigDict(UserDict):
  pass

  # _T = TypeVar('_T', bound='ConfigDict')
  # def __deepcopy__(self: _T) -> _T:
  #   pass

_T = TypeVar('_T')

class ConfigContext(ConfigDict):
  def __init__(self, globals: Optional[Dict[str, Any]]=None, os_environ: Optional[Dict[str, str]]=None):
    super().__init__()
    if not globals is None:
      globals = deepcopy(globals)
      self.update(globals)
    if os_environ is None:
      # NOTE: not thread safe if anyone is calling setvar
      os_environ = dict(os.environ)
    for k, v in os_environ.items():
      self[f"env:{k}"] = v

  def clone(self) -> 'ConfigContext':
    result = deepcopy(self)
    return result

  def render_template_str(self, template_str: str) -> str:
    t: Template = Template(template_str)
    result: str = t.substitute(self)
    return result

  def render_template_json_data(
        self,
        template_json_data: Jsonable,
        *args,
        **kwargs
      ) -> Jsonable:
    template_str = json.dumps(template_json_data)
    json_text: str = self.render_template_str(template_str)
    result: Jsonable = json.loads(json_text)
    return result

  _Config=TypeVar('_Config', bound='Config')
  @overload
  def instantiate_config(self, class_name: str) -> 'Config': ...
  @overload
  def instantiate_config(self, class_name: str, required_type: Optional[Type[_Config]]) -> _Config: ...
  def instantiate_config(self, class_name: str, required_type: Optional[Type['Config']]=None) -> 'Config':
    from .base import Config
    if required_type is None:
      required_type = Config
    assert issubclass(required_type, Config)
    class_parts = class_name.rsplit('.', 1)
    module_name: str
    if len(class_parts) > 1:
      module_name, class_tail = class_parts
    else:
      from .. import config as config_module
      module_name = config_module.__name__
      class_tail = class_name
    module = importlib.import_module(module_name)
    klass = getattr(module, class_tail)
    if not issubclass(klass, required_type):
      raise RuntimeError(f"Config: {full_name_of_type(klass)} is not a subclass of required type {full_name_of_type(required_type)}")
    assert issubclass(klass, Config)
    cfg  = klass()
    assert issubclass(klass, required_type)
    return cfg

  def hash_pathname(self, pathname: str) -> str:
    return g_hash_pathname(pathname=pathname)

  def push_config_file(self, config_file: Optional[str]) -> 'ConfigContext':
    ctx = self.clone()
    ctx.set_config_file(config_file)
    return ctx

  @property
  def config_file(self) -> Optional[str]:
    return self.get('config_file', None)

  def set_config_file(self, config_file: Optional[str]=None):
    if config_file is None:
      for propname in ['config_file','config_dir','config_file_hash','config_dir_hash']:
        if propname in self:
          del self[propname]
    else:
      config_file = os.path.abspath(os.path.expanduser(config_file))
      config_dir = os.path.dirname(config_file)
      config_file_hash = self.hash_pathname(config_file)
      config_dir_hash = self.hash_pathname(config_dir)
      self['config_file'] = config_file
      self['config_dir'] = config_dir
      self['config_file_hash'] = config_file_hash
      self['config_dir_hash'] = config_dir_hash

  @property
  def config_dir(self) -> Optional[str]:
    return self.get('config_dir', None)

  @property
  def config_file_hash(self) -> Optional[str]:
    return self.get('config_file_hash', None)

  @property
  def config_dir_hash(self) -> Optional[str]:
    return self.get('config_dir_hash', None)

  @overload
  def loads(self, s: str) -> 'Config': ...
  @overload
  def loads(self, s: str, required_type: Optional[Type[_Config]]) -> _Config: ...
  def loads(self, s: str, required_type: Optional[Type['Config']]=None) -> 'Config':
    data: Jsonable = json.loads(s)
    ctx = self

    if not isinstance(data, dict):
      raise ValueError(f"ConfigContext: expected json dict, got {full_type(data)}")
    if 'version' in data:
      version_s = data['version']
      if not isinstance(version_s, str):
        raise ValueError(f"ConfigContext: expected str version, got {full_type(version_s)}")
      version = tuple(int(x) for x in version_s.split('.'))
      from .. import __version__ as my_version_s
      my_version = tuple(int(x) for x in my_version_s.split('.'))
      if version > my_version:
        raise RuntimeError(f"ConfigContext: configuration version {version_s} is newer than ConfigContext version {my_version_s}")
    cfg_class_name = data['cfg_class']
    if not isinstance(cfg_class_name, str):
      raise ValueError(f"ConfigContext: expected str cfg_class, got {full_type(cfg_class_name)}")
    cfg_data: Jsonable = data.get('data', {})
    if not isinstance(cfg_data, (dict, str)):
      raise ValueError(f"ConfigContext: expected dict or str data, got {full_type(cfg_data)}")
    cfg = self.instantiate_config(cfg_class_name, required_type=required_type)
    if isinstance(cfg_data, str):
      cfg.loads(ctx, cfg_data)
    else:
      cfg.load_json_data(ctx, cfg_data)
    return cfg

  @overload
  def load_json_data(self, data: Jsonable) -> 'Config': ...
  @overload
  def load_json_data(self, data: Jsonable, required_type: Optional[Type[_Config]]) -> _Config: ...
  def load_json_data(self, data: Jsonable, required_type: Optional[Type['Config']]=None) -> 'Config':
    s = json.dumps(data)
    cfg = self.loads(s, required_type=required_type)
    return cfg

  @overload
  def load_stream(self, stream: TextIO) -> 'Config': ...
  @overload
  def load_stream(self, stream: TextIO, required_type: Optional[Type[_Config]]) -> _Config: ...
  def load_stream(self, stream: TextIO, required_type: Optional[Type['Config']]=None) -> 'Config':
    s = stream.read()
    cfg = self.loads(s, required_type=required_type)
    return cfg

  @overload
  def load_file(self, config_file: str) -> 'Config': ...
  @overload
  def load_file(self, config_file: str, required_type: Optional[Type[_Config]]) -> _Config: ...
  def load_file(self, config_file: str, required_type: Optional[Type['Config']]=None) -> 'Config':
    ctx = self.push_config_file(config_file)
    with open(config_file) as f:
      cfg = ctx.load_stream(f, required_type=required_type)
    return cfg
