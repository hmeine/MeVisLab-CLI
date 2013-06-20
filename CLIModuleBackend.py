from cli_modules import CLIModule
import subprocess, tempfile, os, sys

def updateIfAutoApply():
    if ctx.field("autoApply").value:
        update()
    else:
        clear()

def updateIfAutoUpdate():
    if ctx.field("autoUpdate").value:
        update()
    else:
        clear()

class ArgumentConverter(object):
    """Takes field values from ctx and formats the arguments for being
    passed to CLI modules; implemented as a context manager for
    cleaning up the temporary files."""

    def __init__(self):
        self.tempfiles = []
        self._imageFilenames = []
    
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if not ctx.field('retainTemporaryFiles').value:
            for filename in self.tempfiles:
                os.unlink(filename)

    def mkstemp(self, suffix):
        _, filename = tempfile.mkstemp(suffix = suffix)
        self.tempfiles.append(filename)
        return filename

    def inputImageFilenames(self):
        for p, fn in self._imageFilenames:
            if p.channel == 'input':
                yield p, fn

    def outputImageFilenames(self):
        for p, fn in self._imageFilenames:
            if p.channel == 'output':
                yield p, fn

    def __call__(self, parameter):
        field = ctx.field(parameter.identifier())
        if parameter.typ == 'image':
            if parameter.channel == 'input' and not field.image():
                return None
            filename = self.mkstemp('.nrrd') # TODO: look at fileExtensions
            self._imageFilenames.append((parameter, filename))
            return filename
        elif parameter.isNumericVector():
            return ",".join(field.value.split())
        else:
            return str(field.value)

def escapeShellArg(s):
    """Bad approximation, preventing stupid mistakes, but also unconditional quoting."""
    for badChar in ' ;&|':
        if badChar in s:
            return "'%s'" % s
    return s

def update():
    """Execute the CLI module"""
    command = [cliModule.path]
    arguments, options = cliModule.argumentsAndOptions()

    with ArgumentConverter() as arg:
        for p in options:
            value = arg(p)
            if value is None:
                continue
            if p.longflag is not None:
                command.append(p.longflag)
            else:
                command.append(p.flag)
            command.append(value)

        for p in arguments:
            value = arg(p)
            if value is None:
                sys.stderr.write("%s: Input image %r is not optional!\n" % (
                    cliModule.name, p.identifier()))
                clear()
                return
            command.append(value)

        for p, filename in arg.inputImageFilenames():
            ioModule = ctx.module(p.identifier())
            ioModule.field('unresolvedFileName').value = filename
            ioModule.field('save').touch()

        ctx.field('commandline').value = ' '.join(map(escapeShellArg, command))
        
        ec = subprocess.call(command)
        if ec == 0:
            for p, filename in arg.outputImageFilenames():
                ioModule = ctx.module(p.identifier())
                ioModule.field('unresolvedFileName').value = filename
        elif ec > 0:
            sys.stderr.write("%r returned exitcode %d!\n" % (cliModule.name, ec))
            clear()
        else:
            sys.stderr.write("%r received SIGNAL %d!\n" % (cliModule.name, -ec))
            clear()

def clear():
    """Close all itkImageFileReaders such as to make the output image states invalid"""
    for o in ctx.outputs():
        ctx.module(o).field("close").touch()

def load(path):
    global cliModule
    cliModule = CLIModule(path)
