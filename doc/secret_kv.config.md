# secret_kv.config package

## Submodules

## secret_kv.config.base module

Configuration support.


### _class_ secret_kv.config.base.Config()
Bases: `object`


#### bake()

#### _property_ config_dir(_: Optional[str_ )
The fully qualified pathname of the directory containing the configuration
file from which this Config originated, or None if not from a file


#### _property_ config_file(_: Optional[str_ )
The fully qualified pathname of the configuration file from which this Config
originated, or None if not from a file


#### get_cfg_property(key: str, default: secret_kv.config.base._T)

#### get_cfg_property(key: str)

#### get_cfg_property_dict(key: str, default: secret_kv.config.base._T)

#### get_cfg_property_dict(key: str)

#### get_cfg_property_int(key: str, default: secret_kv.config.base._T)

#### get_cfg_property_int(key: str)

#### get_cfg_property_str(key: str, default: secret_kv.config.base._T)

#### get_cfg_property_str(key: str)

#### get_context()

#### get_template_cfg_property(key: str, default: secret_kv.config.base._T)

#### get_template_cfg_property(key: str)

#### _classmethod_ hash_pathname(pathname: str)

#### _classmethod_ instantiate_config(class_name: str)

#### load_json_data(ctx: secret_kv.config.context.ConfigContext, json_data: Dict[str, Union[str, int, float, bool, None, Dict[str, Union[str, int, float, bool, None, Dict[str, Jsonable], List[Jsonable]]], List[Union[str, int, float, bool, None, Dict[str, Jsonable], List[Jsonable]]]]])

#### loads(ctx: secret_kv.config.context.ConfigContext, config_text: str)

#### render()

#### render_and_bake(context: secret_kv.config.context.ConfigContext)
## secret_kv.config.context module

Configuration context.


### _class_ secret_kv.config.context.ConfigContext(globals: Optional[Dict[str, Any]] = None, os_environ: Optional[Dict[str, str]] = None)
Bases: `secret_kv.config.context.ConfigDict`


#### clone()

#### _property_ config_dir(_: Optional[str_ )

#### _property_ config_dir_hash(_: Optional[str_ )

#### _property_ config_file(_: Optional[str_ )

#### _property_ config_file_hash(_: Optional[str_ )

#### hash_pathname(pathname: str)

#### instantiate_config(class_name: str)

#### instantiate_config(class_name: str, required_type: Optional[Type[_Config]])

#### load_file(config_file: str)

#### load_file(config_file: str, required_type: Optional[Type[_Config]])

#### load_json_data(data: Union[str, int, float, bool, None, Dict[str, Jsonable], List[Jsonable]])

#### load_json_data(data: Union[str, int, float, bool, None, Dict[str, Jsonable], List[Jsonable]], required_type: Optional[Type[_Config]])

#### load_stream(stream: TextIO)

#### load_stream(stream: TextIO, required_type: Optional[Type[_Config]])

#### loads(s: str)

#### loads(s: str, required_type: Optional[Type[_Config]])

#### push_config_file(config_file: Optional[str])

#### render_template_json_data(template_json_data: Union[str, int, float, bool, None, Dict[str, Union[str, int, float, bool, None, Dict[str, Jsonable], List[Jsonable]]], List[Union[str, int, float, bool, None, Dict[str, Jsonable], List[Jsonable]]]], \*args, \*\*kwargs)

#### render_template_str(template_str: str)

#### set_config_file(config_file: Optional[str] = None)

### _class_ secret_kv.config.context.ConfigDict(dict=None, /, \*\*kwargs)
Bases: `collections.UserDict`

## secret_kv.config.keyring_passphrase module

Configuration support for retrieving a secret passphrase.


### _class_ secret_kv.config.keyring_passphrase.KeyringPassphraseConfig()
Bases: `secret_kv.config.passphrase.PassphraseConfig`


#### bake()

#### delete_passphrase()

#### get_passphrase()

#### set_passphrase(s: str)
## secret_kv.config.passphrase module

Configuration support for retrieving a secret passphrase.


### _class_ secret_kv.config.passphrase.PassphraseConfig()
Bases: `secret_kv.config.base.Config`


#### bake()

#### delete_passphrase()

#### get_passphrase()

#### passphrase_exists()

#### set_passphrase(s: str)
## secret_kv.config.sql_store module

Configuration support for SqlKvStore.


### _class_ secret_kv.config.sql_store.SqlKvStoreConfig()
Bases: `secret_kv.config.store.KvStoreConfig`


#### bake()

#### delete_store()

#### open_store(create: bool = False, create_only: bool = False, erase: bool = False, passphrase: Optional[str] = None)
## secret_kv.config.store module

Configuration support for KvStore.


### _class_ secret_kv.config.store.KvStoreConfig()
Bases: `secret_kv.config.base.Config`


#### bake()

#### delete_store()

#### get_passphrase()

#### open_store(create: bool = False, create_only: bool = False, erase: bool = False, passphrase: Optional[str] = None)
## Module contents
