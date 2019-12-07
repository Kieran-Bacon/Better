# Changelog

## 0.5.0 - 2019/12/06 - Inclusion of eval

- Add eval as a type which allows the user to evaluate their settings to even more dynamic
- Add safety methods to ensure that it is safe.
- Included some fixes for the str type - included nested str types

## 0.4.1 - 2019/07/29 - Hotfix for parser

- Corrected local variable ioStream which was not defined
- ensured that tests pass

## 0.4.0 - 2019/07/27 - writing with ConfigParser

- ConfigParser's interface has refined, redundant functions have been removed.
- ConfigParser.write has been added to allow users to write a config to file
- Interpolation has been added.
- sequence type hints have been added to the parsable language

## 0.3.0 - 2019/05/12 - update the ConfigParser

- Add change log for the package (hence why this is the first entry).
- Extend the type system within the ConfigParser to handle and accept sub type casting of settings.
- Add functionality to write a configuration's contents to file. Writing retains types of the items as best as can be.
