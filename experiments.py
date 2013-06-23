import logging, sys, glob
#logging.basicConfig(format='  %(asctime)s %(message)s')
#logging.basicConfig(filename = 'warnings.txt', level = 0)
logging.basicConfig(stream = sys.stdout, level = 0) # easy grep'ping

import cli_to_macro

args = sys.argv[1:] or ['/Applications/Slicer.app/Contents/lib/Slicer-4.2/cli-modules']

for index, total, path in cli_to_macro.importAllCLIs(args, 'mdl'):
        print "%d/%d importing %s..." % (index, total, path)
