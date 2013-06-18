import re

def mdlValue(value):
    value = str(value)
    if "\n" in value:
        return '"*%s*"' % value.replace('\\', '\\\\').replace('"*', '"\\*')
    if re.search('[ \t]', value):
        return '"%s"' % re.sub(r'(["\\])', r'\\\1', value)
    return value


class MDLTag(object):
    def __init__(self, **kwargs):
        (name, value), = kwargs.items()
        self.tagName = name
        self.tagValue = value

    def mdl(self, indentation = ""):
        return "%s%s = %s" % (indentation,
                              mdlValue(self.tagName),
                              mdlValue(self.tagValue))


class MDLGroup(list):
    def __init__(self, tagName, tagValue = None):
        self.tagName = tagName
        self.tagValue = tagValue

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
    def mdl(self, indentation = ""):
        return ""

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
