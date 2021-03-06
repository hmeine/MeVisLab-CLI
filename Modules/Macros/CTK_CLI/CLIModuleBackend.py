# Copyright (c) Fraunhofer MEVIS, Germany. All rights reserved.
# **InsertLicense** code
from ctk_cli import CLIModule, popenCLIExecutable
from cli_to_macro import fieldName
from mlab_free_environment import mlabFreeEnvironment
import tempfile, os, sys, shutil, time
from mevis import MLAB

# global CLIModule instance
cliModule = None

def checkCLI():
    global cliModule
    cliModule = CLIModule(ctx.field('cliExecutablePath').value)
            
def updateIfAutoApply():
    if ctx.field("autoApply").value:
        update()
    else:
        clear()

def updateIfAutoUpdate(field):
    arg.cleanupTemporaryFile(field.getName())
    if ctx.field("autoUpdate").value:
        tryUpdate()
    else:
        clear()

class ArgumentConverter(object):
    """Takes field values from ctx and formats the arguments for being
    passed to CLI modules; manages list of temporary files in order to
    be able to clean up afterwards.
    """

    def __init__(self):
        self._tempdir = None
        self._imageFilenames = {}
    
    def cleanupTemporaryFiles(self):
        """Completely removes all temporary files."""
        if self._tempdir is not None:
            shutil.rmtree(self._tempdir)
            self._tempdir = None
        self._imageFilenames = {}

    def cleanupTemporaryFile(self, touchedFieldName):
        """Remove a single temporary file for an image which was
        touch()ed and thus cannot be reused.  Does nothing (in
        particular, throws no error) if no entry for that field name
        is found.
        """
        for p, fn in self._imageFilenames.items():
            if fieldName(p) == touchedFieldName:
                if os.path.exists(fn):
                    os.unlink(fn)
                # we need to correctly keep track of _imageFilenames,
                # since inputImageFilenames() and
                # outputImageFilenames() must not return old
                # filenames:
                del self._imageFilenames[p]
                return

    def mkstemp(self, suffix):
        if self._tempdir is None:
            self._tempdir = tempfile.mkdtemp() # TODO: prefix = modulename?
        fd, filename = tempfile.mkstemp(suffix = suffix, dir = self._tempdir)
        return fd, filename

    def inputImageFilenames(self):
        for p, fn in self._imageFilenames.items():
            if p.channel == 'input':
                yield p, fn

    def outputImageFilenames(self):
        for p, fn in self._imageFilenames.items():
            if p.channel == 'output':
                yield p, fn

    def parameterAvailable(self, parameter):
        field = ctx.field(fieldName(parameter))
        if parameter.typ == 'image' and field.image():
            return True
        return False

    def __call__(self, parameter):
        field = ctx.field(fieldName(parameter))
        # TODO: do the following for all outputs that shall be automatically
        # saved and loaded (but not for all external types, i.e. not if the field
        # is a string filename field that is set by the user):
        if parameter.typ == 'image':
            # generate filenames
            if parameter.channel == 'input' and not self.parameterAvailable(parameter):
                return None # (optional) input image not given
            filename = self._imageFilenames.get(parameter)
            if filename is None:
                fd, filename = self.mkstemp(parameter.defaultExtension())
                os.close(fd)
                self._imageFilenames[parameter] = filename
            return filename
        else:
            if parameter.channel == 'output':
                if parameter.default is None:
                    return None # nothing to be passed into the CLI module
            if parameter.isNumericVector():
                return ",".join(field.stringValue().split())
            elif parameter.typ == 'boolean':
                if field.value:
                    return True # just set the flag, don't pass an arg
                else:
                    return None # option not set -> no flag must be passed
            elif parameter.typ == 'file' and not field.value:
                return None # don't pass empty filenames
            else:
                return str(field.value)

def escapeShellArg(s):
    """Bad approximation, preventing stupid mistakes, but also
    unconditional quoting.  (This is only used for *display* of the
    command executed for copy-pasting, so no strict security is
    required.)
    """
    for badChar in ' ;&|"\'':
        if badChar in s:
            return "'%s'" % s.replace("'", "'\"'\"'")
    if not s:
        return "''"
    return s

arg = ArgumentConverter()

def cleanupTemporaryFiles():
    if not ctx.field('retainTemporaryFiles').value:
        arg.cleanupTemporaryFiles()

