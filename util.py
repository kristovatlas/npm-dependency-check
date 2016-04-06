"""Utility functions"""

def standardize_str(string):
    """Returns a standardized form of the string-like argument.

    This will convert from a `unicode` object to a `str` object.
    """
    return str(string)

def rstrip_once(string, suffix_char):
    """If `suffix_char` is at end of `string`, remove it once."""
    assert isinstance(string, str), "type('%s')='%s'" % (string, type(string))
    if len(string) > 0 and string[-1] == suffix_char:
        return string[:-1]
    return string
