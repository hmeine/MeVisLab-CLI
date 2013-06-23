import os, re, glob, cli_to_macro

def doImport():
    importPaths = re.split('[:;]', ctx.field('importPaths').value)
    
    targetDirectory = ctx.field('targetDirectory').value
    if not os.path.exists(targetDirectory):
        os.mkdir(targetDirectory)
    
    for index, total, path in cli_to_macro.importAllCLIs(importPaths, targetDirectory):
        print "%d/%d importing %s..." % (index, total, path)

def init():
    if not ctx.field('importPaths').value:
        found = []
        for pattern in ("/Applications/Slicer.app/Contents/lib/Slicer-*/cli-modules", ):
            found.extend(glob.glob(pattern))
        ctx.field('importPaths').value = ':'.join(found)
