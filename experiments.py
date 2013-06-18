import os, logging
logging.basicConfig(format='%(asctime)s %(message)s')

from cli_modules import listCLIExecutables, getXMLDescription, CLIModule
from mdl import MDLGroup, MDLTag, MDLNewline

def mdlDescription(cliModule):
    moduleName = None # "CLI_" + os.path.basename(executablePath)

    result = MDLGroup("MacroModule", moduleName)

    comment = cliModule.title
    if cliModule.version:
        comment += " v%s" % cliModule.version
    if cliModule.description:
        comment += " - " + cliModule.description
    result.append(MDLTag(comment = comment))

    if cliModule.contributor:
        result.append(MDLTag(author = cliModule.contributor))

    if cliModule.category:
        result.append(MDLTag(keywords = "CLI " + cliModule.category.replace('.', ' ')))

    interface = MDLGroup("Interface")
    result.append(MDLNewline())
    result.append(interface)

    inputsSection = MDLGroup("Inputs")
    outputsSection = MDLGroup("Outputs")
    parametersSection = MDLGroup("Parameters")

    for parameters in cliModule:
        for parameter in parameters:
            print parameter.name

    if inputsSection:
        interface.append(inputsSection)
    if outputsSection:
        interface.append(outputsSection)
    if parametersSection:
        interface.append(parametersSection)

    return result
        
cliModules = listCLIExecutables('/Applications/Slicer.app/Contents/lib/Slicer-4.2/cli-modules')

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

elementTree = getXMLDescription(cliModules[10])
executable = elementTree.getroot()
m = CLIModule()
m.parse(executable)

print mdlDescription(m).mdl()
