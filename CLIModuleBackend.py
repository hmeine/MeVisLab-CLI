def updateIfAutoApply():
    if ctx.field("autoApply").value:
        update()

def updateIfAutoUpdate():
    if ctx.field("autoUpdate").value:
        update()

def update():
    print "<fill in CLI module execution here>"

