import os, re, glob, logging, cli_to_macro
from PythonQt import Qt, QtGui

logging.basicConfig() # no-op if there is already a configuration

DEFAULT_SEARCH_PATHS = (
    "/Applications/Slicer.app/Contents/lib/Slicer-*/cli-modules",
    "~/Slicer*/lib/Slicer-*/cli-modules",
    )

def doImport(field = None, window = None):
    importPaths = re.split('[:;]', ctx.field('importPaths').value)
    
    targetDirectory = ctx.field('targetDirectory').value
    if not os.path.exists(targetDirectory):
        os.mkdir(targetDirectory)

    pd = QtGui.QProgressDialog(window.widget() if window else None)
    pd.setWindowModality(Qt.Qt.WindowModal)
     
    for index, total, path in cli_to_macro.importAllCLIs(importPaths, targetDirectory):
        print "%d/%d importing %s..." % (index, total, path)
        pd.setValue(index - 1)
        pd.setMaximum(total)
        pd.setLabelText(os.path.basename(path))
        if pd.wasCanceled:
            break

    pd.setValue(total)

    if not pd.wasCanceled:
        QtGui.QMessageBox.information(
            pd, "Done",
            "%s modules successfully imported. "
            "You probably need to reload the module database (via the 'Extras' menu) now."
            % (total, ))
        if window:
            window.close()

def importAndClose():
    doImport(ctx.window())

def init():
    if not ctx.field('importPaths').value:
        found = []
        for pattern in DEFAULT_SEARCH_PATHS:
            found.extend(glob.glob(os.path.expanduser(pattern)))
        ctx.field('importPaths').value = ':'.join(found)
