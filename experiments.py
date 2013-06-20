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
    definition = MDLGroup("MacroModule", moduleName)
    defFile.append(definition)

    comment = cliModule.title
    if cliModule.version:
        comment += " v%s" % cliModule.version
    if cliModule.description:
        comment += " - " + cliModule.description
    definition.append(MDLTag(comment = comment))

    if cliModule.contributor:
        definition.append(MDLTag(author = re.sub(r' *\([^)]*\)', '', cliModule.contributor)))

    if cliModule.category:
        definition.append(MDLTag(keywords = "CLI " + cliModule.category.replace('.', ' ')))

    definition.append(MDLTag(externalDefinition = "$(LOCAL)/%s.script" % cliModule.name))

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
            definition.append(MDLTag(documentation = "$(LOCAL)/html/%s.html" % cliModule.name))

    # Interface section
    interface = MDLGroup("Interface")
    scriptFile.append(interface)

    inputsSection = MDLGroup("Inputs")
    outputsSection = MDLGroup("Outputs")
    parametersSection = MDLGroup("Parameters")

    # Commands section
    commands = MDLGroup("Commands")
    scriptFile.append(commands)

    commands.append(MDLTag(source = '$(LOCAL)/../CLIModuleBackend.py'))
    commands.append(MDLNewline)

    commands.append(MDLTag(initCommand = 'py: load(%r)' % os.path.abspath(cliModule.path)))
    commands.append(MDLNewline)

    listener = MDLGroup('FieldListener', 'update')
    listener.append(MDLTag(command = 'update'))
    commands.append(listener)

    autoApplyListener = MDLGroup('FieldListener', 'autoApply')
    autoApplyListener.append(MDLTag(command = 'updateIfAutoApply'))
    commands.append(autoApplyListener)

    autoUpdateListener = MDLGroup('FieldListener', 'autoUpdate')
    autoUpdateListener.append(MDLTag(command = 'updateIfAutoUpdate'))
    commands.append(autoUpdateListener)

    # transform parameters
    xInput = xOutput = 0
    for parameters in cliModule:
        for parameter in parameters:
            field = MDLGroup("Field", parameter.identifier())

            if parameter.description:
                field.append(MDLTag(comment = parameter.description))

            if parameter.typ == "image":
                # FIXME: voxel shift? compression?
                ioFields = MDLGroup("fields")
                ioFields.append(MDLTag(instanceName = parameter.identifier()))
                if parameter.channel == "input":
                    inputsSection.append(field)
                    field.append(MDLTag(internalName = "%s.input0" % parameter.identifier()))
                    module = MDLGroup("module", "itkImageFileWriter")
                    ioFields.append(MDLTag(forceDirectionCosineWrite = True))
                    x, y = xInput, 160
                    xInput += 200
                    autoUpdateListener.append(MDLTag(listenField = parameter.identifier()))
                elif parameter.channel == "output":
                    outputsSection.append(field)
                    field.append(MDLTag(internalName = "%s.output0" % parameter.identifier()))
                    module = MDLGroup("module", "itkImageFileReader")
                    x, y = xOutput, 0
                    xOutput += 200
                internal = MDLGroup("internal")
                internal.append(MDLTag(frame = "%d %d 120 64" % (x, y)))
                module.append(internal)
                ioFields.append(MDLTag(correctSubVoxelShift = True))
                module.append(ioFields)
                mlabFile.append(module)
            elif parameter.typ in SIMPLE_TYPE_MAPPING:
                field.append(MDLTag(type_ = SIMPLE_TYPE_MAPPING[parameter.typ]))
                if parameter.default is not None:
                    field.append(MDLTag('value', parameter.default))
                parametersSection.append(field)
                autoApplyListener.append(MDLTag(listenField = parameter.identifier()))
            elif parameter.typ.endswith("-vector"):
                field.append(MDLTag(type_ = 'String'))
                if parameter.default is not None:
                    field.append(MDLTag('value', parameter.default))
                parametersSection.append(field)
                autoApplyListener.append(MDLTag(listenField = parameter.identifier()))
            elif parameter.typ.endswith("-enumeration"):
                field.append(MDLTag(type_ = 'Enum'))
                items = MDLGroup("items")
                for item in parameter.elements:
                    #items.append(MDLGroup('item', item))
                    items.append(MDLTag('item', item))
                field.append(items)
                parametersSection.append(field)
                autoApplyListener.append(MDLTag(listenField = parameter.identifier()))
            else:
                logging.warning("Parameter type %r not yet supported" % parameter.typ)
                parametersSection.append(
                    MDLComment("Parameter %r with type %r not supported yet"
                               % (parameter.identifier(), parameter.typ)))

            if parameter.constraints:
                if parameter.constraints.minimum is not None:
                    field.append(MDLTag(min = parameter.constraints.minimum))
                if parameter.constraints.maximum is not None:
                    field.append(MDLTag(max = parameter.constraints.maximum))

            if parameter.hidden:
                field.append(MDLTag(hidden = True))

    field = MDLGroup('Field', 'autoUpdate')
    field.append(MDLTag(type_ = 'Bool'))
    parametersSection.append(field)

    field = MDLGroup('Field', 'autoApply')
    field.append(MDLTag(type_ = 'Bool'))
    parametersSection.append(field)

    field = MDLGroup('Field', 'update')
    field.append(MDLTag(type_ = 'Trigger'))
    parametersSection.append(field)

    if inputsSection:
        interface.append(inputsSection)
    if outputsSection:
        interface.append(outputsSection)
    if parametersSection:
        interface.append(parametersSection)

    return defFile, scriptFile, mlabFile, htmlFile

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
    #executablePath = cliModules[2]
    logging.info(executablePath)
    #ET.dump(elementTree)
    m = CLIModule(executablePath)
    m.argumentsAndOptions() # performs additional sanity checks

    mdefFile, scriptFile, mlabFile, htmlFile = mdlDescription(m)
    if defFile:
        defFile.append(MDLNewline)
    defFile.extend(mdefFile)
    with file("mdl/%s.script" % m.name, "w") as f:
        f.write(scriptFile.mdl())
    with file("mdl/%s.mlab" % m.name, "w") as f:
        f.write(mlabFile.mdl())
    if htmlFile is not None:
        with file("mdl/html/%s.html" % m.name, "w") as f:
            f.write(htmlFile)

with file("mdl/CLIModules.def", "w") as f:
    f.write(defFile.mdl())
