from cli_modules import CLIModule
import subprocess, tempfile, os

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
    def __init__(self):
        self.tempfiles = []
    
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        for filename in self.tempfiles:
            os.unlink(filename)

    def mkstemp(self, suffix):
        _, filename = tempfile.mkstemp(suffix = suffix)
        self.tempfiles.append(filename)
        return filename

    def __call__(self, parameter):
        field = ctx.field(parameter.identifier())
        if parameter.typ == 'image':
            ioModule = ctx.module(parameter.identifier())
            filename = self.mkstemp('.nrrd') # TODO: look at fileExtensions
            ioModule.field('unresolvedFileName').value = filename
            return filename
        elif parameter.typ.endswith('-vector') and parameter.typ != 'string-vector':
            return ",".join(field.value.split())
        else:
            return str(field.value)

def update():
    """Execute the CLI module"""
    command = [cliModule.path]
    arguments, options = cliModule.argumentsAndOptions()

    with ArgumentConverter() as arg:
        for p in options:
            if p.longflag is not None:
                command.append(p.longflag)
            else:
                command.append(p.flag)
            command.append(arg(p))

        for p in arguments:
            command.append(arg(p))

        for p in cliModule.parameters():
            if p.typ == 'image' and p.channel == 'input':
                ctx.module(p.identifier()).field('save').touch()

        print command
        print subprocess.call(command)

        for p in cliModule.parameters():
            if p.typ == 'image' and p.channel == 'output':
                ctx.module(p.identifier()).field('open').touch()

def clear():
    """Close all itkImageFileReaders such as to make the output image states invalid"""
    for o in ctx.outputs():
        ctx.module(o).field("close").touch()

def load(path):
    global cliModule
    cliModule = CLIModule(path)
