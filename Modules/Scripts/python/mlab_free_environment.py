import os
from mevis import MLABPackageManager
    
def _removePaths(pathString, pathsToBeRemoved):
    paths = pathString.split(os.pathsep)
    for p in pathsToBeRemoved:
        if p in paths:
            paths.remove(p)
    return os.pathsep.join(paths)

_cached = None

def clearMLABFreeEnvironmentCache():
    global _cached
    _cached = None

def mlabFreeEnvironment():
    """Try to undo changes performed by MeVisLab on the process
    environment.  Cleaned version of os.environ is returned as a copy
    that can be used for child processes (e.g. passed as 'env' argument
    to subprocess.call).

    The result is cached; should os.environ indeed change between
    calls, you may call clearMLABFreeEnvironmentCache() to clear the
    cache."""
    
    global _cached
    if _cached is None:
        _cached = dict(os.environ)
        for libPathVar in ('LD_LIBRARY_PATH',
                           'DYLD_LIBRARY_PATH',
                           'DYLD_FRAMEWORK_PATH'):
            if libPathVar in _cached:
                _cached[libPathVar] = _removePaths(_cached[libPathVar],
                                                   MLABPackageManager.getLibPaths())
        if 'PATH' in _cached:
            _cached['PATH'] = _removePaths(_cached['PATH'],
                                           MLABPackageManager.getBinPaths())
        
    return _cached
