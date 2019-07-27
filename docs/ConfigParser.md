# better.ConfigParser

A class to represent and interact with configuration files (the ini standard). This class performs all of the base functionality expressed within the configparser.ConfigParser package plus type conversion, proper section indentation, assignments (of any type) and better interactions with internal python interfaces.

```ini
[Simple Values]
key=value
spaces in keys=allowed
spaces in values=allowed as well
spaces around the delimiter = obviously
you can also use : to delimit keys from values

[All Values Are (not all) Strings]  # NO TRUE IF YOU TYPE CASE
values like this: 1000000
or this: 3.14159265359
are they treated as numbers? : no
(int) values like this: 100000  # This is an example of a value cast
was that treated as a number?: YES!
integers, floats and booleans are held as: strings # Because they weren't cast
can use the API to get converted values directly: FALSE (no need)

[Multiline Values]
chorus: I'm a lumberjack, and I'm okay
    I sleep all night and I work all day

[No Values]
key_without_value
empty string value here =

[You can use comments]
# like this
; or this

# By default only in an empty line.
# Inline comments can be harmful because they prevent users
# from using the delimiting characters as parts of values.
# That being said, this can be customized.

    [Sections Can Be Indented]
        can_values_be_as_well = True
        does_that_mean_anything_special = TRUE
        purpose = formatting for readability AND NESTED SECTIONS
        multiline_values = are
            handled just fine as
            long as they are indented
            deeper than the first line
            of a value
        # Did I mention we can indent comments, too?

[You can even interpolate values]
like = {You can use comments:Sections can Be Indented:can_values_be_as_well}
(list) and then cast = {Simple Values:key}
```

An example:

```python
import configparser
import better

# Assignment
original = configparser.ConfigParser()
original["Default"] = {"key": "value"}
original["Default"]["new"] = "10"

exampleOne = better.ConfigParser({"Default": {"key": "value"}})
exampleTwo = better.ConfigParser()
exampleTwo["Default"] = {"key": "value"}

exampleOne["Default"]["new"] = "10"
exampleTwo["Default"]["new"] = 10  # Values are not restricted to str

# Retrieval
>>> original["Default"]["new"]
"10"
>>> exampleOne["Default"]["new"]
"10"
>>> exampleTwo["Default"]["new"]
10

# Getting section information
>>> original.sections()
["Default"]
>>> exampleOne.keys()
dict_keys(["Default"])
>>> list(exampleOne.keys())
["Default"]  # if need be

# Checking membership
>>> "Default" in original
True
>>> "Default" in exampleOne
True

# Iteration
for key in original["Default"]:
    print(key)

for key in exampleOne["Default"]:
    print(key)
for value in exampleOne["Default"].values():
    print(value)
for key, value in exampleOne["Default"].items():
    print(key, value)

# Safe retrieval
value = original.get("Default", option="new")
defaultSection = original["Default"]
value = defaultSection.get("new")
value = defaultSection.get("new", "fallback value")
value = defaultSection.get("new", "fallback value", fallback="backwards compatibility")

value = original.get("Default", {}).get("new")
defaultSection = exampleOne.get("Default")
defaultSection = exampleOne["Default"]
value = defaultSection.get("new")
value = defaultSection.get("new", "fallback value")
```

functions such as `getboolean`, `getint` and `getfloat` have not been implemented for a few reasons:

**Too Simple a wrapper**: These methods are typically equivalent to calling the primitive type on the string value. `config.getint("key") == int(config["key"])` `config.getint("key", fallback=1.2) == int(config.get("key", 1.2))`

**You can't be abstracted away**: Calling this method requires that the user knowns that the section and key exist with a value that can be cast to the target type. It also requires that the user must extract this value explicitly and the value must then be stored elsewhere.

This is rather unhelpful when you want to be able to generically collect a section of non required key values that are to be unpacked into something else. Either the user is to unpack each item in turn and cast them with considerable bloat, or they just have to program to accept strings.

