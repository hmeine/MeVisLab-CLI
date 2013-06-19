import os, logging, sys, glob, re
#logging.basicConfig(format='  %(asctime)s %(message)s')
#logging.basicConfig(filename = 'warnings.txt', level = 0)
logging.basicConfig(stream = sys.stdout, level = 0) # easy grep'ping

from cli_modules import isCLIExecutable, listCLIExecutables, getXMLDescription, CLIModule
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
    definition = MDLGroup("MacroModule", moduleName)
    defFile.append(definition)
    scriptFile = MDLFile()
    interface = MDLGroup("Interface")
    scriptFile.append(interface)
    mlabFile = MDLFile()
    mlabFile.append(MDLComment('MDL v1 utf8'))
    #mlabFile.append(MDLGroup('network'))

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

    inputsSection = MDLGroup("Inputs")
    outputsSection = MDLGroup("Outputs")
    parametersSection = MDLGroup("Parameters")

    xInput = xOutput = 0

    for parameters in cliModule:
        for parameter in parameters:
            field = MDLGroup("Field", parameter.identifier())

            if parameter.description:
                field.append(MDLTag(comment = parameter.description))

            if parameter.typ == "image":
                # FIXME: voxel shift? compression?
                if parameter.channel == "input":
                    inputsSection.append(field)
                    field.append(MDLTag(internalName = "%s.input0" % parameter.identifier()))
                    module = MDLGroup("module", "itkImageFileWriter")
                    x, y = xInput, 160
                    xInput += 200
                elif parameter.channel == "output":
                    outputsSection.append(field)
                    field.append(MDLTag(internalName = "%s.output0" % parameter.identifier()))
                    module = MDLGroup("module", "itkImageFileReader")
                    x, y = xOutput, 0
                    xOutput += 200
                internal = MDLGroup("internal")
                internal.append(MDLTag(frame = "%d %d 120 64" % (x, y)))
                module.append(internal)
                bpFields = MDLGroup("fields")
                bpFields.append(MDLTag(instanceName = parameter.identifier()))
                module.append(bpFields)
                mlabFile.append(module)
            elif parameter.typ in SIMPLE_TYPE_MAPPING:
                field.append(MDLTag(type_ = SIMPLE_TYPE_MAPPING[parameter.typ]))
                if parameter.default is not None:
                    field.append(MDLTag('value', parameter.default))
                parametersSection.append(field)
            elif parameter.typ.endswith("-vector"):
                field.append(MDLTag(type_ = 'String'))
                if parameter.default is not None:
                    field.append(MDLTag('value', parameter.default))
                parametersSection.append(field)
            elif parameter.typ.endswith("-enumeration"):
                field.append(MDLTag(type_ = 'Enum'))
                items = MDLGroup("items")
                for item in parameter.elements:
                    #items.append(MDLGroup('item', item))
                    items.append(MDLTag('item', item))
                field.append(items)
                parametersSection.append(field)

            if parameter.constraints:
                if parameter.constraints.minimum is not None:
                    field.append(MDLTag(min = parameter.constraints.minimum))
                if parameter.constraints.maximum is not None:
                    field.append(MDLTag(max = parameter.constraints.maximum))

            if parameter.hidden:
                field.append(MDLTag(hidden = True))

    if inputsSection:
        interface.append(inputsSection)
    if outputsSection:
        interface.append(outputsSection)
    if parametersSection:
        interface.append(parametersSection)

    #mlabFile.append(MDLTag('connections'))
    #mlabFile.append(MDLTag('networkModel'))

    return defFile, scriptFile, mlabFile

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

import xml.etree.ElementTree as ET

defFile = MDLFile()

for executablePath in args:
    #executablePath = cliModules[2]
    logging.info(executablePath)
    if isCLIExecutable(executablePath):
        elementTree = getXMLDescription(executablePath)
    else:
        elementTree = ET.parse(file(executablePath))
    #ET.dump(elementTree)
    m = CLIModule(os.path.basename(executablePath))
    m.parse(elementTree.getroot())

    mdefFile, scriptFile, mlabFile = mdlDescription(m)
    if defFile:
        defFile.append(MDLNewline)
    defFile.extend(mdefFile)
    with file("mdl/%s.script" % m.name, "w") as f:
        f.write(scriptFile.mdl())
    with file("mdl/%s.mlab" % m.name, "w") as f:
        f.write(mlabFile.mdl())

with file("mdl/CLIModules.def", "w") as f:
    f.write(defFile.mdl())
