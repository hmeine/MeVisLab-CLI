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
     
    for index, successful, total, path in cli_to_macro.importAllCLIs(importPaths, targetDirectory):
        print "%d/%d importing %s..." % (index+1, total, path)
        pd.setValue(index)
        pd.setMaximum(total)
        if path:
            pd.setLabelText(os.path.basename(path))
        if pd.wasCanceled:
            break

    if not pd.wasCanceled:
        if successful:
            QtGui.QMessageBox.information(
                pd, "Done" if (successful == total) else "Done (with errors)",
                "%s modules successfully imported. "
                "You probably need to reload the module database (via the 'Extras' menu) now."
                % ("All %d" % total if (successful == total)
                   else "%d out of %d modules" % (successful, total), ))
            if window and (successful == total):
                window.close()
        else:
            if not total:
                QtGui.QMessageBox.critical(
                    pd, "Import Failed",
                    "%d CLI modules found, but none could be imported.  Check the log for details." % total
                    if total else
                    "No CLI modules found in the given directories.")

def importAndClose():
    doImport(ctx.window())

def init():
    if not ctx.field('importPaths').value:
        found = []
        for pattern in DEFAULT_SEARCH_PATHS:
            found.extend(glob.glob(os.path.expanduser(pattern)))
        ctx.field('importPaths').value = ':'.join(found)