class CLIExecution(object):
    def __init__(self):
        self.returnParameterFilename = None

        self.stdout = None
        self.stderr = None
        self.stdoutFilename = None
        self.stderrFilename = None
        self.process = None
        self.errorDescription = None

    def compileCommand(self):
        arguments, options, outputs = cliModule.classifyParameters()

        command = [cliModule.path]
        
        for p in options:
            value = arg(p)
            if value is None: # missing optional arg / output arg (without default) / false bool
                continue

            if p.longflag is not None:
                command.append(p.longflag)
            else:
                command.append(p.flag)

            # boolean is special cased, because we need to decide
            # about passing --longflag without arg:
            if value != True:
                command.append(value)

        if outputs:
            command.append('--returnparameterfile')
            fd, self.returnParameterFilename = arg.mkstemp('.params')
            os.close(fd)
            command.append(self.returnParameterFilename)

        for p in arguments:
            value = arg(p)
            if value is None:
                clear()
                return "%s: Input image %r is not optional!\n" % (cliModule.name, fieldName(p))
            command.append(value)
            
        return command

    def saveInputImages(self):
        for p, filename in arg.inputImageFilenames():
            if os.path.exists(filename) and os.path.getsize(filename):
                continue
            ioModule = ctx.module(fieldName(p))
            ioModule.field('unresolvedFileName').value = filename
            ioModule.field('save').touch()

    def start(self):
        command = self.compileCommand()
        ctx.field('debugCommandline').value = ' '.join(map(escapeShellArg, command))
        
        self.saveInputImages()

        self.errorDescription = None
        self.stdout, self.stdoutFilename = arg.mkstemp('.stdout')
        self.stderr, self.stderrFilename = arg.mkstemp('.stderr')
        self.process = popenCLIExecutable(command, stdout = self.stdout, stderr = self.stderr,
                                          env = mlabFreeEnvironment())
        return self.process

    def isRunning(self):
        self.process.poll()
        return self.process.returncode is None
    
    def wait(self):
        if self.isRunning():
            self.process.wait()
        ec = self.process.returncode
        if self.stdout is not None: # wait() may be called again
            self._processTerminated(ec)
        return ec

    def _processTerminated(self, ec):
        os.close(self.stdout)
        os.close(self.stderr)

        with open(self.stdoutFilename) as f:
            ctx.field('debugStdOut').value = f.read()
        with open(self.stderrFilename) as f:
            ctx.field('debugStdErr').value = f.read()

        self.stdout = None
        self.stderr = None

        if ec == 0:
            self.parseResults()
            self.loadOutputImages()
        elif ec > 0:
            clear()
            self.errorDescription = "%s returned exitcode %d!\n" % (cliModule.name, ec)
        else:
            clear()
            self.errorDescription = "%s received SIGNAL %d!\n" % (cliModule.name, -ec)

        return ec
            
    def parseResults(self):
        if self.returnParameterFilename:
            with open(self.returnParameterFilename) as f:
                for line in f:
                    key, value = line.split('=', 1)
                    key = key.strip()
                    value = value.strip()
                    ctx.field(key).value = value

    def loadOutputImages(self):
        for p, filename in arg.outputImageFilenames():
            ioModule = ctx.module(fieldName(p))
            ioModule.field('unresolvedFileName').value = filename

def _pollProcessStatus():
    if execution and execution.isRunning():
        ctx.callLater(0.15, _pollProcessStatus)
    else:
        ec = execution.wait()

            
def tryUpdate():
    """Execute the CLI module, but don't warn about missing inputs (used
    for autoUpdate).  Returns error messages that can be displayed if
    explicitly run (cf. update())."""

    global execution
    execution = CLIExecution()

    execution.start()
    if ctx.field('runInBackground_WIP').value:
        _pollProcessStatus()
    else:
        while execution.isRunning():
            MLAB.processEvents()
            time.sleep(0.1)
        ec = execution.wait()
        if ec:
            return execution.errorDescription

def update():
    """Execute the CLI module"""
    failReason = tryUpdate()
    if failReason:
        sys.stderr.write(failReason)

def clear():
    """Close all itkImageFileReaders such as to make the output image states invalid"""
    for o in ctx.outputs():
        ctx.module(o).field("close").touch()
        arg.cleanupTemporaryFile(o)
