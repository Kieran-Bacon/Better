# better.ConfigParser

A class to represent and interact with configuration files (the ini standard). This class performs all of the base functionality expressed within the configparser.ConfigParser package (except interpolation) however it makes use of the standard dictionary methods to make it consistent with dictionaries and to dramatically reduce its size.

```ini
[Simple Values]
key=value
spaces in keys=allowed
spaces in values=allowed as well
spaces around the delimiter = obviously
you can also use : to delimit keys from values

[All Values Are Strings]  # NO TRUE IF YOU TYPE CASE ;)
values like this: 1000000
or this: 3.14159265359
are they treated as numbers? : no
(int) values like this: 100000
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
```


The interface of the original `configparser.ConfigParser` has not been maintained as
its functions became either obselete or varients were already implemented as a part
of `dict`.


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

functions such as `getboolean`, `getint` and `getfloat` have not been implemented for a few reasons

* Too simple a wrapper, especially as you need to adhere to it explicitly
* The method requires that the sections exists, no utility to get around this
* The order of the look up is fixed and one cannot have control over this easily
* Dictionaries come with functionality to help with this already
* `better.ConfigParser` has multiple layers to sections and therefore is inconsitent
with this behaviour
* Values can be cast within the config.ini itself therefore avoiding this requirement

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

Furthermore, all the base dictionary functions have been inherited so the interface is
rich with its ability to interact with other dictionary objects

```python
betterConfig = better.ConfigParser()
dict1 = {"1": "2", "a": "A"}

dict1.update(betterConfig)
betterConfig.update(dict1)

merge = {**betterConfig, **dict1}

copy = betterConfig.copy()

betterConfig.setdefault("key")
betterConfig.setdefault("keyvalue", "value")
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

An extension of the base config parser is that the lines can support casting of
key values into various types. This allows users to avoid the bloat of casting
the values inline.
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
time.sleep(config["Databse"]["timeout"])

isinstance(config["Extreme"]["simple_document"], infogain.artefact.Document)  # True
```

# Reference Manual

## better.ConfigParser

#### better.ConfigParser(source: object = {}, *, indent_size: int = 4, delimiter: str = ",")

A `source` object can either be a dictionary, a string, or any instance that has as
part of its interface the `readline()` method. This source is used to populate the
ConfigParser during initialisation.

The `indent_size` is the number of spaces a tab character is equivilent too

A `delimiter` character is used to split values into sequences when a type has been
provided. This sequence can then been feed into the init of the type.

If the `source` object provided is incorrect then the a `ValueError` shall be raised in response.

## Instance Methods

#### read(filepath: str)

Read the contents of a file using the filepath provided, parse the contents and
updates this objects values accordingly.

`read` shall raise any `IOError` exceptions that can be raised by `open`, if the
filepath provided is incorrect

If `read` is called on a `ConfigParser` that already has contents, overlapping
keys shall have their values replaced, independant keys shall remain, and sections
shall be merged.

```python
config = ConfigParser()
config.read("./config.ini")
```

#### parse(configuration_str: str)

Parse a `str` object and update the configurations values accordingly

If `parse` is called on a `ConfigParser` that already has contents, overlapping
keys shall have their values replaced, independant keys shall remain, and sections
shall be merged.

```python
config_string = """
[Section One]
a = 10
"""

config = ConfigParser()
config.parse(config_string)
```

#### parseIO(iostream: io.IOBase)

Parse an iostream and convert and update the configurations values accordingly

`AttributeError` shall be raised in the event that the `iostream` does not have a
`readline()` method.

```python
config = better.ConfigParser()

with open("./example.ini") as handler:
    config.parserIO(handler)
```

## Class Methods

#### fromFile(filepath: str)

Create a ConfigParser from a file location, the same as as the instance method
`read()` however it doesn't require a ConfigParser to already have been made.

```python
import better
config = better.ConfigParser.fromFile("./config.ini")
```
