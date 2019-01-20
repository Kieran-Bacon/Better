import io
import re

class ConsistencyError(Exception):
    """ A warning that the internal consistency of the config parser has broken down """
    pass

class ConfigParser(dict):
    """ This is an implementation of the global ini configuration format

    Attributes:

    Parameters:
        source (object): A source for the config parser, to allow it to initialize with values. Must be either a string
            or an instance that implements the io.IOBase interface (essentially must have a readline method)
        *,
        indent_size (int): The number of of spaces that have to be adjacent, such that they can be treated as a tab char
        delimiter (str): The char(s) used to delimite sequences within the configuration file

    Raises:
        ValueError: In the event that the source provided does not have a readline function
    """

    _comments = re.compile(r"[#;].*")  # Identifies comments and all following characters

    _typeRegx = re.compile(r"\w+")

    _emptyline = re.compile(r"^\s*$")
    _leadingWhitespace = re.compile(r"^\s*")
    _sectionRegx = re.compile(r"^\[(?P<header>.+)\]$")
    _equalityRegx = re.compile(r"^(\((?P<type>[\w.]+)\)){0,1}(?P<name>.+)\s*[=:]\s*(?P<value>.*)$")

    @classmethod
    def fromFile(cls, filepath: str):
        with open(filepath) as fh:
            return cls(fh)

    def __init__(self, source: object = {}, *, indent_size: int = 4, delimiter: str = ","):

        self._indent = indent_size
        self._delimiter = delimiter

        if isinstance(source, dict):
            self.update(source)
        else:
            if isinstance(source, str):
                source = io.StringIO(source)

            if not hasattr(source, "readline"):
                raise ValueError("Source is invalid, requirement for readline function")

            self.parseIO(source)

    def read(self, filepath: str):
        """ Read the contents of a file using the filepath provided, parse the contents and update the config with its
        values

        Parameters:
            filepath (str): The filepath to the configuration file.

        Raises:
            IOError: Any error that can be raises by the 'open' builtin can be raised by this function
        """
        with open(filepath) as fh:
            self.parseIO(fh)

    def parse(self, configuration_string: str):
        """ Parse the provided string converting its contents into key values and updating this config with the values

        Parameters:
            configuration_string (str): The string to be parsed
        """
        self.parseIO(io.StringIO(configuration_string))

    def parseIO(self, iostream: io.IOBase):
        """ Processes the config string provided as a single configuration file. Add the contents the file to the
        instance

        Params:
            config_str (str): The configuration file string
        """

        scope_stack = []  # Structure to hold the sections currently 'opened' during parsing
        variable = {
            "lnumber": None,  # The line number the variable begins on
            "scope": None,  # The scope of the variable
            "type": None,  # The type of the variable if provided
            "name": None,  # The name of the variable that is currently being processed
            "value": None  # The current value of the variable (this may increase due to follow on lines)
        }

        def pushVariable(variable):
            """ Push the information about the variable into the config at the position expressed by the scope stack """
            if variable["name"] is None: return  variable# Nothing to do

            if variable["type"] is not None and variable["type"] != "str":
                try:
                    variable["value"] = self._convertType(variable["type"], variable["value"])
                except Exception as e:
                    raise ValueError(
                        "Invalid type definition of property {} on line {}".format(variable["lnumber"], variable["name"])
                    ) from e

            node = self._traverse(variable["scope"])
            node[variable["name"].strip()] = variable["value"]

            variable = {key: None for key in variable.keys()}
            return variable


        line_index = 0  # Line counter / Represnets the line number of the file being read
        while True:
            line_index += 1 # Increment the counter as we are about to read another line

            line = iostream.readline()
            if line == "": break  # The line has reached an end of file line (due to the lack of a new line character)

            line = self._comments.sub("", line)  # Remove comments
            if self._emptyline.search(line): continue  # Ignore empty lines

            # Determine the scope of the line by examining the indentation of the line - update current scope stack
            scope = len(self._leadingWhitespace.match(line).group(0).replace("\t", " "*self._indent))
            scope_stack = scope_stack[:scope+1]

            line = line.strip()  # Strip out all surrounding whitespace

            print(scope_stack, line)

            # Check if the current line is opening up a section
            match = self._sectionRegx.search(line)
            if match is not None:
                variable = pushVariable(variable)
                section_header = match.group("header")

                # Collect the scope this section sits in - make sure to not overwrite any previous values
                node = self._traverse(scope_stack[:scope])
                node[section_header] = node.get(section_header, {})

                # Add the header to the stack updated section header
                scope_stack += [None]*((scope + 1) - len(scope_stack))
                scope_stack[scope] = section_header

                continue

            # The line is a configuration line - extract the information
            match = self._equalityRegx.search(line)
            if match is not None:  # The line is a key value pair
                variable = pushVariable(variable)  # Push any previous variable
                variable["lnumber"] = line_index
                variable["scope"] = scope_stack.copy()
                for group in ["type", "name", "value"]: variable[group] = match.group(group)
            elif len(scope_stack) <= scope and variable["name"] is not None:  # The line extends the previous
                variable["value"] += "\n" + line
            else:  # The line is an empty key without a value
                variable["name"] = line
                variable["value"] = True
                variable["scope"] = scope_stack.copy()
                variable = pushVariable(variable)

        pushVariable(variable)

    def _traverse(self, path: [str]):
        """ Traverse the internal structure with the provided path and return the value located. All strings passed
        must be the keys for dictionaries within the structure other than than the last item. The value returned can
        be anything that exists at that point

        Params:


        Raises:
            KeyError - if the structure is does not resemble the path that has been provided
        """

        node = self  # Root node
        for key in path:    # Traverse the dictionary for the final item
            if key is None: continue
            if not isinstance(node, dict): raise ConsistencyError("Path expected a greater depth during traversal")
            node = node[key]

        return node

    def _convertType(self, variable_type: str, variable_value: str):
        """ Convert the value passed into the type provided

        Raises:
            TypeError: In the event that the value is not acceptable for the type specified
            Exception: Any other acception that may be caused by using a non standard type
        """

        if variable_value:
            variable_value = [x.strip() for x in variable_value.split(self._delimiter)]
        else:
            variable_value = []

        if   variable_type == "list":         return variable_value
        elif variable_type == "set":          return set(variable_value)
        elif variable_type == "frozenset":    return frozenset(variable_value)
        elif variable_type == "tuple":        return tuple(variable_value)
        elif variable_type == "range":        return range(*[int(x) for x in variable_value])

        elif variable_type == "bytes":        return bytes(*variable_value)
        elif variable_type == "bytearray":    return bytearray(*variable_value)

        elif variable_value == "bool":        return "True" == variable_value[0]
        elif variable_type == "int":
            if len(variable_value) == 2: variable_value[1] = int(variable_value[1])
            return int(*variable_value)
        elif variable_type == "float":        return float(*variable_value)
        elif variable_type == "complex":      return float("".join(variable_value))

        else:
            import importlib

            modules = variable_type.split(".")
            importClass = getattr(importlib.import_module(".".join(modules[:-1])), modules[-1])
            return importClass(*variable_value)
