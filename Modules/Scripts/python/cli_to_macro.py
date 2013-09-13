"""Code for transforming CLI modules' XML descriptions into MeVisLab
macro modules, currently supporting most parameter types (see below).
The code makes use of the `cli_modules` module for parsing the XML
(into Python objects with the relevant attributes, values also parsed
into Python datatypes), and the (much less complex) `mdl_writer`
module for creating valid MDL code (.def/.script/.mlab files).

This is how the various parameter types are mapped:

boolean, integer, float, double, string
  directly converted to their MeVisLab counterparts

file, directory
  mapped to String fields, with browse button for 'input' channel

integer-vector, float-vector, double-vector
  mapped to String (via intermediate conversion to numeric vector, converting between comma-separated and space-separated values)

string-vector
  mapped to String (comma-separated, passed through without change)

integer-enumeration, float-enumeration, double-enumeration, string-enumeration
  mapped to Enum

point
  mapped to Vector3

region
  ???

image
  mapped to module inputs / outputs

geometry
  not supported yet, mapped to String fields with filenames

transform
  not supported yet (linear transforms could be mapped to Matrix fields), mapped to String fields with filenames

table
  not supported yet (maybe similar to StylePalette), mapped to String fields with filenames

measurement
  not supported yet (could become curve input/output), mapped to String fields with filenames
"""

import os, logging, re
logger = logging.getLogger(__name__)

from cli_modules import isCLIExecutable, CLIModule
from mdl_writer import MDLGroup, MDLNewline, MDLComment, MDLFile, MDLInclude

SIMPLE_TYPE_MAPPING = {
    'boolean'   : 'Bool',
    'integer'   : 'Integer',
    'float'     : 'Float',
    'double'    : 'Double',
    'string'    : 'String',

    'directory' : 'String',
    'file'      : 'String',
    }

def countFields(box):
    result = 0
    for el in box:
        if isinstance(el, MDLGroup) and el.tagName == 'Field':
            result += 1
    return result

