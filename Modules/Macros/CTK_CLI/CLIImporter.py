# **InsertLicense** code
import os, re, glob, logging, cli_to_macro
from PythonQt import Qt, QtGui
from mevis import MLABFileDialog

from mlab_free_environment import mlabFreeEnvironment

logging.basicConfig() # no-op if there is already a configuration

DEFAULT_SEARCH_PATHS = (
    "/Applications/Slicer*.app/Contents/lib/Slicer-*/cli-modules",
    "/Applications/Slicer*.app/Contents/Extensions-*/*/lib/Slicer-*/cli-modules",
    "~/Slicer*/lib/Slicer-*/cli-modules",
    "~/.config/NA-MIC/Extensions-*/*/lib/Slicer-*/cli-modules",
    r"C:\Program*\Slicer*\lib\Slicer-*\cli-modules",
    r"C:\Program*\Slicer*\Extensions-*\*\lib\Slicer-*\cli-modules",
    )

PATH_SEP = '\n'
    
def _importPathsAsList():
    return ctx.field('importPaths').value.split(PATH_SEP)

def doImport(field = None, window = None):
    importPaths = [ctx.expandFilename(os.path.expanduser(path))
                   for path in _importPathsAsList()]
    
    targetDirectory = ctx.expandFilename(os.path.expanduser(
            ctx.field('targetDirectory').value))
    if not os.path.exists(targetDirectory):
        os.mkdir(targetDirectory)
    if not os.path.exists(os.path.join(targetDirectory, "mhelp")):
        os.mkdir(os.path.join(targetDirectory, "mhelp"))

    generateScreenshots = ctx.field('generatePanelScreenshots').value
        
    pd = QtGui.QProgressDialog(window.widget() if window else None)
    pd.setWindowModality(Qt.Qt.WindowModal)
     
    for index, successful, total, path in cli_to_macro.importAllCLIs(
            importPaths, targetDirectory,
            includePanelScreenshots = generateScreenshots,
            env = mlabFreeEnvironment()):
        if path:
            print "%d/%d importing %s..." % (index+1, total, path)
        pd.setValue(index)
        pd.setMaximum(total)
        if path:
            pd.setLabelText(os.path.basename(path))
        if pd.wasCanceled:
            break

    if not pd.wasCanceled:
        if successful:
            if generateScreenshots:
                pd.setLabelText("Generating screenshots...")
                ctx.field('MLABModuleHelp2Html.directory').value = targetDirectory
                ctx.field('MLABModuleHelp2Html.createScreenshots').touch()

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
    doImport(window = ctx.window())

def init():
    if not ctx.field('importPaths').value:
        found = []
        for pattern in DEFAULT_SEARCH_PATHS:
            found.extend(glob.glob(os.path.expanduser(pattern)))
        ctx.field('importPaths').value = PATH_SEP.join(found)

def browseForDirectory():
    dirName = MLABFileDialog.getExistingDirectory(
        ctx.localPath(), "Select CLI Modules Directory")
    if dirName:
        importPaths = _importPathsAsList()
        importPaths.append(ctx.unexpandFilename(dirName))
        ctx.field('importPaths').value = PATH_SEP.join(importPaths)

def _selectedPaths():
    c = ctx.control('pathList')
    importPaths = _importPathsAsList()
    return [index for index in range(len(importPaths))
            if c.isItemSelected(index)]
    
        
def removeSelectedDirectory():
    selected = _selectedPaths()
    if selected:
        importPaths = _importPathsAsList()
        for index in selected[::-1]:
            del importPaths[index]
        ctx.field('importPaths').value = PATH_SEP.join(importPaths)

def pathSelectionChanged():
    ctx.control('removeButton').setEnabled(bool(_selectedPaths()))
