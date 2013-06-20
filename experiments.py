import os, logging, sys, glob, re
#logging.basicConfig(format='  %(asctime)s %(message)s')
#logging.basicConfig(filename = 'warnings.txt', level = 0)
logging.basicConfig(stream = sys.stdout, level = 0) # easy grep'ping

from cli_modules import listCLIExecutables, CLIModule
from mdl import MDLGroup, MDLTag, MDLNewline, MDLComment, MDLFile

SIMPLE_TYPE_MAPPING = {
    'boolean'   : 'Bool',
    'integer'   : 'Integer',
    'float'     : 'Float',
    'double'    : 'Double',
    'string'    : 'String',
    'directory' : 'String',
    'file'      : 'String',
    }

def mdlDescription(cliModule):
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
            logging.warning("%r has a bad documentation url (%r)" % (cliModule.name, cliModule.documentation_url))
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
    commands = scriptFile.addGroup("Commands")

    commands.addTag(source = '$(LOCAL)/../CLIModuleBackend.py')
    commands.append(MDLNewline)

    commands.addTag(initCommand = 'py: load(%r)' % os.path.abspath(cliModule.path))
    commands.append(MDLNewline)

    listener = MDLGroup('FieldListener', 'update')
    listener.addTag(command = 'update')
    commands.append(listener)

    autoApplyListener = MDLGroup('FieldListener', 'autoApply')
    autoApplyListener.addTag(command = 'updateIfAutoApply')
    commands.append(autoApplyListener)

    autoUpdateListener = MDLGroup('FieldListener', 'autoUpdate')
    autoUpdateListener.addTag(command = 'updateIfAutoUpdate')
    commands.append(autoUpdateListener)

    # transform parameters
    xInput = xOutput = 0
    for parameters in cliModule:
        for parameter in parameters:
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
                internal = MDLGroup("internal")
                internal.addTag(frame = "%d %d 120 64" % (x, y))
                module.append(internal)
                ioFields.addTag(correctSubVoxelShift = True)
                module.append(ioFields)
                mlabFile.append(module)
            elif parameter.typ in SIMPLE_TYPE_MAPPING:
                field.addTag(type_ = SIMPLE_TYPE_MAPPING[parameter.typ])
                if parameter.default is not None:
                    field.addTag('value', parameter.default)
                parametersSection.append(field)
                autoApplyListener.addTag(listenField = parameter.identifier())
            elif parameter.typ.endswith("-vector"):
                field.addTag(type_ = 'String')
                if parameter.default is not None:
                    field.addTag('value', parameter.default)
                parametersSection.append(field)
                autoApplyListener.addTag(listenField = parameter.identifier())
            elif parameter.typ.endswith("-enumeration"):
                field.addTag(type_ = 'Enum')
                items = MDLGroup("items")
                for item in parameter.elements:
                    #items.append(MDLGroup('item', item))
                    items.addTag('item', item)
                field.append(items)
                parametersSection.append(field)
                autoApplyListener.addTag(listenField = parameter.identifier())
            else:
                logging.warning("Parameter type %r not yet supported" % parameter.typ)
                parametersSection.append(
                    MDLComment("Parameter %r with type %r not supported yet"
                               % (parameter.identifier(), parameter.typ)))

            if parameter.constraints:
                if parameter.constraints.minimum is not None:
                    field.addTag(min = parameter.constraints.minimum)
                if parameter.constraints.maximum is not None:
                    field.addTag(max = parameter.constraints.maximum)

            if parameter.hidden:
                field.addTag(hidden = True)

    field = MDLGroup('Field', 'retainTemporaryFiles')
    field.addTag(type_ = 'Bool')
    field.addTag(hidden = True) # no visible effect for parameter fields
    parametersSection.append(field)

    field = MDLGroup('Field', 'commandline')
    field.addTag(type_ = 'String')
    field.addTag(hidden = True) # no visible effect for parameter fields
    field.addTag(editable = False)
    parametersSection.append(field)

    field = MDLGroup('Field', 'autoUpdate')
    field.addTag(type_ = 'Bool')
    parametersSection.append(field)

    field = MDLGroup('Field', 'autoApply')
    field.addTag(type_ = 'Bool')
    parametersSection.append(field)

    field = MDLGroup('Field', 'update')
    field.addTag(type_ = 'Trigger')
    parametersSection.append(field)

    if inputsSection:
        interface.append(inputsSection)
    if outputsSection:
        interface.append(outputsSection)
    if parametersSection:
        interface.append(parametersSection)

    return defFile, scriptFile, mlabFile, htmlFile

def cliToMacroModule(executablePath, targetDirectory, defFile = True):
    """Write .script/.mlab files for the CLI module `executablePath`
    to `targetDirectory`.  If `defFile` is set to an MLDFile instance,
    the .def file contents are appended to that object, otherwise a
    .def file for that single module gets written."""
    logging.info(executablePath)
    #ET.dump(elementTree)
    m = CLIModule(executablePath)
    m.argumentsAndOptions() # performs additional sanity checks

    mdefFile, scriptFile, mlabFile, htmlFile = mdlDescription(m)
    if defFile is True:
        with file(os.path.join(targetDirectory, "%s.def" % m.name), "w") as f:
            f.write(mdefFile.mdl())
    else:
        if defFile:
            defFile.append(MDLNewline)
        defFile.extend(mdefFile)

    with file(os.path.join(targetDirectory, "%s.script" % m.name), "w") as f:
        f.write(scriptFile.mdl())
    with file(os.path.join(targetDirectory, "%s.mlab" % m.name), "w") as f:
        f.write(mlabFile.mdl())
    if htmlFile is not None:
        with file(os.path.join(targetDirectory, "html", "%s.html" % m.name), "w") as f:
            f.write(htmlFile)

    return mdefFile

cliModules = listCLIExecutables('/Applications/Slicer.app/Contents/lib/Slicer-4.2/cli-modules')
xmlFiles = glob.glob("xml/*")

args = sys.argv[1:] or xmlFiles # cliModules

# for e in cliModules:
#     import subprocess
#     with open("xml/%s" % os.path.basename(e), "w") as f:
#         p = subprocess.Popen([e, '--xml'], stdout = subprocess.PIPE)
#         f.write(p.stdout.read())

# SLOW, should probably be deleted:
# def listCLIModules(baseDir):
#     result = []
#     for executable in listCLIExecutables(baseDir):
#         result.append(getXMLDescription(executable))
#     return result

defFile = MDLFile()

for executablePath in args:
    cliToMacroModule(executablePath, "mdl", defFile)

with file("mdl/CLIModules.def", "w") as f:
    f.write(defFile.mdl())
