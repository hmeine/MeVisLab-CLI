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

def mdlDescription(cliModule):
    """Given CLIModule instance, return tuple (defFile, scriptFile,
    mlabFile, htmlFile) containing a MeVisLab macro module definition.
    The first three items are MDLFile instances that can be converted
    into strings using their mdl() methods, while htmlFile is actually
    a string containing an HTML file (that redirects to the module's
    documentation URL).  If no proper documentation URL is given,
    htmlFile is None.  The .def file references the .script file in
    the same directory, and the htmlFile should be placed in a
    subdirectory named 'html'."""
    
    moduleName = "CLI_" + cliModule.name

    defFile = MDLFile()
    scriptFile = MDLFile()
    mlabFile = MDLFile()
    mlabFile.append(MDLComment('MDL v1 utf8'))
    htmlFile = None

    # MacroModule definition
    definition = defFile.addGroup("MacroModule", moduleName)

    comment = cliModule.title
    if cliModule.version:
        comment += " v%s" % cliModule.version
    if cliModule.description:
        comment += " - " + cliModule.description
    definition.addTag(comment = comment)

    if cliModule.contributor:
        definition.addTag(author = re.sub(r' *\([^)]*\)', '', cliModule.contributor))

    if cliModule.category:
        definition.addTag(keywords = "CLI " + cliModule.category.replace('.', ' '))

    definition.addTag(externalDefinition = "$(LOCAL)/%s.script" % cliModule.name)

    if cliModule.documentation_url:
        if not cliModule.documentation_url.startswith('http'):
            logger.warning("%r has a bad documentation url (%r)" % (cliModule.name, cliModule.documentation_url))
        else:
            htmlFile = """<html>
<head>
<meta http-equiv="refresh" content="1;url=%(url)s">
<script type="text/javascript">window.location.href = "%(url)s"</script>
<title>%(name)s documentation</title>
</head>
<body>
<p>You should be automatically redirected to <em>%(name)s</em>'s documentation at <a href="%(url)s">%(url)s</a>.</p>
</body>
</html>""" % dict(url = cliModule.documentation_url,
                  name = cliModule.name)
            definition.addTag(documentation = "$(LOCAL)/html/%s.html" % cliModule.name)

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

        if parameter.description:
            field.addTag(comment = parameter.description)

        if parameter.typ == "image":
            # FIXME: voxel shift? compression?
            ioFields = MDLGroup("fields")
            ioFields.addTag(instanceName = parameter.identifier())
            if parameter.channel == "input":
                inputsSection.append(field)
                field.addTag(internalName = "%s.input0" % parameter.identifier())
                module = MDLGroup("module", "itkImageFileWriter")
                ioFields.addTag(forceDirectionCosineWrite = True)
                x, y = xInput, 160
                xInput += 200
                autoUpdateListener.addTag(listenField = parameter.identifier())
            elif parameter.channel == "output":
                outputsSection.append(field)
                field.addTag(internalName = "%s.output0" % parameter.identifier())
                module = MDLGroup("module", "itkImageFileReader")
                x, y = xOutput, 0
                xOutput += 200
            module.addGroup("internal") \
                .addTag(frame = "%d %d 120 64" % (x, y))
            ioFields.addTag(correctSubVoxelShift = True)
            module.append(ioFields)
            mlabFile.append(module)
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

            if parameter.default is not None:
                field.addTag('value', parameter.default)

            if parameter.channel == 'output':
                field.addTag('editable', False)
            else:
                autoApplyListener.addTag(listenField = parameter.identifier())

            parametersSection.append(field)

        if parameter.constraints:
            if parameter.constraints.minimum is not None:
                field.addTag(min = parameter.constraints.minimum)
            if parameter.constraints.maximum is not None:
                field.addTag(max = parameter.constraints.maximum)

        if parameter.hidden:
            field.addTag(hidden = True)

    parametersSection.addGroup('Field', 'retainTemporaryFiles') \
        .addTag(type_ = 'Bool') # no visible effect for parameter fields

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

    if inputsSection:
        interface.append(inputsSection)
    if outputsSection:
        interface.append(outputsSection)
    if parametersSection:
        interface.append(parametersSection)

    scriptFile.append(MDLNewline)
    window = scriptFile.addGroup('Window', 'CLI GUI') \
        .addGroup('Vertical') \
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
    hori.addGroup('Field', 'autoApply')
    hori.addGroup('Field', 'autoUpdate')
    hori.addGroup('Button', 'update')

    # debug Window section
    scriptFile.append(MDLNewline)
    scriptFile.append(MDLInclude('$(LOCAL)/../DebugWindow.script'))

    return defFile, scriptFile, mlabFile, htmlFile

def cliToMacroModule(executablePath, targetDirectory, defFile = True):
    """Write .script/.mlab files for the CLI module `executablePath`
    to `targetDirectory`.  If `defFile` is set to an MLDFile instance,
    the .def file contents are appended to that object, otherwise a
    .def file for that single module gets written.  (An HTML
    documentation file may get written to an 'html' subdirectory,
    too.)"""
    
    logger.info("processing %s..." % executablePath)
    #ET.dump(elementTree)
    m = CLIModule(executablePath)
    m.classifyParameters() # performs additional sanity checks

    mdefFile, scriptFile, mlabFile, htmlFile = mdlDescription(m)
    if defFile is True:
        with file(os.path.join(targetDirectory, "%s.def" % m.name), "w") as f:
            f.write(mdefFile.mdl())
    else:
        if defFile: # not empty, add separating newline
            defFile.append(MDLNewline)
        defFile.extend(mdefFile)

    with file(os.path.join(targetDirectory, "%s.script" % m.name), "w") as f:
        f.write(scriptFile.mdl())
    with file(os.path.join(targetDirectory, "%s.mlab" % m.name), "w") as f:
        f.write(mlabFile.mdl())
    if htmlFile is not None:
        if not os.path.exists(os.path.join(targetDirectory, "html")):
            os.mkdir(os.path.join(targetDirectory, "html"))
        with file(os.path.join(targetDirectory, "html", "%s.html" % m.name), "w") as f:
            f.write(htmlFile)

    return mdefFile

def importAllCLIs(importPaths, targetDirectory, defFileName = 'CLIModules.def'):
    """Imports any number of CLI modules at once.  `importPaths` shall
    contain either directory names to be scanned (non-recursively) or
    paths of CLI executables.  All module definitions will be put into
    the same .def file, and all generated files will be written to
    `targetDirectory` (or into an 'html' subdirectory).  See
    `cliToMacroModule` for more information."""

    defFile = MDLFile()

    for path in importPaths:
        if os.path.isdir(path):
            for entry in sorted(os.listdir(path)):
                entry = os.path.join(path, entry)
                if isCLIExecutable(entry):
                    importPaths.append(entry)
        else:
            cliToMacroModule(path, targetDirectory, defFile)

    with file(os.path.join(targetDirectory, defFileName), "w") as f:
        f.write(defFile.mdl())
