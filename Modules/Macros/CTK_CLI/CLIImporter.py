import os, re, glob, cli_to_macro

def doImport():
    importPaths = re.split('[:;]', ctx.field('importPaths').value)
    
    targetDirectory = ctx.field('targetDirectory').value
    if not os.path.exists(targetDirectory):
        os.mkdir(targetDirectory)
    
    cli_to_macro.importAllCLIs(importPaths, targetDirectory)

def init():
    if not ctx.field('importPaths').value:
        found = []
        for pattern in ("/Applications/Slicer.app/Contents/lib/Slicer-*/cli-modules", ):
            found.extend(glob.glob(pattern))
        ctx.field('importPaths').value = ':'.join(found)
