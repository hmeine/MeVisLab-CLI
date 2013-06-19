# see https://github.com/commontk/CTK/blob/master/Libs/CommandLineModules/Core/Resources/ctkCmdLineModule.xsd
# for what we aim to be able to parse

import os, sys, glob, subprocess, logging
import xml.etree.ElementTree as ET

logger = logging.getLogger(__name__)

def isCLIExecutable(filePath):
    # see qSlicerUtils::isCLIExecutable
    # e.g. https://github.com/Slicer/Slicer/blob/master/Base/QTCore/qSlicerUtils.cxx
    if not os.path.isfile(filePath):
        return False
    if sys.platform.startswith('win'):
        filePath = filePath.lower() # be case insensitive
        return filePath.endswith(".exe") or filePath.endswith(".bat")
    else:
        # differing from qSlicerUtils here, which does not check for executable bits
        # (this way we can differentiate between XML files saved with the same name
        # as the executables and the executables themselves)
        if not os.access(filePath, os.X_OK):
            return False
        return not '.' in os.path.basename(filePath)

def listCLIExecutables(baseDir):
    return [path for path in glob.glob(os.path.join(baseDir, '*'))
            if isCLIExecutable(path)]

def getXMLDescription(cliExecutable):
    p = subprocess.Popen([cliExecutable, '--xml'], stdout = subprocess.PIPE)
    return ET.parse(p.stdout)

# --------------------------------------------------------------------

def _tagToIdentifier(tagName):
    return tagName.replace('-', '_')

def _parseBool(x):
    if x in ('true', 'True', '1'):
        return True
    if x in ('false', 'False', '0'):
        return False
    raise ValueError, "cannot convert %r to boolean" % (x, )

def _tag(element):
    """Return element.tag with xmlns stripped away."""
    tag = element.tag
    if tag[0] == "{":
        uri, tag = tag[1:].split("}")
    return tag

def _uriPrefix(element):
    """Return xmlns prefix of the given element."""
    i = element.tag.find('}')
    if i < 0:
        return ""
    return element.tag[:i+1]


def _parseElements(self, elementTree, expectedTag = None):
    """Read REQUIRED_ELEMENTS and OPTIONAL_ELEMENTS and returns
    the rest of the children.  Every read child element's text
    value will be filled into an attribute of the same name,
    i.e. <description>Test</description> will lead to 'Test' being
    assigned to self.description.  Missing REQUIRED_ELEMENTS
    result in warnings."""

    xmlns = _uriPrefix(elementTree)

    if expectedTag is not None:
        assert _tag(elementTree) == expectedTag, 'expected <%s>, got <%s>' % (expectedTag, _tag(elementTree))

    parsed = []

    for tagName in self.REQUIRED_ELEMENTS + self.OPTIONAL_ELEMENTS:
        tags = elementTree.findall(xmlns + tagName)
        if tags:
            parsed.extend(tags)
            tagValue = tags[0].text
            tagValue = tagValue.strip() if tagValue else ""
            if len(tags) > 1:
                logger.warning("More than one <%s> found within %r (using only first)" % (tagName, _tag(elementTree)))
        else:
            tagValue = None
            if tagName in self.REQUIRED_ELEMENTS:
                logger.warning("Required element %r not found within %r" % (tagName, _tag(elementTree)))
        setattr(self, _tagToIdentifier(tagName), tagValue)

    return [tag for tag in elementTree if tag not in parsed]


class CLIModule(list):
    REQUIRED_ELEMENTS = ('title', 'description')

    OPTIONAL_ELEMENTS = ('category', 'version', 'documentation-url',
                         'license', 'contributor', 'acknowledgements')

    __slots__ = ('path', ) + tuple(map(_tagToIdentifier, REQUIRED_ELEMENTS + OPTIONAL_ELEMENTS))

    def __init__(self, path):
        self.path = path

        if isCLIExecutable(path):
            elementTree = getXMLDescription(path)
        else:
            with file(path) as f:
                elementTree = ET.parse(f)

        self._parse(elementTree.getroot())

    @property
    def name(self):
        return os.path.basename(self.path)

    def parameters(self):
        """Generator that recursively enumerates all parameters from
        all parameter groups"""
        for parameters in self:
            for parameter in parameters:
                yield parameter

    def argumentsAndOptions(self):
        """Return (arguments, options) tuple.  Together, the two lists
        contain all parameters (recursively fetched from all parameter
        groups), classified into optional parameters and required ones
        (with an index).  `arguments` contains the required arguments,
        already sorted by index."""
        arguments = []
        options = []
        for parameter in self.parameters():
            if parameter.index is not None:
                arguments.append(parameter)
                if parameter.flag is not None or parameter.longflag is not None:
                    logger.warning("Parameter %s has both index=%d and flag set." % (
                        parameter.identifier(), parameter.index))
            else:
                options.append(parameter)
        arguments.sort(key = lambda parameter: parameter.index)
        return (arguments, options)

    # this is called _parse, not parse (like in the classes below),
    # because it is not a classmethod that is supposed to be used as a
    # factory method from the outside, even if the signature and
    # content is really similar:
    def _parse(self, elementTree):
        childNodes = _parseElements(self, elementTree, 'executable')

        for pnode in childNodes:
            if _tag(pnode) == 'parameters':
                self.append(CLIParameters.parse(pnode))
            else:
                logger.warning("Element %r within %r not parsed" % (_tag(pnode), _tag(elementTree)))


