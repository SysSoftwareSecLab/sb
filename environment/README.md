# Environment and execution boundary

The portable offline entry point needs Python >=3.10 and its standard library only. No pip installation, credential file, GPU, robot driver, shell wrapper, or network service is required.

Original program generation requested Python 3.11. Historical execution involved a process-isolated instrumented API and finite geometric evidence; those runtime dependencies are not equivalent to the minimal aggregation environment. An exact pinned fresh-execution environment has not yet been validated in this release candidate. No misleading `requirements.txt` containing only the aggregation dependencies is presented as the original execution environment.

`environment/revalidate.py` is the supported entry point. Scripts in `oracles/source-snapshots/` are historical inspection material. Do not execute generated code directly or connect it to hardware.
