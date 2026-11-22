import ghidra.app.script.GhidraScript;
import ghidra.app.plugin.core.analysis.PdbUniversalAnalyzer;
import ghidra.app.util.bin.format.pdb2.pdbreader.PdbReaderOptions;
import ghidra.app.util.pdb.pdbapplicator.PdbApplicatorOptions;
import ghidra.app.util.importer.MessageLog;
import java.io.File;

public class ApplySymbols extends GhidraScript {
    public void run() throws Exception {
        PdbUniversalAnalyzer.setPdbFileOption(currentProgram, new File(getScriptArgs()[0]));
        analyzeAll(currentProgram);
    }
}