**The order of lookup is fixed** The order of lookup is `vars` (optionally provided), the section, and then the defaultSect. This behaviour is already emulate-able via traditional mapping methods such that is as a result, actually rather restrictive as other orders are now not achievable.

**True multiple layer implementation breaks these methods**: As a consequence of adding multiple layers to the config parser, these methods interfaces would have had to have had changed to allow the user to drive down through each layer. I felt that this deviation was already substantial and due the the previously described issues, determined to be unnecessary.

**Logically where should items be cast**: Though likely a strongly types language's philosophy, it is believed that the optimal location for indicating the intended type of a variable is when it is defined, not when it is about to be used. Considering that the aim is to fail fast, and not let errors propagate, there is already a overhead of requiring someone to convert these values with this interface and this can entirely be mitigated if it was declared within the config. Which is now is.

```python
# Base case
original.getfloat("Default", "new")
float(exampleOne["Default"]["new"])

# Fallback
original.getfloat("Default", "new", fallback=1.2)
float(exampleOne["Default"].get("new", 1.2))

# Vars
original.getfloat("Default", "new", vars={"new": "value"})
float({**{"new": "values"}, **exampleOne["Default"]}.get("new"))

# Vars and fallback
original.getfloat("Default", "new", vars={"new": "value"}, fallback=1.2)
float({**{"new": "values"}, **exampleOne["Default"]}.get("new", 1.2))

# If the value had been cast this would have been as simple as
>>> value = betterExample["Default"]["new"]
>>> type(value)
<class 'float'>
```

Furthermore, all the base mapping methods have been inherited so the interface is rich with its ability to interact with other dictionary objects

```python
betterConfig = better.ConfigParser()
dict1 = {"1": "2", "a": "A"}

dict1.update(betterConfig)
betterConfig.update(dict1)

merge = {**betterConfig, **dict1}

copy = betterConfig.copy()

betterConfig.setdefault("key")
betterConfig.setdefault("keyvalue", "value")

betterConfig.get("1", "example")

config = better.ConfigParser(r"""
1: value
[nested]
    key: value
""")

config.get("1")
config.get("nested:key")
```

## Nested sections

`better.ConfigParser` shall nest sections that have been indented within one another.
This is to allow for greater control and separation for information. Keys and properties
belong to the section they are in scope of. Scope is closed as soon as an entry is
made that is in a greater scope (see below)

```ini
[Ultimate test]
	[Nested section]
			value = true
				another = true
		third = true

		[third section]
		variable in 'third section' = hello
	variable in 'nested section' = 10
        variable also in 'nested section' = as 'third section' was closed

variable in Ultimate test = 100

[new section]
end of test = 1000
```

## Type casting

An extension of the base config parser is that the lines can support casting of key values into various types. This allows users to avoid the bloat of casting the values inline.

```python
config_ini = """
[Database]
host : 127.0.0.1
port : 8071
(int) timeout = 1000

[Extreme]
(infogain.artefact.Document) simple_document = content
"""

config = better.ConfigParser(config_ini)

db_connect(**config["Database"])
time.sleep(config["Database"]["timeout"])

isinstance(config["Extreme"]["simple_document"], infogain.artefact.Document)  # True
```

### 0.3.0 changes - iterable subtypes

Iterable objects can now have their sub-items cast to a type as they are being read/written by using the `<>` notation following its type.

`(list<int>) a = 1,2,3  # Generated shall be a list of intergers`

## Interpolated values

keys can have their values dynamically generated from previously defined keys within the configparser, allowing for setting reuse. The syntax allows for traversing multiple layers and must always be the absolute path to the key. Interpolated values can then be cast when they are interjected.

The interpolation can be avoided by putting an escape character at the end of its scope. The escape character shall then be removed when parsed. If it is intended to be present then you'll have to add two (if you want two you'll have to add three and so on and so forth...).

