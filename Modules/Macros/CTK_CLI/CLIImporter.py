import os, re, glob, logging, cli_to_macro
from PythonQt import Qt, QtGui

logging.basicConfig() # no-op if there is already a configuration

DEFAULT_SEARCH_PATHS = (
    "/Applications/Slicer.app/Contents/lib/Slicer-*/cli-modules",
    "~/Slicer*/lib/Slicer-*/cli-modules",
    )

def doImport():
    importPaths = re.split('[:;]', ctx.field('importPaths').value)
    
    targetDirectory = ctx.field('targetDirectory').value
    if not os.path.exists(targetDirectory):
        os.mkdir(targetDirectory)

    pd = QtGui.QProgressDialog()
    pd.setWindowModality(Qt.Qt.WindowModal)
     
    for index, total, path in cli_to_macro.importAllCLIs(importPaths, targetDirectory):
        print "%d/%d importing %s..." % (index, total, path)
        pd.setValue(index - 1)
        pd.setMaximum(total)
        pd.setLabelText(os.path.basename(path))
        if pd.wasCanceled:
            break

def init():
    if not ctx.field('importPaths').value:
        found = []
        for pattern in DEFAULT_SEARCH_PATHS:
            found.extend(glob.glob(os.path.expanduser(pattern)))
        ctx.field('importPaths').value = ':'.join(found)
