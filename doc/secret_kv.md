# secret_kv package

## Subpackages


* [secret_kv.config package](secret_kv.config.md)


    * [Submodules](secret_kv.config.md#submodules)


    * [secret_kv.config.base module](secret_kv.config.md#module-secret_kv.config.base)


    * [secret_kv.config.context module](secret_kv.config.md#module-secret_kv.config.context)


    * [secret_kv.config.keyring_passphrase module](secret_kv.config.md#module-secret_kv.config.keyring_passphrase)


    * [secret_kv.config.passphrase module](secret_kv.config.md#module-secret_kv.config.passphrase)


    * [secret_kv.config.sql_store module](secret_kv.config.md#module-secret_kv.config.sql_store)


    * [secret_kv.config.store module](secret_kv.config.md#module-secret_kv.config.store)


    * [Module contents](secret_kv.config.md#module-secret_kv.config)


## Submodules

## secret_kv.constants module

Constants used by secret_kv

## secret_kv.exceptions module

Exceptions defined by this package


### _exception_ secret_kv.exceptions.KvError()
Bases: `Exception`

Base class for all error exceptions defined by this package.


### _exception_ secret_kv.exceptions.KvNoEnumerationError()
Bases: `secret_kv.exceptions.KvError`

Exception indicating failure because the KvStore does not support enumeration of keys.


### _exception_ secret_kv.exceptions.KvNoPassphraseError()
Bases: `secret_kv.exceptions.KvError`, `KeyError`

Exception indicating failure because a passphrase was not provided.


### _exception_ secret_kv.exceptions.KvReadOnlyError()
Bases: `secret_kv.exceptions.KvError`

Exception indicating failure because the KvStore does not allow write operations.

## secret_kv.internal_types module

Type hints used internally by this package


### secret_kv.internal_types.Jsonable()
A Type hint for a simple JSON-serializable value; i.e., str, int, float, bool, None, Dict[str, Jsonable], List[Jsonable]

alias of `Union`[`str`, `int`, `float`, `bool`, `None`, `Dict`[`str`, `Jsonable`], `List`[`Jsonable`]]


### secret_kv.internal_types.JsonableDict()
A type hint for a simple JSON-serializable dict; i.e., Dict[str, Jsonable]

alias of `Dict`[`str`, `Union`[`str`, `int`, `float`, `bool`, `None`, `Dict`[`str`, `Jsonable`], `List`[`Jsonable`]]]


### secret_kv.internal_types.SqlConnection()
A type hint for a connection to an SQL database (possibly sqlite3 or sqlcipher3)


### secret_kv.internal_types.XJsonable()
A Type hint for an extended JSON-serializable value; i.e., str, int, float, bool, bytes, bytearray,XJsonSerializable, None, Dict[str, Jsonable], List[Jsonable]

alias of `Union`[`str`, `int`, `float`, `bool`, `bytes`, `bytearray`, `object`, `None`, `Mapping`[`str`, `XJsonable`], `Iterable`[`XJsonable`]]


### secret_kv.internal_types.XJsonableDict()
A type hint for an extended JSON-serializable dict; i.e., Mapping[str, XJsonable]

alias of `Mapping`[`str`, `Union`[`str`, `int`, `float`, `bool`, `bytes`, `bytearray`, `object`, `None`, `Mapping`[`str`, `XJsonable`], `Iterable`[`XJsonable`]]]

## secret_kv.sentinel module

Sentinel values


### _class_ secret_kv.sentinel.NothingType(name: str)
Bases: `secret_kv.sentinel.Sentinel`


### _class_ secret_kv.sentinel.Sentinel(name: str)
Bases: `object`


### secret_kv.sentinel.sentinel(name: str)
## secret_kv.simple module

Simplified instanciation, creation API for KvStore, an abstract key/value store.

A KvStore supports string keys, and rich value types including json-serializable data and binary data.
A mechanism is also provided to attach metadata to a key via named tags, which may themselves
have rich value types.


### secret_kv.simple.create_kv_store(parent_dir: str, passphrase: Optional[str] = None)

### secret_kv.simple.delete_kv_store(config_path: Optional[str] = None, scan_parent_dirs: bool = True)

### secret_kv.simple.get_kv_store_default_passphrase()

### secret_kv.simple.get_kv_store_default_passphrase_keyring_key()

### secret_kv.simple.get_kv_store_passphrase(config_file: str)

### secret_kv.simple.get_kv_store_passphrase_keyring_key(config_filename: str)

### secret_kv.simple.get_kv_store_passphrase_keyring_service()

### secret_kv.simple.load_any_config_file(config_file: str)

### secret_kv.simple.load_any_config_file(config_file: str, required_type: Type[secret_kv.simple._Config])

### secret_kv.simple.load_kv_store_config(config_path: Optional[str] = None, scan_parent_dirs: bool = True)

### secret_kv.simple.locate_kv_store_config_file(config_path: Optional[str] = None, scan_parent_dirs: bool = True)

### secret_kv.simple.open_kv_store(config_path: Optional[str] = None, scan_parent_dirs: bool = True, create_db: bool = False, create_db_only: bool = False, erase_db: bool = False, passphrase: Optional[str] = None)

### secret_kv.simple.set_kv_store_default_passphrase(passphrase: str)

### secret_kv.simple.set_kv_store_passphrase(config_file, passphrase: str)
## secret_kv.sql_store module


### _class_ secret_kv.sql_store.SqlKvStore(store_name: Optional[str] = None, db: Optional[sqlite3.Connection] = None, passphrase: Optional[str] = None)
Bases: `secret_kv.store.KvStore`


#### DB_APP_NAME(_ = 'SqlKvStore_ )

#### SCHEMA_VERSION(_: in_ _ = _ )

#### clear()

#### close()

#### _property_ db(_: Optional[sqlite3.Connection_ )

#### delete_tag(key, tag_name: str)

#### delete_value(key: str)

#### get_db()

#### get_num_tags(key: str)

#### get_tag(key: str, tag_name: str)

#### get_tags(key: str)

#### get_value(key: str)
Get the KvValue associated with a key, if it exists

Args:

    key (str): The key for which a KvValue is requested

Returns:

    Optional[KvValue]: The KvValue associated with the key, or None if the key does not exist.


#### get_value_and_tags(key: str)
Get a KvValue and all tags associated with a key, if it exists

Args:

    key (str): The key for which a KvValue and tags are requested

Returns:

    Tuple[Optional[KvValue], Dict[str, KvValue]]:

        A tuple with two values:

            [0]:  The KvValue associated with the key, or None if the key does not exist.
            [1]:  A dictionary mapping all tag names assocated with the key to their respective

            > tag KvValue. If the key does not exist, {} is returned.


#### has_key(key: str)

#### has_tag(key: str, tag_name: str)

#### init_db()

#### initialize_db_pragmas()

#### initialize_new_db()

#### items_with_tags()

#### iter_items()

#### iter_keys()

#### iter_values()

#### num_keys()

#### set_passhrase(passphrase: Optional[str])

#### set_tag(key, tag_name: str, value: Union[str, int, float, bool, bytes, bytearray, object, None, Mapping[str, Union[str, int, float, bool, bytes, bytearray, object, None, Mapping[str, XJsonable], Iterable[XJsonable]]], Iterable[Union[str, int, float, bool, bytes, bytearray, object, None, Mapping[str, XJsonable], Iterable[XJsonable]]]])

#### set_tags(key, tags: Mapping[str, Union[str, int, float, bool, bytes, bytearray, object, None, Mapping[str, Union[str, int, float, bool, bytes, bytearray, object, None, Mapping[str, XJsonable], Iterable[XJsonable]]], Iterable[Union[str, int, float, bool, bytes, bytearray, object, None, Mapping[str, XJsonable], Iterable[XJsonable]]]]], clear_tags: bool = False)

#### set_value(key: str, value: Union[str, int, float, bool, bytes, bytearray, object, None, Mapping[str, Union[str, int, float, bool, bytes, bytearray, object, None, Mapping[str, XJsonable], Iterable[XJsonable]]], Iterable[Union[str, int, float, bool, bytes, bytearray, object, None, Mapping[str, XJsonable], Iterable[XJsonable]]]])

#### set_value_and_tags(key: str, value: Union[str, int, float, bool, bytes, bytearray, object, None, Mapping[str, Union[str, int, float, bool, bytes, bytearray, object, None, Mapping[str, XJsonable], Iterable[XJsonable]]], Iterable[Union[str, int, float, bool, bytes, bytearray, object, None, Mapping[str, XJsonable], Iterable[XJsonable]]]], tags: Mapping[str, Union[str, int, float, bool, bytes, bytearray, object, None, Mapping[str, Union[str, int, float, bool, bytes, bytearray, object, None, Mapping[str, XJsonable], Iterable[XJsonable]]], Iterable[Union[str, int, float, bool, bytes, bytearray, object, None, Mapping[str, XJsonable], Iterable[XJsonable]]]]], clear_tags: bool = False)
Set the KvValue and tags associated with a key. If the key does not exist it is created.

Args:

    key (str): The key that is being created or updated.
    value (XJsonable): A KvValue or KvValue-Coercible value to assign to the key
    tags (Mapping[str, XJsonable]): A dict mapping tag names to KvValue-coercible tag values
    clear_tags (bool, optional): If true, any existing tags will be cleared before setting new tags. Defaults to False.

Raises:

    KvReadOnlyError: The KvStore does not support writing the requested values or keys


#### tag_items(key: str)

#### tag_names(key: str)

#### tag_values(key: str)
## secret_kv.store module

Base class definition for KvStore, an abstract key/value store.

A KvStore supports string keys, and rich value types including json-serializable data and binary data.
A mechanism is also provided to attach metadata to a key via named tags, which may themselves
have rich value types.

Subclasses of KvStore must override and implement a few get/set methods. Default implementations
are provided in the base class for most methods, and to provide a MutableMapping interface.


### _class_ secret_kv.store.KvStore(store_name: Optional[str] = None)
Bases: `MutableMapping`[`str`, `secret_kv.value.KvValue`]


#### _class_ KvStoreItemsView(kv_store: secret_kv.store.KvStore)
Bases: `ItemsView`[`str`, `secret_kv.value.KvValue`]


#### _class_ KvStoreKeysView(kv_store: secret_kv.store.KvStore)
Bases: `KeysView`[`str`]


#### _class_ KvStoreValuesView(kv_store: secret_kv.store.KvStore)
Bases: `ValuesView`[`secret_kv.value.KvValue`]


#### clear()

#### clear_tags(key: str)

#### close()

#### contains_item(item: object)

#### contains_value(value: object)

#### delete_tag(key, tag_name: str)

#### delete_value(key: str)

#### get_num_tags(key: str)

#### get_tag(key: str, tag_name: str)

#### get_tags(key: str)

#### get_value(key: str)
Get the KvValue associated with a key, if it exists

Args:

    key (str): The key for which a KvValue is requested

Returns:

    Optional[KvValue]: The KvValue associated with the key, or None if the key does not exist.


#### get_value_and_tags(key: str)
Get a KvValue and all tags associated with a key, if it exists

Args:

    key (str): The key for which a KvValue and tags are requested

Returns:

    Tuple[Optional[KvValue], Dict[str, KvValue]]:

        A tuple with two values:

            [0]:  The KvValue associated with the key, or None if the key does not exist.
            [1]:  A dictionary mapping all tag names assocated with the key to their respective

            > tag KvValue. If the key does not exist, {} is returned.


#### has_key(key: str)

#### has_tag(key: str, tag_name: str)

#### items()

#### items_with_tags()

#### iter_items()

#### iter_keys()

#### iter_values()

#### keys()

#### num_keys()

#### set_tag(key, tag_name: str, value: Union[str, int, float, bool, bytes, bytearray, object, None, Mapping[str, Union[str, int, float, bool, bytes, bytearray, object, None, Mapping[str, XJsonable], Iterable[XJsonable]]], Iterable[Union[str, int, float, bool, bytes, bytearray, object, None, Mapping[str, XJsonable], Iterable[XJsonable]]]])

#### set_tags(key, tags: Dict[str, Union[str, int, float, bool, bytes, bytearray, object, None, Mapping[str, Union[str, int, float, bool, bytes, bytearray, object, None, Mapping[str, XJsonable], Iterable[XJsonable]]], Iterable[Union[str, int, float, bool, bytes, bytearray, object, None, Mapping[str, XJsonable], Iterable[XJsonable]]]]], clear_tags: bool = False)

#### set_value(key: str, value: Union[str, int, float, bool, bytes, bytearray, object, None, Mapping[str, Union[str, int, float, bool, bytes, bytearray, object, None, Mapping[str, XJsonable], Iterable[XJsonable]]], Iterable[Union[str, int, float, bool, bytes, bytearray, object, None, Mapping[str, XJsonable], Iterable[XJsonable]]]])

#### set_value_and_tags(key: str, value: Union[str, int, float, bool, bytes, bytearray, object, None, Mapping[str, Union[str, int, float, bool, bytes, bytearray, object, None, Mapping[str, XJsonable], Iterable[XJsonable]]], Iterable[Union[str, int, float, bool, bytes, bytearray, object, None, Mapping[str, XJsonable], Iterable[XJsonable]]]], tags: Mapping[str, Union[str, int, float, bool, bytes, bytearray, object, None, Mapping[str, Union[str, int, float, bool, bytes, bytearray, object, None, Mapping[str, XJsonable], Iterable[XJsonable]]], Iterable[Union[str, int, float, bool, bytes, bytearray, object, None, Mapping[str, XJsonable], Iterable[XJsonable]]]]], clear_tags: bool = False)
Set the KvValue and tags associated with a key. If the key does not exist it is created.

Args:

    key (str): The key that is being created or updated.
    value (XJsonable): A KvValue or KvValue-Coercible value to assign to the key
    tags (Mapping[str, XJsonable]): A dict mapping tag names to KvValue-coercible tag values
    clear_tags (bool, optional): If true, any existing tags will be cleared before setting new tags. Defaults to False.

Raises:

    KvReadOnlyError: The KvStore does not support writing the requested values or keys


#### _property_ store_name(_: st_ )
The name of the store. Typically a pathname or URI.


#### tag_items(key: str)

#### tag_names(key: str)

#### tag_values(key: str)

#### update(\*\*F)
If E present and has a .keys() method, does:     for k in E: D[k] = E[k]
If E present and lacks .keys() method, does:     for (k, v) in E: D[k] = v
In either case, this is followed by: for k, v in F.items(): D[k] = v


#### values()
## secret_kv.util module

Miscellaneous utility functions


### secret_kv.util.clone_json_data(data: Union[str, int, float, bool, None, Dict[str, Union[str, int, float, bool, None, Dict[str, Jsonable], List[Jsonable]]], List[Union[str, int, float, bool, None, Dict[str, Jsonable], List[Jsonable]]]])
Makes a deep copy of a json-serializable value, by serializing and then unserializing.

Args:

    data (Jsonable): A JSON-serializable value

Raises:

    TypeError: If data is not serializable to JSON

Returns:

    Jsonable: A deep copy of the provided value, which can be modified without affecting the original.


### secret_kv.util.full_name_of_type(t: Type)
Returns the fully qualified name of a type

Args:

    t (Type): A type, which may be a builtin type or a class

Returns:

    str: The fully qualified name of the type


### secret_kv.util.full_type(o: Any)
Returns the fully qualified name of an object or value’s type

Args:

    o: any object or value

Returns:

    str: The fully qualified name of the object or value’s type


### secret_kv.util.hash_pathname(pathname: str)
## secret_kv.value module

Definition of KvValue, an abstraction for an immutable value that has a type and is is serializable to JSON.

Typical usage example:

a = KvValue(“foo”)
b = KvValue(7)
c = KvValue(dict(x=5, y=7))
d = KvValue([ 4, 5, 6])
e = KvValue(None)
f = KvValue(3.14159)
g = KvValue(b’binary data’)  # encoded as a base64 string

a_data = a.data
a_json_data = a.json_data
a_json_text = a.json_text


### _class_ secret_kv.value.KvValue(data: Union[str, int, float, bool, bytes, bytearray, object, None, Mapping[str, Union[str, int, float, bool, bytes, bytearray, object, None, Mapping[str, XJsonable], Iterable[XJsonable]]], Iterable[Union[str, int, float, bool, bytes, bytearray, object, None, Mapping[str, XJsonable], Iterable[XJsonable]]]])
Bases: `secret_kv.value.XJsonSerializable`

An immutable representation of a XJsonable value that is serializable to and from JSON.
Allows optional metadata to be attached.


#### as_simple_jsonable()

#### as_sortable_value()
Returns an opaque value that can be hashed or compared to similar values
for sorting and equality-testing purposes.

NOTE: this does not provide true ordinal sort order for scalar integers and floats. It

    simply sorts by serialized json string.

Returns:

    Tuple[str, str]: An opaque value that represents this KvValue in a way that can be compared/sorted


#### clone()

#### _property_ data(_: Union[str, int, float, bool, bytes, bytearray, object, None, Mapping[str, Union[str, int, float, bool, bytes, bytearray, object, None, Mapping[str, XJsonable], Iterable[XJsonable]]], Iterable[Union[str, int, float, bool, bytes, bytearray, object, None, Mapping[str, XJsonable], Iterable[XJsonable]]]_ )
The extended JSON-serializable value. Must not be modified.


#### _property_ json_data(_: Union[str, int, float, bool, None, Dict[str, Union[str, int, float, bool, None, Dict[str, Jsonable], List[Jsonable]]], List[Union[str, int, float, bool, None, Dict[str, Jsonable], List[Jsonable]]]_ )
The JSON-serializable representation of the value. Must not be modified.


#### _property_ json_text(_: st_ )
The serialized JSON text representation of the value


### _class_ secret_kv.value.XJsonSerializable()
Bases: `object`


### secret_kv.value.clone_simple_jsonable(data: Union[str, int, float, bool, None, Dict[str, Union[str, int, float, bool, None, Dict[str, Jsonable], List[Jsonable]]], List[Union[str, int, float, bool, None, Dict[str, Jsonable], List[Jsonable]]]])

### secret_kv.value.validate_simple_jsonable(data: Any)

### secret_kv.value.xjson_decode(data: Union[str, int, float, bool, None, Dict[str, Union[str, int, float, bool, None, Dict[str, Jsonable], List[Jsonable]]], List[Union[str, int, float, bool, None, Dict[str, Jsonable], List[Jsonable]]]])

### secret_kv.value.xjson_decode_extended_value(rtype: str, rdata: Union[str, int, float, bool, None, Dict[str, Union[str, int, float, bool, None, Dict[str, Jsonable], List[Jsonable]]], List[Union[str, int, float, bool, None, Dict[str, Jsonable], List[Jsonable]]]])

### secret_kv.value.xjson_decode_simple_jsonable(data: Union[str, int, float, bool, None, Dict[str, Union[str, int, float, bool, None, Dict[str, Jsonable], List[Jsonable]]], List[Union[str, int, float, bool, None, Dict[str, Jsonable], List[Jsonable]]]])

### secret_kv.value.xjson_encode(data: Union[str, int, float, bool, bytes, bytearray, object, None, Mapping[str, Union[str, int, float, bool, bytes, bytearray, object, None, Mapping[str, XJsonable], Iterable[XJsonable]]], Iterable[Union[str, int, float, bool, bytes, bytearray, object, None, Mapping[str, XJsonable], Iterable[XJsonable]]]])

### secret_kv.value.xjson_encode_simple_jsonable(data: Union[str, int, float, bool, None, Dict[str, Union[str, int, float, bool, None, Dict[str, Jsonable], List[Jsonable]]], List[Union[str, int, float, bool, None, Dict[str, Jsonable], List[Jsonable]]]])
## secret_kv.version module

Package secret_kv provides encrypted rich key/value storage for an application or project

## Module contents

Package secret_kv provides encrypted rich key/value storage for an application or project
