import os
import xml.etree.ElementTree as ET

from cli_modules import listCLIExecutables, getXMLDescription, CLIModule
from mdl import MDLGroup, MDLTag, MDLNewline

def mdlDescription(executablePath):
    moduleName = os.path.basename(executablePath)
    elementTree = getXMLDescription(executablePath)
    executable, = elementTree.findall('.')
    assert executable.tag == 'executable'

    result = MDLGroup("MacroModule", moduleName)
    version = None
    for el in executable:
        if el.tag == 'title':
            title = el.text
        elif el.tag == 'description':
            description = el.text
        elif el.tag == 'version':
            version = el.text
        elif el.tag == 'contributor':
            result.append(MDLTag(author = el.text))
    result.insert(0, MDLTag(comment = "%s%s - %s" % (title, " v%s" % version if version else "",
                                                     description)))
    
    interface = MDLGroup("Interface")
    result.append(MDLNewline())
    result.append(interface)

    inputsSection = MDLGroup("Inputs")
    outputsSection = MDLGroup("Outputs")
    parametersSection = MDLGroup("Parameters")

    for parameters in executable.findall('parameters'):
        for parameter in parameters:
            if parameter.tag == "image":
                if parameter.find('channel').text == 'input':
                    pass # FIXME

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


print mdlDescription(cliModules[10]).mdl()