def mdlDescription(cliModule, includePanelScreenshots = True):
    """Given CLIModule instance, return tuple (defFile, scriptFile,
    mlabFile, mhelpFile) containing a MeVisLab macro module
    definition.  The elements are MDLFile instances that can be
    converted into strings using their mdl() methods.  The .def file
    references the .script file in the same directory, and the
    mhelpFile should be placed in a subdirectory named 'mhelp' (as
    usual)."""
    
    moduleName = "CLI_" + cliModule.name

    defFile = MDLFile()
    scriptFile = MDLFile()
    mlabFile = MDLFile()
    mhelpFile = MDLFile()

    mlabFile.append(MDLComment('MDL v1 utf8'))

    # MacroModule definition & documentation
    definition = defFile.addGroup("MacroModule", moduleName)

    doc = mhelpFile.addGroup("ModuleHelp")
    docMeta = doc.addGroup("MetaInformation")
    docMeta.addTag(moduleName = moduleName)
    docMeta.addTag(moduleType = 'MacroModule')

    comment = cliModule.title
    docPurpose = cliModule.title
    if cliModule.version:
        comment += " v%s" % cliModule.version
        docPurpose += " (Version %s)" % cliModule.version
    if cliModule.description:
        comment += " - " + cliModule.description
        docPurpose += "\n%s\n\n%s\n" % ('-'*len(docPurpose), cliModule.description.rstrip())
    else:
        docPurpose += "\n"

    docUsage = """:module:`this` wraps a CLI module, which means that its execution (i.e. pressing :field:`update`) will save temporary files to disk, call the CLI executable behind the scenes, and load the results provided by it.  Compared with native MeVisLab modules, you will get limited feedback during execution, and the additional saving/loading of images introduces an additional cost (depending on the speed of your machine and I/O within the temporary directory).

This documentation is extracted from the CLI module's self-description."""
        
    if cliModule.documentation_url:
        url = cliModule.documentation_url
        if not url.startswith('http'):
            logger.warning("%r has a bad documentation url (%r)" % (cliModule.name, url))
        else:
            docUsage += " *Additional documentation* is provided at the following URL: %s\n" % (url, )

    if cliModule.acknowledgements:
        docPurpose += "\nAcknowledgements\n----------------\n\n%s\n" % (
            cliModule.acknowledgements.strip(), )
        
    if cliModule.license:
        docPurpose += "\nLicense\n-------\n\n%s\n" % (
            cliModule.license.strip(), )

    definition.addTag(comment = comment)

    if cliModule.contributor:
        authors = re.sub(r' *\([^)]*\)', '', cliModule.contributor)
        definition.addTag(author = authors)
        docMeta.addTag(author = authors)

    if cliModule.category:
        keywords = "CLI " + cliModule.category.replace('.', ' ')
        definition.addTag(keywords = keywords)
        docMeta.addTag(keywords = keywords)

    definition.addTag(externalDefinition = "$(LOCAL)/%s.script" % cliModule.name)

    # mhelp structure (mhelp parser needs a lot of empty groups/tags)
    doc.addGroup('Purpose').addTag(text = docPurpose)
    doc.addGroup('Usage').addTag(text = docUsage)
    doc.addGroup('Details').addTag(text = "")
    doc.addGroup('Interaction').addTag(text = "")
    doc.addGroup('Tips').addTag(text = "")

    if includePanelScreenshots:
        windows = doc.addGroup('Windows').addTag(text = "")
        for title in ('CLI GUI', ): # 'Execution Debugging'
            windows.addGroup('Window', title) \
              .addTag(title = "") \
              .addTag(text = ".. screenshot:: %s" % title)

    inputsDoc = doc.addGroup("Inputs")
    outputsDoc = doc.addGroup("Outputs")
    parametersDoc = doc.addGroup("Parameters")

    # Interface section
    interface = scriptFile.addGroup("Interface")

    inputsSection = MDLGroup("Inputs")
    outputsSection = MDLGroup("Outputs")
    parametersSection = MDLGroup("Parameters")

    # Commands section
    scriptFile.append(MDLNewline)
    commands = scriptFile.addGroup("Commands")

    commands.addTag(source = '$(LOCAL)/../CLIModuleBackend.py')
    commands.append(MDLNewline)

    commands.addTag(initCommand = 'checkCLI')
    commands.append(MDLNewline)

    commands.addGroup('FieldListener', 'update') \
        .addTag(command = 'update')

    autoApplyListener = commands.addGroup('FieldListener', 'autoApply') \
        .addTag(command = 'updateIfAutoApply')

    autoUpdateListener = commands.addGroup('FieldListener', 'autoUpdate') \
        .addTag(command = 'updateIfAutoUpdate')

    # transform parameters
    xInput = xOutput = 0
    for parameter in cliModule.parameters():
        field = MDLGroup("Field", parameter.identifier())
        fieldDoc = MDLGroup("Field", parameter.identifier())

        if parameter.typ == "image":
            if parameter.channel not in ('input', 'output'):
                logger.warning("image parameter (%r) has invalid channel (%r), don't know how to handle this!" % (
                        parameter.identifier(), parameter.channel))
                continue

            ioFields = MDLGroup("fields")
            ioFields.addTag(instanceName = parameter.identifier())
            if parameter.channel == "input":
                inputsSection.append(field)
                inputsDoc.append(fieldDoc)

                field.addTag(internalName = "%s.input0" % parameter.identifier())
                module = MDLGroup("module", "itkImageFileWriter")
                ioFields.addTag(forceDirectionCosineWrite = True)
                x, y = xInput, 160
                xInput += 200

                autoUpdateListener.addTag(listenField = parameter.identifier())
            else:
                assert parameter.channel == "output"
                outputsSection.append(field)
                outputsDoc.append(fieldDoc)

                field.addTag(internalName = "%s.output0" % parameter.identifier())
                module = MDLGroup("module", "itkImageFileReader")
                ioFields.addTag(autoDetermineDataType = True)
                x, y = xOutput, 0
                xOutput += 200

            # add reader/writer module to network:
            module.addGroup("internal") \
                .addTag(frame = "%d %d 120 64" % (x, y))
            ioFields.addTag(correctSubVoxelShift = True)
            module.append(ioFields)
            mlabFile.append(module)

            fieldDoc.addTag(type_ = 'Image')
        else:
            if parameter.typ in SIMPLE_TYPE_MAPPING:
                field.addTag(type_ = SIMPLE_TYPE_MAPPING[parameter.typ])
            elif parameter.typ.endswith("-vector"):
                field.addTag(type_ = 'String')
            elif parameter.typ.endswith("-enumeration"):
                field.addTag(type_ = 'Enum')
                items = field.addGroup("items")
                for item in parameter.elements:
                    items.addTag('item', item)
            elif parameter.typ == 'point':
                if parameter.multiple:
                    logger.warning("multiple points (%r) not yet supported" % parameter.identifier())
                field.addTag(type_ = 'Vector3')
            else:
                logger.warning("Parameter type %r not yet supported (using pass-through String field)"
                                % parameter.typ)
                field.addTag(type_ = 'String')

            fieldDoc.addTag(type_ = field.tag('type').value())

            if parameter.default is not None:
                field.addTag('value', parameter.default)

            if parameter.channel == 'output':
                if not parameter.isExternalType():
                    field.addTag('editable', False)
            else:
                autoApplyListener.addTag(listenField = parameter.identifier())

            parametersSection.append(field)
            parametersDoc.append(fieldDoc)

        fieldDoc.addTag(text = parameter.description or "")
        if parameter.typ != "image":
            # copy more parameter properties into the .mhelp file:
            if parameter.label:
                fieldDoc.addTag(title = parameter.label)
            fieldDoc.addTag(visibleInGUI = not parameter.hidden) # FIXME: crude heuristic

            if fieldDoc.tag('type').value() == 'Enum':
                items = fieldDoc.addGroup("items")
                for item in parameter.elements:
                    items.addTag('item', item)

            defaultValue = field.tag('value')
            if defaultValue is not None:
                fieldDoc.addTag(default = defaultValue.value())

        if parameter.constraints:
            if parameter.constraints.minimum is not None:
                field.addTag(min = parameter.constraints.minimum)
            if parameter.constraints.maximum is not None:
                field.addTag(max = parameter.constraints.maximum)

        if parameter.hidden:
            field.addTag(hidden = True)

    parametersSection.addGroup('Field', 'retainTemporaryFiles') \
        .addTag(type_ = 'Bool')

    parametersSection.addGroup('Field', 'cliExecutablePath') \
        .addTag(type_ = 'String') \
        .addTag('value', os.path.abspath(cliModule.path)) \
        .addTag(persistent = False)

    parametersSection.addGroup('Field', 'debugCommandline') \
        .addTag(type_ = 'String') \
        .addTag(editable = False)

    parametersSection.addGroup('Field', 'debugStdOut') \
        .addTag(type_ = 'String') \
        .addTag(editable = False)

    parametersSection.addGroup('Field', 'debugStdErr') \
        .addTag(type_ = 'String') \
        .addTag(editable = False)

    parametersSection.addGroup('Field', 'autoUpdate') \
        .addTag(type_ = 'Bool')

    parametersSection.addGroup('Field', 'autoApply') \
        .addTag(type_ = 'Bool')

    parametersSection.addGroup('Field', 'update') \
        .addTag(type_ = 'Trigger')

    parametersDoc.addGroup('Field', 'retainTemporaryFiles') \
        .addTag(type_ = 'Bool') \
        .addTag(text = 'Do not delete temporary files after CLI execution') \
        .addTag(title = 'Retain Temporary Files')

    parametersDoc.addGroup('Field', 'cliExecutablePath') \
        .addTag(type_ = 'String') \
        .addTag(text = 'Path of the CLI executable to run (set by CLIImporter)') \
        .addTag(title = 'Executable Path') \
        .addTag(persistent = False)

    parametersDoc.addGroup('Field', 'debugCommandline') \
        .addTag(type_ = 'String') \
        .addTag(text = 'Full commandline used for executing the CLI module.  Actually, this string is composed for debugging; the real execution does not use this exact quoting (but calls a library function that takes arguments within an array).') \
        .addTag(persistent = False)

    parametersDoc.addGroup('Field', 'debugStdOut') \
        .addTag(type_ = 'String') \
        .addTag(text = 'Standard output collected during CLI execution') \
        .addTag(persistent = False)

    parametersDoc.addGroup('Field', 'debugStdErr') \
        .addTag(type_ = 'String') \
        .addTag(text = 'Standard error collected during CLI execution (may be very helpful if the module does not work as expected)') \
        .addTag(persistent = False)

    parametersDoc.addGroup('Field', 'autoUpdate') \
        .addTag(type_ = 'Bool') \
        .addTag(text = 'Automatically execute CLI module whenever any one of the input images changes (may be slow, use carefully)') \
        .addTag(title = 'Auto update') \
        .addTag(visibleInGUI = True)

    parametersDoc.addGroup('Field', 'autoApply') \
        .addTag(type_ = 'Bool') \
        .addTag(text = 'Automatically execute CLI module whenever any one of the input parameters changes (may be slow, use carefully)') \
        .addTag(title = 'Auto apply') \
        .addTag(visibleInGUI = True)

    parametersDoc.addGroup('Field', 'update') \
        .addTag(type_ = 'Trigger') \
        .addTag(text = 'Execute the CLI module') \
        .addTag(title = 'Update') \
        .addTag(visibleInGUI = True)

    if inputsSection:
        interface.append(inputsSection)
    if outputsSection:
        interface.append(outputsSection)
    if parametersSection:
        interface.append(parametersSection)

    scriptFile.append(MDLNewline)
    window = scriptFile.addGroup('Window', 'CLI GUI') \
        .addGroup('Category') \
        .addTag(expandY = True)

    main = []
    advanced = []
    for parameters in cliModule:
        box = MDLGroup('Box', parameters.label)
        if parameters.description:
            box.addTag(tooltip = parameters.description)
        for parameter in parameters:
            if parameter.typ == 'image':
                continue # already exposed is module input/output
            elif parameter.typ in ('file', 'directory') or parameter.isExternalType():
                field = box.addGroup('Field', parameter.identifier())
                if parameter.label:
                    field.addTag(title = parameter.label)
                if parameter.channel != 'output':
                    field.addTag(browseButton = True)
                    if parameter.typ == 'directory':
                        field.addTag(browseMode = 'Directory')
                    if parameter.fileExtensions:
                        field.addTag(browseFilter = "Supported files (%s);;All files (*)"
                                     % " ".join('*%s' % ext for ext in parameter.fileExtensions))
            else:
                field = box.addGroup('Field', parameter.identifier())
            if parameter.constraints:
                if parameter.constraints.step is not None:
                    field.addTag(step = parameter.constraints.step)
        if not countFields(box):
            continue # skip empty boxes (e.g. only image I/O)
        if parameters.advanced:
            advanced.append(box)
        else:
            main.append(box)

    # got (non-empty) groups, distribute over multiple tabs:
    tabs = []
    for boxes, category in ((main, 'Main'),
                            (advanced, 'Advanced')):
        if not boxes:
            continue
        pages = [[]]
        for box in boxes:
            if sum(countFields(box) for box in pages[-1]) > 15:
                pages.append([])
            pages[-1].append(box)

        # assign names to tabs:
        if len(pages) == 1:
            tabs.append((category, pages[0]))
        else:
            for i, page in enumerate(pages):
                tabs.append(('%s %d' % (category, i+1), page))

    if len(tabs) == 1:
        title, page = tabs[0]
        if len(page) == 1:
            window.extend(page[0])
        else:
            window.extend(page)
    else:
        tabView = window.addGroup("TabView")
        for title, page in tabs:
            tab = tabView.addGroup('Category', title)
            if len(page) == 1:
                tab.extend(page[0])
            else:
                tab.extend(page)

    # execution controls
    hori = window.addGroup("Horizontal")
    hori.addGroup('CheckBox', 'autoApply')
    hori.addGroup('CheckBox', 'autoUpdate')
    hori.addGroup('Button', 'update')

    # debug Window section
    scriptFile.append(MDLNewline)
    scriptFile.append(MDLInclude('$(LOCAL)/../DebugWindow.script'))

    return defFile, scriptFile, mlabFile, mhelpFile

