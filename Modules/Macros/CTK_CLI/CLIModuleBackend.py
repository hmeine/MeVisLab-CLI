from cli_modules import CLIModule, popenCLIExecutable
from cli_to_macro import fieldName
from mlab_free_environment import mlabFreeEnvironment
import tempfile, os, sys, shutil

def updateIfAutoApply():
    if ctx.field("autoApply").value:
        update()
    else:
        clear()

def updateIfAutoUpdate():
    if ctx.field("autoUpdate").value:
        tryUpdate()
    else:
        clear()

class ArgumentConverter(object):
    """Takes field values from ctx and formats the arguments for being
    passed to CLI modules; implemented as a context manager for
    cleaning up the temporary files."""

    def __init__(self):
        self._imageFilenames = []
        self.hasOutputParameters = False
        self._tempdir = None
        self._tempfiles = []
    
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if not ctx.field('retainTemporaryFiles').value:
            if self._tempdir is not None:
                shutil.rmtree(self._tempdir)

    def mkstemp(self, suffix):
        if self._tempdir is None:
            self._tempdir = tempfile.mkdtemp() # TODO: prefix = modulename?
        fd, filename = tempfile.mkstemp(suffix = suffix, dir = self._tempdir)
        self._tempfiles.append(filename)
        return fd, filename

    def inputImageFilenames(self):
        for p, fn in self._imageFilenames:
            if p.channel == 'input':
                yield p, fn

    def outputImageFilenames(self):
        for p, fn in self._imageFilenames:
            if p.channel == 'output':
                yield p, fn

    def parameterAvailable(self, parameter):
        field = ctx.field(fieldName(parameter))
        if parameter.typ == 'image' and field.image():
            return True
        return False

    def __call__(self, parameter):
        field = ctx.field(fieldName(parameter))
        if parameter.isExternalType():
            if parameter.channel == 'input' and not self.parameterAvailable(parameter):
                return None
            _, filename = self.mkstemp(parameter.defaultExtension())
            if parameter.typ == 'image':
                self._imageFilenames.append((parameter, filename))
            return filename
        else:
            if parameter.channel == 'output':
                self.hasOutputParameters = True
                if parameter.default is None:
                    return None # nothing to be passed into the CLI module
            if parameter.isNumericVector():
                return ",".join(field.stringValue().split())
            elif parameter.typ == 'boolean':
                if field.value:
                    return True # just set the flag, don't pass an arg
                else:
                    return None # option not set -> no flag must be passed
            elif (parameter.typ == 'file' and not field.value):
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
        return ''
    return s

def tryUpdate():
    """Execute the CLI module, but don't warn about missing inputs (used
    for autoUpdate).  Returns error messages that can be displayed if
    explicitly run (cf. update())."""

    command = [cliModule.path]
    arguments, options, outputs = cliModule.classifyParameters()

    returnParameterFilename = None

    with ArgumentConverter() as arg:
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
            _, returnParameterFilename = arg.mkstemp('.params')
            command.append(returnParameterFilename)

        for p in arguments:
            value = arg(p)
            if value is None:
                clear()
                return "%s: Input image %r is not optional!\n" % (cliModule.name, fieldName(p))
            command.append(value)

        for p, filename in arg.inputImageFilenames():
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

def checkCLI():
    global cliModule
    cliModule = CLIModule(ctx.field('cliExecutablePath').value)
