import unittest

import os

import better
from better import ConfigParser

RESOURCES = os.path.join(os.path.dirname(__file__), "resources", "configparser")

class Test_ConfigParser(unittest.TestCase):

    maxDiff = None

    def test_parse_simpleString(self):
        simple_string = "[hello]\na = 10"
        config = ConfigParser(simple_string)
        self.assertEqual(config["hello"]["a"], "10")

    def test_parse_multiple_sections_string(self):

        section_string = "[hello]\na = 10\nb=20\n\n[there]\nobione=yes\n"
        config = ConfigParser(section_string)

        expected_result = {
            "hello": {
                "a": "10",
                "b": "20",
            },
            "there": {
                "obione": "yes"
            }
        }

        self.assertEqual(config, expected_result)

    def test_dictionary_behaviour(self):

        other_dictionary = {"there": {"obione": "yes"}}
        config = ConfigParser("[hello]\na = 10\nb=20")
        expected_result = {
            "hello": {
                "a": "10",
                "b": "20",
            },
            "there": {
                "obione": "yes"
            }
        }

        isinstance(config.copy(), ConfigParser)

        # Testing update works as expected
        toUpdate = config.copy()
        toMix = other_dictionary.copy()
        toUpdate.update(toMix)
        toMix.update(config)

        self.assertEqual(toUpdate, expected_result)
        self.assertEqual(toMix, expected_result)

        # Unpacking into another item works
        self.assertEqual({**config, **other_dictionary}, expected_result)

    def test_fromFile(self):
        config = ConfigParser.fromFile(os.path.join(RESOURCES, "example.ini"))

        expected_result = {
            'Simple Values': {
                'key': 'value',
                'spaces in keys': 'allowed',
                'spaces in values': 'allowed as well',
                'spaces around the delimiter': 'obviously',
                'you can also use': 'to delimit keys from values'
            },
            'All Values Are Strings': {
                'values like this': '1000000',
                'or this': '3.14159265359',
                'are they treated as numbers?': 'no',
                'integers, floats and booleans are held as': 'strings',
                'can use the API to get converted values directly': 'true'
            },
            'Multiline Values': {
                'chorus': "I'm a lumberjack, and I'm okay\nI sleep all night and I work all day"
            },
            'No Values': {
                'key_without_value': True,
                'empty string value here': ''
            },
            'You can use comments': {
                'Sections Can Be Indented': {
                    'can_values_be_as_well': 'True',
                    'does_that_mean_anything_special': 'False',
                    'purpose': 'formatting for readability',
                    'multiline_values': 'are\nhandled just fine as\nlong as they are indented\ndeeper than the first line\nof a value'
                }
            }
        }

        self.assertEqual(config, expected_result)

    def test_fromChallengingFile(self):
        config = ConfigParser.fromFile(os.path.join(RESOURCES, "challenging.ini"))

        expected_result = {
            'Ultimate test': {
                'Nested section': {
                    'value': 'true',
                    'another': 'true',
                    'third': 'true',
                    'third section': {
                        'something': True
                    },
                    "variable in 'nested section'": '10'
                },
                'variable in Ultimate test': '100'
            },
            'new section': {
                'end of test': '1000'
            }
        }

        print(config)
        self.assertEqual(config, expected_result)

    def test_parse_string(self):

        config = ConfigParser()
        config.parse("""
        [section]
        a = 10
        """)

        self.assertEqual(config, {"section": {"a": "10"}})

    def test_read(self):
        config = ConfigParser()
        config.read(os.path.join(RESOURCES, "challenging.ini"))

        expected_result = {
            'Ultimate test': {
                'Nested section': {
                    'value': 'true',
                    'another': 'true',
                    'third': 'true',
                    'third section': {
                        'something': True
                    },
                    "variable in 'nested section'": '10'
                },
                'variable in Ultimate test': '100'
            },
            'new section': {
                'end of test': '1000'
            }
        }

        self.assertEqual(config, expected_result)

    def test_merging_configs(self):

        config = ConfigParser()

        config.parse("""
        [section]
        a = 10
        """)

        config.parse("""
        [section]
        b = 10
        """)

        self.assertEqual(config, {"section": {"a": "10", "b": "10"}})


    def test_comments(self):
        """ Test that comments that are submitted to the config parser aren't picked up as a value or cause the
        parsing to error """

        config = ConfigParser()

        config.parse("""
        this line should not = include the comment # This is the comment
        Nor should this = one ; include this either...
        # These are obvious comments
        ;Yet you may be surprised
        #; Whhat If # I do this!
        ;# Or that?

        [WHAT SHALL HAPPEN] # nothing...
        """
        )

        self.assertEqual(set(config.keys()), {"this line should not", "Nor should this", "WHAT SHALL HAPPEN"})
        self.assertEqual(config["this line should not"], "include the comment")
        self.assertEqual(config["Nor should this"], "one")
        self.assertEqual(config["WHAT SHALL HAPPEN"], {})

    def test_single_space_indentation_works(self):

        config = ConfigParser()
        config.parse("""
            a = something
             and this should add together too
            """
        )

        self.assertEqual(config["a"], "something\nand this should add together too")

    def test_type_casting(self):

        config = ConfigParser()
        config.parse("""
        (int) a = 10
        (list) names = Kieran, Martha, Mumbo
        (int) k = 10, 2
        (range) yes = 10, 20, 5
        (uuid.uuid4) guid =
        (list) b = one, two, three
        (list) c =
            one,
            two, three,
            four five
            six
        """
        )

        self.assertEqual(config.keys(), {"a", "names", "k", "yes", "guid", "b", "c"})
        self.assertEqual(config["a"], 10)
        self.assertEqual(config["names"], ["Kieran", "Martha", "Mumbo"])
        self.assertEqual(config["k"], int("10", 2))
        self.assertEqual(config["yes"], range(10, 20, 5))
        self.assertEqual(config["b"], ["one", "two", "three"])
        self.assertEqual(config["c"], ["one","two", "three", "four five\nsix"])

        import uuid
        self.assertIsInstance(config["guid"], uuid.UUID)

    def test_equality_delimitation_of_properties(self):

        config = ConfigParser()

        config.parse("""
        a = 100
        b : 200
        (int) c = 1000
        (int) d : 2000
        e=123
        f:47432
        """)

        self.assertEqual(config.keys(), {"a","b","c","d","e","f"})

    def test_configparser_Quick_Start_Example(self):

        config = ConfigParser.fromFile(os.path.join(RESOURCES, "Quick Start.ini"))

        self.assertEqual(
            config,
            {
                "DEFAULT": {
                    "ServerAliveInterval": "45",
                    "Compression": "yes",
                    "CompressionLevel": "9",
                    "ForwardX11": "yes"
                },

                "bitbucket.org": {
                    "User": "hg"
                },

                "topsecret.server.com": {
                    "Port": "50022",
                    "ForwardX11": "no"
                }
            }
        )

    def test_for_in_behaviour(self):
        config = ConfigParser.fromFile(os.path.join(RESOURCES, "Quick Start.ini"))
        keys = [k for k in config["DEFAULT"]]
        self.assertSetEqual(set(keys), {'ServerAliveInterval', 'Compression', 'CompressionLevel', 'ForwardX11'})

    def test_comments_dont_bother_values(self):

        config = ConfigParser(r"""
        a = value # This comment should not exist as part of the value
        b = "value # This one should though since its inside a quote"
        c = 'just to clarify that #either quotes work'
        d = "And we need to check that if the thing isn't within the quotes" # Then its totally ok
        e = "We should also ensure that \" works as a method of escaping the quotes" # And this should still work
        f = Lets go for multi-line comments ; shaking nervously
         these should not be a problem right!? # One would hope
         because that would be bad...
        g = "Well this shouldn't  really work... # as this comment
         is actually within the multi-line quote."
        """)

        self.assertEqual(config, {
            "a": "value",
            "b": "value # This one should though since its inside a quote",
            "c": "just to clarify that #either quotes work",
            "d": "And we need to check that if the thing isn't within the quotes",
            "e": 'We should also ensure that \\" works as a method of escaping the quotes',
            "f": "Lets go for multi-line comments\nthese should not be a problem right!?\nbecause that would be bad...",
            "g": "Well this shouldn't  really work... # as this comment\nis actually within the multi-line quote."
        })

    def test_interpolationOfValues(self):
        """ Assert that interpolated values can be extracted correctly """

        config = ConfigParser(r"""
        a = something
        b = {a} else

        [section]
        c = example
        d = {section:c} proven
        """)

        print(config._elements)

        self.assertEqual(config, {
            "a": "something",
            "b": "something else",
            "section": {
                "c": "example",
                "d": "example proven"
            }
        })

    def test_interpolationEscaped(self):

        config = ConfigParser(r"""
        a = something
        b = \{header:a:okay\} else
        """)

        print(config._elements)

        self.assertEqual(config, {
            "a": "something",
            "b": r"\{header:a:okay\} else",
        })

    def test_interpolationWithType(self):

        config = ConfigParser(r"""
        a = 2,3,4
        (list) b = {a}
        """)

        self.assertEqual(config["b"], ["2","3","4"])

    def test_deepGet(self):

        config = ConfigParser(r"""
        basic = Still works
        [1]
            [2]
                [3]
                    key = value
                    (int) number = 10
        """)

        # Show basics
        self.assertEqual(config.get("basic"), "Still works")
        self.assertEqual(config.get("not present basic", "This is fine"), "This is fine")

        # Show traversal of keys
        self.assertEqual(config.get("1:2:3:key"), "value")
        self.assertEqual(config.get("1:2:3:number"), 10)
        self.assertEqual(config.get("1:2:3:not present"), None)
        self.assertEqual(config.get("1:2:3:not present", True), True)