def cliToMacroModule(executablePath, targetDirectory, defFile = True,
                     includePanelScreenshots = True):
    """Write .script/.mlab/.mhelp files for the CLI module `executablePath`
    to `targetDirectory`[/mhelp].  If `defFile` is set to an MLDFile instance,
    the .def file contents are appended to that object, otherwise a
    .def file for that single module gets written."""
    
    logger.info("processing %s..." % executablePath)
    #ET.dump(elementTree)
    m = CLIModule(executablePath)
    m.classifyParameters() # performs additional sanity checks

    mdefFile, scriptFile, mlabFile, mhelpFile = mdlDescription(m, includePanelScreenshots)
    if defFile is True:
        mdefFile.write(os.path.join(targetDirectory, "%s.def" % m.name))
    else:
        if defFile: # not empty, add separating newline
            defFile.append(MDLNewline)
        defFile.extend(mdefFile)

    scriptFile.write(os.path.join(targetDirectory, "%s.script" % m.name))
    mlabFile.write(os.path.join(targetDirectory, "%s.mlab" % m.name))
    mhelpFile.write(os.path.join(targetDirectory, "mhelp", "CLI_%s.mhelp" % m.name))

    return mdefFile

def importAllCLIs(importPaths, targetDirectory, defFileName = 'CLIModules.def',
                  includePanelScreenshots = True):
    """Generator function that imports any number of CLI modules at
    once.  `importPaths` shall contain either directory names to be
    scanned (non-recursively) or paths of CLI executables.  Before
    importing, the target directory will be wiped.  All module
    definitions will be put into the same .def file, and all generated
    files will be written to `targetDirectory` and an 'mhelp'
    subdirectory, which must both exist already.  See
    `cliToMacroModule` for more information.  The generator will yield
    (index, total, path) tuples for progress display (index being
    1-based for this purpose)."""

    defFile = MDLFile()

    executablePaths = []

    for path in importPaths:
        if os.path.isdir(path):
            for entry in sorted(os.listdir(path)):
                entry = os.path.join(path, entry)
                if isCLIExecutable(entry):
                    executablePaths.append(entry)
        elif isCLIExecutable(path):
            executablePaths.append(path)

    successful = 0
    total = len(executablePaths)
    for i, path in enumerate(executablePaths):
        yield (i, successful, total, path)
        try:
            cliToMacroModule(path, targetDirectory, defFile,
                             includePanelScreenshots)
            successful += 1
        except StandardError, e:
            logger.error(str(e))
    yield (total, successful, total, "")

    with file(os.path.join(targetDirectory, defFileName), "w") as f:
        # the XML files may contain non-ascii characters; don't fail with
        # "UnicodeEncodeError: 'ascii' codec can't encode ..."
        mdl = defFile.mdl()
        if isinstance(mdl, unicode):
            mdl = mdl.encode('latin-1', 'ignore')
        f.write(mdl)
