IMETC Ghidra analysis
====================
Run: ./analyze/scripts/run.ps1
Source: IMETC.ref (nine DLL/EXE files)
Tool: Ghidra 12.1.4 with bundled JDK

modules/<filename> contains pseudocode, disassembly, function/import/export/string
lists, instruction references, errors and architecture metadata.
references.csv includes instruction references to functions and strings.
summary.csv records SHA-256 before analysis and source integrity after analysis.
selection-index.txt contains keyword leads, not confirmed functional attribution.
logs/ contains the full analysis and script logs.
project/ contains reusable Ghidra projects.

Individual decompilations time out after 120 seconds. Decompiled C is pseudocode,
not the original source. Automatic analysis warnings remain in logs.
No target binaries are executed or modified.
