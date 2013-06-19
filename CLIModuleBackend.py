from cli_modules import CLIModule

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

def update():
    """Execute the CLI module"""
    print "<fill in CLI module execution here>"

def clear():
    """Close all itkImageFileReaders such as to make the output image states invalid"""
    for o in ctx.outputs():
        ctx.module(o).field("close").touch()

def load(path):
    global cliModule
    cliModule = CLIModule(path)