Values are resolved while it is being read, which results in implied depth of lookup as a value can come from a key who's value came from arbitrarily any number of previous keys. Realistically however, as these values are resolved immediately they are simply collecting a single value. This limits the users ability to dynamically generate references within the configparser to other keys. (but lets be honest - don't do that)

```ini

database_url = 'postgresql://kieran:bacon@localhost:5432/'

[Accounts]
database = {database_url}accounts
(int) timeout = 30

[Invoices]
database = {database_url}invoices
    [Nested Section]
    value = 10

[Example]
(int) key = {Invoices:NestedSection:value}
just the text = {database_url\}  # Escaped the interpolation
```

## Reference Manual

### class ConfigParser(collections.abc.MutableMapping)

```python
better.ConfigParser(
    source: object = {},
    *,
    indent_size: int = 4,
    delimiter: str = ",",
    join: str = "\n",
    default: object = True
)
```

- **source**: The source object for the config parser, which can be either a string which shall be parsed or a dictionary as a seed config.
- **indent_size**: the number of spaces a tab is to represent and the number of spaces to be used to indent when writing to file.
- **delimiter**: The character used within the config that splits listable setting values.
- **join**: The character used to join a multi-line setting value.
- **default**: The default value for a setting.

#### read

```python
config.read(filepath: str) -> ConfigParser
```

- **filepath**: Path to file to be read.

Read the contents of a file as a config definition and add its setting values into the config. Sections shall be merged, settings values shall be overwritten if there is a conflict.

Note: As setting values shall overwrite previously defined settings, if a setting is read who's name conflicts with a previously established section, the section shall be remove it.

**Returns** `ConfigParser` to allow for chaining and single line allocation

```python
config = ConfigParser().read("file1.ini")

config.read("another.ini").read("and another.ini")
```

#### write

```python
config.write(filepath: str)
```

- **filepath**: Path to the location of the new configuration file.

Write the config out to file and preserve the types of the settings as best as can be.

```python
from better import ConfigParser

config = ConfigParser("""

a = 10
(int) b = 20

[section 1]
(list<int>) values = 1, 2, 3, 4

    [section 1-1]
    another value = something
""")

config.write("testfile.ini")
```

```bash
$ cat testfile.ini
a = 10
(int) b = 20

[section 1]
(list<int>) values = 1, 2, 3, 4

    [section 1-1]
    another value = something

```

#### parse

```python
config.parse(configuration_string: str) -> ConfigParser
```

- **configuration_string**: A string representation of a config file.

Read from some source configuration strings/settings and add them into the `ConfigParser`. `parse` can take either a string or an object that implements `readline()`. An `AttributeError` shall be raised if ever an object is passed that doesn't. The `readline()` shall need to return a empty string when it has exhausted its contents.
Similar to read, parse shall add and update settings values accordingly

**Returns** `ConfigParser` to allow for chaining of parse statements

```python
with open('file.ini', 'r') as handler:
    config = ConfigParser().parse(handler).parse("Something = 10")

config.parse("""
something else = 20
""")
```

#### get

```python
config.get(path: str, default: object = None) -> object
```

- **path**: A key for a section or settings who's value is to be returned. A path can be comprised of nested keys by delimitering with a ':'
- **default**: A value to be returned in the event that the key doesn't exist within the config

Collect a key's value from the config parser. `get` has equivalent behaviour to a dictionary's `get`, however, it exploits the restriction for colon's to be present within a settings name to allow for deep key value retrieval immediately.

**Returns** `object` found at path given or the default value

```python
config = ConfigParser(r"""
basic = Still works
[1]
    [2]
        [3]
            key = value
            (int) number = 10
""")

config.get("1:2:3:key")  # Returns "value"
config.get("1:2:3:number")  # Returns 10
config.get("1:2:3:not present", "A default value")  # Returns "A default value"
```