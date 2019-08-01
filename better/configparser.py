import os
import io
import re
import collections

class ConsistencyError(Exception):
    """ A warning that the internal consistency of the config parser has broken
    down
    """
    pass

class Setting:
    """ A setting value within the a config file. A key value representation
    that holds its scope
    """

    def __init__(self, scope: [str], line: int, name: str, value: object, type: str = None):
        self.scope = scope
        self.line = line
        self.name = name
        self.value = value
        self.type = type

    def __repr__(self):
        return "line {} in {}: ({}) {} = {}".format(self.line, self.scope, self.type, self.name, self.value)

class ConfigParser(collections.abc.MutableMapping):
    """ This is an implementation of the global ini configuration format

    Parameters:
        source (object): A source for the config parser, to allow it to
            initialize with values. Must be either a string or an instance that
            implements the io.IOBase interface (essentially must have a readline
            method)
        *,
        indent_size (int): The number of of spaces that have to be adjacent,
            such that they can be treated as a tab char
        delimiter (str): The char(s) used to delimite sequences within the
            configuration file

    Raises:
        ValueError: In the event that the source provided does not have a
            readline function
    """

    _rxComments = re.compile(r"[#;].*")  # Identifies comments and all following characters

    _rxEmptyLine = re.compile(r"^\s*$")
    _rxWhiteSpace = re.compile(r"^\s*")

    _rxSection = re.compile(r"^\[(?P<header>.+)\]$")
    _rxEquality = re.compile(r"^(\((?P<type>[^\({}\)=:\n]+)\))?\s*(?P<name>[^\({}\)=:\n]+)\s*[=:]\s*(?P<value>.*)$")

    _rxInterpolation = re.compile(r"{(.*)[^\\]}")

    _rxType = re.compile(r"^(?P<type>[\w\.]+)(<(?P<sub_type>[^>]+)>)?$")

    _max_line_length = 120

    def __init__(self, source: object = {}, *, indent_size: int = 4, delimiter: str = ",", join: str = os.linesep, default: object = True):

        self._elements = {}  # The dictionary containing the content
        self._indent = indent_size
        self._delimiter = delimiter
        self._join = join
        self._default = default

        if isinstance(source, dict):
            self.update(source)
        else:
            self.parse(source)

    def __repr__(self): return "<ConfigParser {}>".format(self._elements)
    def __len__(self): return len(self._elements)
    def __getitem__(self, key: object): return self._elements[key]
    def __setitem__(self, key: object, value: object): self._elements[key] = value
    def __delitem__(self, key: object): del self._elements[key]
    def __iter__(self): return iter(self._elements)

    def get(self, path: str, default: object = None) -> object:
        """ Collect the value from within the config parser and return or if not
        found return the default value

        Params:
            path (str): A semi-colon delimited path of key names
            default (object) = None: The value to be returned if nothing is
                found

        returns:
            object: Either the value at the location of path, or the default
        """

        if ":" in path:
            # Split the path into its absolute path key names
            absolute_path = path.split(":")

            # Select the top level node as value to travel down
            value = self._elements

            # For each key attempt to traverse the node
            for key in absolute_path:
                if not isinstance(value, dict) or key not in value:
                    # The value doesn't exist return the default provided
                    return default

                value = value[key]

            # Return the value found after traversing the nodes
            return value
        else:
            # Traditional behaviour
            return super().get(path, default)

    def read(self, filepath: str):
        """ Read the contents of a file using the filepath provided, parse the
        contents and update the config with its values

        Parameters:
            filepath (str): The filepath to the configuration file.

        Returns:
            ConfigParser: self

        Raises:
            IOError: Any error that can be raises by the 'open' builtin can be
                raised by this function
        """
        with open(filepath) as fh:
            self.parse(fh)

        return self

    def parse(self, configuration_string: str):
        """ Parse the provided  object converting its contents into key values and updating this config with the values.
        This function accepts strings or io objects that express a readline function.

        Parameters:
            configuration_string (str / io.IO.base): The string to be parsed
        """

        # Convert any string passed into an io stream
        if isinstance(configuration_string, str):
            ioStream = io.StringIO(configuration_string)

        # Check that the source configuration is valid
        elif hasattr(configuration_string, 'readline'):
            ioStream = configuration_string

        else:
            raise ValueError("Source object doesn't implement a readline function - cannot parse")

        # The current indentation of the line - scope shall be greater than scope stack for variables being defined in
        # a section.
        scope = 0

        # Holds current indentation for section headers - e.g ["header", None, None, "sub header"]. Scope shall reduce
        # the scope stack.
        scope_stack = []

        # Currently examined setting container - holds name and points to value
        setting = None

        # Line counter / represents the line number of the file being read
        line_index = 0

        while True:
            line = ioStream.readline()
            if line == "": break  # The line has reached an end of file line (due to the lack of a new line character)

            # Increment the line number
            line_index += 1

            line = self._removeComments(line)  # Remove comments from the line
            if self._rxEmptyLine.search(line): continue  # Ignore empty lines

            # Determine scope and reduce scope stack if less than section scope
            scope = len(self._rxWhiteSpace.match(line).group(0).replace("\t", " "*self._indent))
            scope_stack = scope_stack[:scope+1]

            line = line.strip()  # Strip out all surrounding whitespace

            # Examine the syntax of the line and determine its intention
            match = self._rxSection.search(line)
            if match is not None:
                # Section declaration - Open a new section in at this scope

                # Push any currently open setting
                self._addSetting(setting)
                setting = None

                # Collect from the match object the section header
                section_header = match.group("header")

                # Traverse the current parsed scope and add the section in if present
                # Note: Taking care to ensure that a previously openned section isn't overwritten
                node = self._traverse(scope_stack[:scope])
                node[section_header] = node.get(section_header, {})

                # Add the header to the stack updated section header - padding scope with None
                scope_stack += [None]*((scope + 1) - len(scope_stack))
                scope_stack[scope] = section_header

                continue

            match = self._rxEquality.search(line)
            if match is not None:
                # Setting Declaration - The line is a key value pair

                # Add previous setting if set
                self._addSetting(setting)

                # Generate a setting to hold the information of this line just read in
                setting = Setting(
                    scope_stack.copy(),
                    line_index,
                    match.group("name").strip(),
                    self._performInterpolation(match.group("value").strip()),
                    match.group("type")
                )

            elif len(scope_stack) <= scope and setting is not None:
                # Setting Extension - Scope is greater than section header + no key value - assumed value extension
                setting.value += self._join + self._performInterpolation(line)

            else:
                # Key Declaration - The line is a key without a value
                self._addSetting(setting)

                self._addSetting(
                    Setting(
                        scope_stack.copy(),
                        line_index,
                        line,
                        self._default
                    )
                )

                # Reset setting - ready for a new value
                setting = None

        # All lines read - push final setting
        self._addSetting(setting)

        return self

    def write(self, filepath: str) -> None:
        """ Write the config to file

        Params:
            filepath (str): The path of to where the file should be generated
        """

        def write(handler: object, section: dict, depth: int = 0) -> None:
            """ Write the section provided into the filehandler provided, and recursively write subsections into
            the handler

            Params:
                handler (FileHandle): The handler to be written to
                section (dict): The section to be written
                depth (int) = 0: The depth of the section - none zero value implies that the section is a nested section
            """

            # Define containers for the two types of contents of the dictionary - separate the section
            settings, sections = [], []

            for key, value in section.items():
                if isinstance(value, dict):
                    sections.append((key, value))
                else:
                    settings.append((key, value))

            # Process the settings of the section first - sort the keys before writing
            for key, value in sorted(settings, key = lambda x: x[0]):

                setting_depth = max(0, depth - 1)

                # Define the variables type
                setting_type, value = self._convertFromType(value)
                if setting_type: setting_type = "({}) ".format(setting_type)

                # Define the key for the setting
                title = "{}{}{} = ".format(" "*(setting_depth*self._indent), setting_type, key)
                lentit = len(title)

                # Define the value string
                lenval = len(value)

                config_value = ""  # The manipulated value string
                whitespace = " "*(1 + setting_depth*self._indent)

                if lentit + lenval < self._max_line_length or self._join not in value:
                    # The entire setting can fit on a single line - or it cannot be broken up
                    config_value = value
                else:
                    # The setting is greater than the line limit -  examine the value for break points
                    start, end = 0, self._max_line_length - lentit
                    line_length = self._max_line_length - (setting_depth*self._indent + 1)

                    while True:
                        # Check whether we can break from the processing of the value
                        if end > lenval:
                            # The final window containing the rest of the value - write it and break
                            config_value += value[start:]
                            break

                        # Idenfity whether there is a break point in the window
                        splitPoint = value[start: end].rfind(self._join)

                        if splitPoint == -1:
                            # There was nowhere to split for this window, search for next split and add entire line
                            nextSplit = value[end:].find(self._join)

                            if nextSplit == -1:
                                # There is not going to be another split, write the remaining line and end
                                config_value += value[start:]
                                break
                            else:
                                end += nextSplit
                        else:
                            end = start + splitPoint

                        # Extract the line given by the start and end char and add it to the config line
                        config_value += value[start: end] + os.linesep + whitespace

                        # Update the start and end index - Add one to the previous end to jump over the break character
                        start, end = end + len(os.linesep), end + len(os.linesep) + line_length

                # Ensure that white space is handled
                config_value = re.sub(
                    "{}(?!{})".format(os.linesep, whitespace),
                    "{}{}".format(os.linesep, whitespace),
                    config_value
                )

                # Write the setting line
                handler.write("".join((title, config_value, os.linesep)))

            for name, section in sorted(sections, key = lambda x: x[0]):
                # Write the nested sections - start by writing its name
                handler.write("{}[{}]{}".format(" "*(depth*self._indent), name, os.linesep))

                # Write the contents of the section
                write(handler, section, depth + 1)

                # Separate the sections - Check that section contents doesn't already separate sections
                if not any(isinstance(v, dict) for v in section.values()):
                    handler.write(os.linesep)

        with open(filepath, mode = "w", newline = '') as handler:
            write(handler, self)

    def _addSetting(self, setting: Setting):
            """ Push the information about the currently staged variable into the config at the position expressed by
            its mark on the scope stack
            """
            if setting is None: return  # Nothing to add

            # None string type set for value - update the value before adding to self
            if setting.type is not (None and "str"):
                try:
                    setting.value = self._convertToType(setting.type, setting.value)
                except Exception as e:
                    raise ValueError(
                        "Invalid type definition: Line {} - {} = {}".format(setting.line, setting.name, setting.value)
                    ) from e

            elif isinstance(setting.value, str) and setting.value:
                # Trim quotes from  string setting value if applicable
                if setting.value[0] in ('"', "'") and setting.value[0] == setting.value[-1]:
                    setting.value = setting.value[1:-1]

            # Insert the setting into self at the correct position
            self._traverse(setting.scope)[setting.name] = setting.value

    def _removeComments(self, line: str) -> None:
        """ Remove comments ensuring that a the comment symbols aren't removed
        if they are actually apart of the value

        Params:
            line (str): The line that is to have the comment striped out of it

        Returns:
            str: The line provided without line
        """

        comment = None
        escape = False
        openChar = None
        for i, char in enumerate(line):
            if char == "\\":
                escape = True
                continue

            elif not escape and openChar and openChar == char: openChar = None  # Close the original opening char
            elif openChar is None and not escape and char in ["\"", "'"]: openChar = char
            elif openChar is None and char in ["#", ";"]:
                comment = i
                break

            escape = False

        if comment is not None: line = line[:comment]
        return line

    def _traverse(self, path: [str]):
        """ Traverse the internal structure with the provided path and return
        the value located. All strings passed must be the keys for dictionaries
        within the structure other than than the last item. The value returned
        can be anything that exists at that point

        Params:
            path ([str]): A list of keys of the objects - the path through the
                config to the value

        Raises:
            KeyError - if the structure is does not resemble the path that has
                been provided
        """

        # Root Node
        node = self._elements

        for key in path:
            # Traverse the dictionary for the final item
            if key is None: continue  # Ignore unused scope
            if not isinstance(node, dict): raise ConsistencyError("Path expected a greater depth during traversal")
            node = node[key]

        return node

    def _performInterpolation(self, line: str) -> str:
        """ Convert the references in the provided line into their value that
        was previously defined, and not a key value within the config

        Params:
            line (str): The line to perform the interpolation on

        Returns:
            str: The line transformed to have its values
        """

        # For each match in the line
        for match in self._rxInterpolation.finditer(line):
            path = match.group(0).strip("{}").split(":")  # Path/key of value

            value = self._traverse(path[:-1])[path[-1]]  # Extract the value for the path

            line = re.sub(match.group(0), str(value), line)  # Replace the original match with this value

        # Return the transformed line
        return line

    def _convertToType(self, variable_type: str, variable_value: str):
        """ Convert the value passed into the type provided

        Raises:
            TypeError: In the event that the value is not acceptable for the
                type specified
            Exception: Any other acception that may be caused by using a non
                standard type
        """

        match = self._rxType.match(variable_type)
        if match is None:
            raise ValueError("Couldn't process type signature: {}".format(variable_type))


        if variable_value:
            variable_value = [x.strip() for x in variable_value.split(self._delimiter)]

            if match.group("sub_type"):
                variable_value = [self._convertToType(match.group("sub_type"), sub_val) for sub_val in variable_value]
        else:
            variable_value = []

        if   match.group("type") == "list":         return variable_value
        elif match.group("type") == "set":          return set(variable_value)
        elif match.group("type") == "frozenset":    return frozenset(variable_value)
        elif match.group("type") == "tuple":        return tuple(variable_value)
        elif match.group("type") == "range":        return range(*[int(x) for x in variable_value])

        elif match.group("type") == "bytes":        return bytes(*variable_value)
        elif match.group("type") == "bytearray":    return bytearray(*variable_value)

        elif match.group("type") == "bool":        return variable_value[0] == ("True" or "yes" or "1" or "on")
        elif match.group("type") == "int":
            if len(variable_value) == 2: variable_value[1] = int(variable_value[1])
            return int(*variable_value)
        elif match.group("type") == "float":        return float(*variable_value)
        elif match.group("type") == "complex":      return float("".join(variable_value))

        else:
            import importlib

            modules = match.group("type").split(".")
            importClass = getattr(importlib.import_module(".".join(modules[:-1])), modules[-1])
            return importClass(*variable_value)

    @staticmethod
    def _updateIterableType(base: str, iterable: object):
        """ Check whether all the items within an iterable have the same type if so update the base to reflext that

        Params:
            base (str): The base type of the iterable
            iterable (object): An object that can be iterated

        Returns:
            str: the base or the base and its subtype if all items have the same type
        """
        if len(iterable): # Assert that the iterable has length before checking its values
            iterType = None
            for item in iterable:

                if iterType is None:
                    # Record the type of the first item
                    iterType = type(item).__name__
                    continue

                # break in the event that an item doesn't have the same type of any previous items
                if type(item).__name__ != iterType:
                    break
            else:
                return "{}<{}>".format(base, iterType) # If it never breaks, then all the items must have the same type

        return base

    def _convertFromType(self, value: object) -> str:
        """ Convert the provided value into a string which would be acceptable as input to the config parser. This
        method is to service the serialisation of a config.

        Params:
            value (object): The value that is to be stringified

        Returns:
            str: The config parser string representation of the object
        """

        if isinstance(value, str):
            return "", value

        # Assert the name of the type for casting
        value_type = type(value).__name__

        if isinstance(value, (int, bool, float)):
            value_string = str(value)

        elif isinstance(value, set):
            value_type = self._updateIterableType(value_type, value)

            if len(value): value_string = str(value).strip(r"{}")
            else: value_string = ""

        elif isinstance(value, frozenset):
            value_type = self._updateIterableType(value_type, value)

            if len(value): value_string = str(value)[11:-2]
            else: value_string = ""

        elif isinstance(value, list):
            value_type = self._updateIterableType(value_type, value)
            value_string = str(value).strip("[]")

        elif isinstance(value, tuple):
            value_type = self._updateIterableType(value_type, value)
            value_string = str(value).strip("()")

        elif isinstance(value, (bytes, bytearray)):
            value_string = value.decode() + ", utf-8"

        elif isinstance(value, complex):
            value_string = str(value).strip("()")

        else:
            raise ValueError("Variable type could not be converted")

        return value_type, value_string

    def copy(self): return self._elements.copy()