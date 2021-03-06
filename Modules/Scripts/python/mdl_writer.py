# Copyright (c) Fraunhofer MEVIS, Germany. All rights reserved.
# **InsertLicense** code
"""This module contains classes for convenient creation of
syntactically valid (and nicely formatted) MDL files.
"""

import re

def mdlValue(value):
    """Convert python value into MDL string representation.  Lists are
    converted into space-separated vector strings, assuming numeric
    elements."""
    if isinstance(value, bool):
        return "yes" if value else "no"
    elif isinstance(value, list):
        value = " ".join(map(mdlValue, value))
    value = str(value)
    if value == '':
        return '""'
    if "\n" in value:
        return '"*%s*"' % value.replace('\\', '\\\\').replace('"*', '"\\*')
    if re.search('[ \t{}=]', value) or '//' in value:
        return '"%s"' % re.sub(r'(["\\])', r'\\\1', value)
    return value


class MDLTag(object):
    def __init__(self, name = None, value = '', **kwargs):
        if name is None:
            (name, value), = kwargs.items()
            if name == 'type_':
                name = 'type'
        elif kwargs:
            raise ValueError("MDLTag: use either positional args or kwargs, not both!")
        self.tagName = name
        self.tagValue = value

    def name(self):
        return self.tagName

    def value(self):
        return self.tagValue

    def mdl(self, indentation = ""):
        return "%s%s = %s" % (indentation,
                              mdlValue(self.tagName),
                              mdlValue(self.tagValue))


class _MDLParent(list):
    def addGroup(self, *args):
        result = MDLGroup(*args)
        self.append(result)
        return result

    def addTag(self, *args, **kwargs):
        result = MDLTag(*args, **kwargs)
        self.append(result)
        return self

    def tag(self, name):
        for child in self:
            if isinstance(child, MDLTag) and child.name() == name:
                return child

    def group(self, name, value = None):
        for child in self:
            if isinstance(child, MDLGroup) and child.name() == name and \
              child.value() == value:
                return child
    

class MDLGroup(_MDLParent):
    def __init__(self, tagName, tagValue = None):
        self.tagName = tagName
        self.tagValue = tagValue

    def name(self):
        return self.tagName

    def value(self):
        return self.tagValue

    def mdl(self, indentation = ""):
        content = [child.mdl(indentation + "  ")
                   for child in self]
        result = indentation + self.tagName
        if self.tagValue is not None:
            result += " " + mdlValue(self.tagValue)
        if content:
            return "%s {\n%s\n%s}" % (result, "\n".join(content), indentation)
        else:
            return "%s {}" % (result, )


class MDLNewline(object):
    @staticmethod
    def mdl(indentation = ""):
        return ""


class MDLComment(object):
    def __init__(self, comment):
        self.comment = comment

    def mdl(self, indentation = ""):
        return "\n".join("%s// %s" % (indentation, line)
                         for line in self.comment.split("\n"))


class MDLFile(_MDLParent):
    def mdl(self):
        return "\n".join(element.mdl() for element in self) + "\n"

    def write(self, filename):
        with open(filename, 'w') as f:
            f.write(self.mdl())


class MDLInclude(object):
    def __init__(self, include):
        self.include = include

    def mdl(self, indentation = ""):
        return "%s#include %s" % (indentation, mdlValue(self.include))

# --------------------------------------------------------------------

def test_simple_quoting():
    assert mdlValue('Simple') == 'Simple'
    assert mdlValue(42) == '42'
    assert mdlValue('Test Me') == '"Test Me"'

def test_quoting_of_special_chars():
    assert mdlValue(r'\n needs quoting') == r'"\\n needs quoting"'
    assert mdlValue('42" Monitor') == '"42\\" Monitor"'
    assert mdlValue('def test():\n  assert True') == '"*def test():\n  assert True*"'

def test_advanced_quoting():
    assert mdlValue('def test():\n  print "Hello\\nWorld"') == '"*def test():\n  print "Hello\\\\nWorld"*"'

def test_hierarchy():
    g = MDLGroup("myGroup", "exampleGroup")
    g.append(MDLTag(normalTag = "This is a normal tag"))
    inner = MDLGroup('groupInside')
    inner.append(MDLTag(insideTag = "Another example tag"))
    g.append(inner)
    assert g.mdl() == """myGroup exampleGroup {
  normalTag = "This is a normal tag"
  groupInside {
    insideTag = "Another example tag"
  }
}"""

def test_tagOnlyGroup():
    g = MDLGroup('tagOnlyGroup')
    g.append(MDLTag(normalTag = "This group has no value"))
    assert g.mdl() == """tagOnlyGroup {
  normalTag = "This group has no value"
}"""
