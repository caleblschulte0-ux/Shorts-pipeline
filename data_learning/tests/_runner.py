"""One runner for the data_learning free-function tests.

These modules are plain `test_*` functions invoked by name from
`preview_explainer.yml`, not unittest cases — `unittest discover` collects
nothing from them. That is fine as long as something really runs them, and
the thing that runs them is honest about having found nothing.

Five modules had carried a verbatim copy of the collect-and-run loop, and
every copy printed PASS over an empty list. A module whose tests stop being
discovered — renamed prefix, a decorator that eats the name, a module that
half-imports — then exits 0 with no assertions and the workflow step is
green. `run()` treats an empty collection as a failure, which is the whole
reason this lives in one place.
"""
from __future__ import annotations


def collect(namespace: dict) -> list:
    """Every module-level `test_*` callable, in a stable order."""
    return [v for k, v in sorted(namespace.items())
            if k.startswith("test_") and callable(v)]


def run(namespace: dict, label: str = "") -> int:
    """Run a module's tests. Returns a process exit code.

    Zero collected tests is a FAILURE, not a pass — see the module docstring.
    """
    fns = collect(namespace)
    if not fns:
        print("FAIL — collected 0 tests; a suite that runs nothing is not a "
              "suite that passes")
        return 1
    failed = 0
    for fn in fns:
        try:
            fn()
            print(f"  ok   {fn.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"  FAIL {fn.__name__}: {e}")
        except Exception as e:  # noqa: BLE001
            # A TypeError halfway down used to abort the module, so every
            # test after it went unreported. Report and keep going.
            failed += 1
            print(f"  ERROR {fn.__name__}: {type(e).__name__}: {e}")
    if failed:
        print(f"{failed} FAILED")
        return 1
    print(f"PASS — {len(fns)} checks" + (f" ({label})" if label else ""))
    return 0
