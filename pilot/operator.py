#!/usr/bin/env python3
"""Operator launcher: `python3 -I operator.py run|check|status|selftest` (the code is in pm_operator.py).

Why this file is so small: its name is the same as the standard-library module `operator`. When a program in
this folder (smoke.py, exp_bids.py, conn_check.py) is started without `-I`, the folder comes first on the
module search path, and the standard library's own `import operator` (collections, functools, ...) would find
this file instead. In that case this file loads the real standard-library module and does nothing else, so
those programs keep working. Only when it is run as a script does it start the operator.
"""
import sys as _sys

if __name__ != "__main__":
    # imported as `operator`: be exactly the standard-library module (pure Python source, then its C part)
    _dirs = [getattr(_sys, "_stdlib_dir", None)]
    for _name in ("os", "codecs", "abc", "io"):
        _f = getattr(_sys.modules.get(_name), "__file__", None)
        if _f:
            _dirs.append(_f.rsplit("/", 1)[0])
    _done = False
    for _d in _dirs:
        if not _d:
            continue
        try:
            with open(_d + "/operator.py", encoding="utf-8") as _fh:
                _src = _fh.read()
        except OSError:
            continue
        exec(compile(_src, _d + "/operator.py", "exec"), globals())
        _done = True
        break
    if not _done:
        from _operator import *  # noqa: F401,F403  (the C module holds every public function)
else:
    _sys.dont_write_bytecode = True          # leave no __pycache__ in the working copy
    from pathlib import Path

    _sys.path.insert(0, str(Path(__file__).resolve().parent))
    import pm_operator

    _sys.exit(pm_operator.main())