class CLIParameters(list):
    REQUIRED_ELEMENTS = ('label', 'description')
    OPTIONAL_ELEMENTS = ()

    __slots__ = ("advanced", ) + REQUIRED_ELEMENTS

    @classmethod
    def parse(cls, elementTree):
        self = cls()
        
        childNodes = _parseElements(self, elementTree, 'parameters')
        
        self.advanced = _parseBool(elementTree.get('advanced', 'false'))

        for pnode in childNodes:
            self.append(CLIParameter.parse(pnode))

        return self


class CLIParameter(object):
    TYPES = (
        'boolean',
        'integer', 'float', 'double',
        'string', 'directory',
        'integer-vector', 'float-vector', 'double-vector',
        'string-vector',
        'integer-enumeration', 'float-enumeration', 'double-enumeration', 'string-enumeration',
        'point', 'region',
        'file', 'image', 'geometry',
        'transform', 'table', 'measurement',
    )

    PYTHON_TYPE_MAPPING = {
        'boolean' : bool,
        'integer' : int,
        'float' : float,
        'double' : float,
    }

    REQUIRED_ELEMENTS = ('name', 'description', 'label')

    OPTIONAL_ELEMENTS = (# either 'flag' or 'longflag' (or both) or 'index' are required
                         'flag', 'longflag', 'index',
                         'default', 'channel')
    
    __slots__ = ("typ", "hidden", "_pythonType") + REQUIRED_ELEMENTS + OPTIONAL_ELEMENTS + (
                 "constraints", # scalarVectorType, scalarType
                 "multiple", # multipleType
                 "elements", # enumerationType
                 "coordinateSystem", # pointType
                 "fileExtensions", # fileType
                 "subtype", # 'type' of imageType / geometryType
        )

    def identifier(self):
        result = self.name if self.name else self.longflag.lstrip('-')
        if not result:
            raise RuntimeError, "Cannot identify parameter either by name or by longflag (both missing)"
        return result

    def parseValue(self, value):
        if self.typ.endswith('-vector') and self.typ != 'string-vector':
            return map(self._pythonType, value.split(','))
        if self.typ == 'boolean':
            return _parseBool(value)
        return self._pythonType(value)

    @classmethod
    def parse(cls, elementTree):
        assert _tag(elementTree) in cls.TYPES, _tag(elementTree)

        self = cls()
        self.typ = _tag(elementTree)

        elementType = self.typ
        if elementType.endswith('-vector'):
            elementType = elementType[:-7]
        elif elementType.endswith('-enumeration'):
            elementType = elementType[:-12]
        self._pythonType = self.PYTHON_TYPE_MAPPING.get(elementType, str)

        self.hidden = _parseBool(elementTree.get('hidden', 'false'))

        self.constraints = None
        self.multiple = None
        self.elements = None
        self.coordinateSystem = None
        self.fileExtensions = None
        self.subtype = None

        for key, value in elementTree.items():
            if key == 'multiple':
                self.multiple = _parseBool(value)
            elif key == 'coordinateSystem':
                self.coordinateSystem = value
            elif key == 'coordinateSystem':
                self.coordinateSystem = value
            elif key == 'fileExtensions':
                self.fileExtensions = [ext.strip() for ext in value.split(",")]
            elif key == 'type':
                self.subtype = value
            elif key != 'hidden':
                logger.warning('attribute of %r ignored: %s=%r' % (_tag(elementTree), key, value))

        elements = []

        childNodes = _parseElements(self, elementTree)
        for n in childNodes:
            if _tag(n) == 'constraints':
                self.constraints = CLIConstraints.parse(n)
            elif _tag(n) == 'element':
                if not n.text:
                    logger.warning("Ignoring empty <element> within <%s>" % (_tag(elementTree), ))
                else:
                    elements.append(n.text)
            else:
                logger.warning("Element %r within %r not parsed" % (_tag(n), _tag(elementTree)))

        if self.flag and not self.flag.startswith('-'):
            self.flag = '-' + self.flag
        if self.longflag and not self.longflag.startswith('-'):
            self.longflag = '--' + self.longflag

        if self.index is not None:
            self.index = int(self.index)

        if self.default:
            self.default = self.parseValue(self.default)

        if self.typ.endswith('-enumeration'):
            self.elements = map(self.parseValue, elements)
            if not elements:
                logger.warning("No <element>s found within <%s>" % (_tag(elementTree), ))
        else:
            self.elements = None
            if elements:
                logger.warning("Ignoring <element>s within <%s>" % (_tag(elementTree), ))

        return self


class CLIConstraints(object):
    REQUIRED_ELEMENTS = ('step', )

    OPTIONAL_ELEMENTS = ('minimum', 'maximum')
    
    __slots__ = REQUIRED_ELEMENTS + OPTIONAL_ELEMENTS

    @classmethod
    def parse(cls, elementTree):
        self = cls()
        childNodes = _parseElements(self, elementTree, 'constraints')
        for n in childNodes:
            logger.warning("Element %r within %r not parsed" % (_tag(n), _tag(elementTree)))

        return self
