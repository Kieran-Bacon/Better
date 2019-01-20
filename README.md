# Better

This package extends other packages with functionality that users typically have to implement themselves. Better doesn't redefine or alter the initial implementations, simply adding additional utilites along side.

To ensure that there is no misunderstanding, I am not suggesting that any initial implementation is substandard, nor that they were incomplete, far from it, I've used and enjoyed each package. This is a package of code snippets that I've written into various projects while using the respective package and thought that others might find them useful.

## Threading

Currently only adds threading for loop functionality.

## Multiprocessing

Added a PoolManager that provides a minimal api for generating and handling interactions with a pool of processes.

## ConfigParser

A class to represent and interact with configuration files (the ini standard). This class performs all of the base functionality expressed within the configparser.ConfigParser package (except interpolation) however it makes use of the standard dictionary methods to make it consistent with dictionaries and to dramatically reduce its size.

The interface of the configparser package is not maintained as most of the functions either became obselete or they are implemented already as methods on the dictionary.

An example:
```
config.sections() == config.keys()
```

Additionally functions that provide little utility have also been removed.

```
config.getfloat(key)  == float(config[key])
```

Casting of types have been introduced to remove the requirement to programmatically convert these values.
```
(int) key = 100  # Shall be converted on read into an integer

# Casting shall also attempt to import and cast complex types
(infogain.artefact.Document) simple_document = content
```
