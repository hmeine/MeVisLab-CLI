# **InsertLicense** code
from ctk_cli import CLIModule, popenCLIExecutable
from cli_to_macro import fieldName
from mlab_free_environment import mlabFreeEnvironment
import tempfile, os, sys, shutil

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
        for p, fn in self._imageFilenames.iteritems():
            if p.channel == 'input':
                yield p, fn

    def outputImageFilenames(self):
        for p, fn in self._imageFilenames.iteritems():
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
        
def tryUpdate():
    """Execute the CLI module, but don't warn about missing inputs (used
    for autoUpdate).  Returns error messages that can be displayed if
    explicitly run (cf. update())."""

    command = [cliModule.path]
    arguments, options, outputs = cliModule.classifyParameters()

    returnParameterFilename = None

    if True:
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
            fd, returnParameterFilename = arg.mkstemp('.params')
            os.close(fd)
            command.append(returnParameterFilename)

        for p in arguments:
            value = arg(p)
            if value is None:
                clear()
                return "%s: Input image %r is not optional!\n" % (cliModule.name, fieldName(p))
            command.append(value)

        for p, filename in arg.inputImageFilenames():
            if os.path.exists(filename) and os.path.getsize(filename):
                continue
            ioModule = ctx.module(fieldName(p))
            ioModule.field('unresolvedFileName').value = filename
            ioModule.field('save').touch()

        ctx.field('debugCommandline').value = ' '.join(map(escapeShellArg, command))

        stdout, stdoutFilename = arg.mkstemp('.stdout')
        stderr, stderrFilename = arg.mkstemp('.stderr')
        p = popenCLIExecutable(command, stdout = stdout, stderr = stderr,
                               env = mlabFreeEnvironment())
        ec = p.wait()
        os.close(stdout)
        os.close(stderr)

        with file(stdoutFilename) as f:
            ctx.field('debugStdOut').value = f.read()
        with file(stderrFilename) as f:
            ctx.field('debugStdErr').value = f.read()

        if ec == 0:
            if returnParameterFilename:
                with file(returnParameterFilename) as f:
                    for line in f:
                        key, value = line.split('=', 1)
                        key = key.strip()
                        value = value.strip()
                        ctx.field(key).value = value
            for p, filename in arg.outputImageFilenames():
                ioModule = ctx.module(fieldName(p))
                ioModule.field('unresolvedFileName').value = filename
        elif ec > 0:
            clear()
            return "%s returned exitcode %d!\n" % (cliModule.name, ec)
        else:
            clear()
            return "%s received SIGNAL %d!\n" % (cliModule.name, -ec)

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

def checkCLI():
    global cliModule
    cliModule = CLIModule(ctx.field('cliExecutablePath').value)
