import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.*;
import ghidra.program.model.address.Address;
import ghidra.program.model.data.*;
import ghidra.program.model.listing.Function;
import ghidra.program.model.pcode.HighFunctionDBUtil;
import java.nio.file.*;

/** Precisely scoped call override, justified by native instructions and PDB signature. */
public class RepairKnownCalls extends GhidraScript {
    public void run() throws Exception {
        if (!currentProgram.getName().equalsIgnoreCase("IMTCCORE.DLL")) throw new Exception("Wrong module");
        Function caller=currentProgram.getFunctionManager().getFunctionAt(toAddr(0x18009d500L));
        if(caller==null) throw new Exception("Missing known caller");
        Address call=toAddr(0x18009d537L);
        FunctionDefinitionDataType signature=new FunctionDefinitionDataType("IImeUserDataMgr_GetBigramFactor");
        signature.setReturnType(IntegerDataType.dataType);
        signature.setCallingConvention("__fastcall");
        DataType ptr=new PointerDataType(VoidDataType.dataType,currentProgram.getDataTypeManager());
        DataType fp=new PointerDataType(FloatDataType.dataType,currentProgram.getDataTypeManager());
        signature.setArguments(new ParameterDefinition[] {
            new ParameterDefinitionImpl("self",ptr,null),
            new ParameterDefinitionImpl("previous_word_id",UnsignedIntegerDataType.dataType,null),
            new ParameterDefinitionImpl("next_word_id",UnsignedIntegerDataType.dataType,null),
            new ParameterDefinitionImpl("unigram_fallback",IntegerDataType.dataType,null),
            new ParameterDefinitionImpl("factor_out",fp,null),
            new ParameterDefinitionImpl("lookup_mode",IntegerDataType.dataType,null)
        });
        HighFunctionDBUtil.writeOverride(caller,call,signature);
        Function trigram=currentProgram.getFunctionManager().getFunctionAt(toAddr(0x1800c3500L));
        if(trigram==null)throw new Exception("Missing trigram caller");
        DataType up=new PointerDataType(UnsignedIntegerDataType.dataType,currentProgram.getDataTypeManager());
        FunctionDefinitionDataType pairLookup=new FunctionDefinitionDataType("CCompressedTboLdr_GetBigramIndex");
        pairLookup.setReturnType(IntegerDataType.dataType);pairLookup.setCallingConvention("__fastcall");
        pairLookup.setArguments(new ParameterDefinition[] {
            new ParameterDefinitionImpl("self",ptr,null),
            new ParameterDefinitionImpl("previous_word_id",UnsignedIntegerDataType.dataType,null),
            new ParameterDefinitionImpl("next_word_id",UnsignedIntegerDataType.dataType,null),
            new ParameterDefinitionImpl("pair_index_out",up,null)
        });
        HighFunctionDBUtil.writeOverride(trigram,toAddr(0x1800c3567L),pairLookup);
        FunctionDefinitionDataType valueLookup=new FunctionDefinitionDataType("CCompressedTboLdr_GetTrigramValue");
        valueLookup.setReturnType(IntegerDataType.dataType);valueLookup.setCallingConvention("__fastcall");
        valueLookup.setArguments(new ParameterDefinition[] {
            new ParameterDefinitionImpl("self",ptr,null),
            new ParameterDefinitionImpl("pair_index",UnsignedIntegerDataType.dataType,null),
            new ParameterDefinitionImpl("next_word_id",UnsignedIntegerDataType.dataType,null),
            new ParameterDefinitionImpl("score_out",fp,null)
        });
        HighFunctionDBUtil.writeOverride(trigram,toAddr(0x1800c35aaL),valueLookup);
        Function importer=currentProgram.getFunctionManager().getFunctionAt(toAddr(0x1800678f8L));
        if(importer==null)throw new Exception("Missing learning importer");
        FunctionDefinitionDataType scan=new FunctionDefinitionDataType("swscanf_s_float_callsite");
        scan.setReturnType(IntegerDataType.dataType);scan.setCallingConvention("__fastcall");
        scan.setArguments(new ParameterDefinition[] {
            new ParameterDefinitionImpl("input",ptr,null),
            new ParameterDefinitionImpl("format",ptr,null),
            new ParameterDefinitionImpl("factor_out",fp,null)
        });
        // The native format at 1800d8b58 is L"%f". R8 points at [RSP+0x50],
        // subsequently read by MOVSS at 180067b42 and 180067ba9.
        HighFunctionDBUtil.writeOverride(importer,toAddr(0x180067b0cL),scan);
        DecompInterface decompiler=new DecompInterface();
        decompiler.openProgram(currentProgram);
        try {
            DecompileResults result=decompiler.decompileFunction(caller,120,monitor);
            if(!result.decompileCompleted()) throw new Exception(result.getErrorMessage());
            Path directory=Paths.get(getScriptArgs()[0]);Files.createDirectories(directory);
            Files.writeString(directory.resolve("CImeDicWrap_GetBigramFactor.c"),result.getDecompiledFunction().getC());
            result=decompiler.decompileFunction(trigram,120,monitor);
            if(!result.decompileCompleted())throw new Exception(result.getErrorMessage());
            Files.writeString(directory.resolve("CCompressedTboLdr_GetTrigram.c"),result.getDecompiledFunction().getC());
            result=decompiler.decompileFunction(importer,120,monitor);
            if(!result.decompileCompleted())throw new Exception(result.getErrorMessage());
            Files.writeString(directory.resolve("CStatisLearn_ProcessLearningData.c"),result.getDecompiledFunction().getC());
        } finally {decompiler.dispose();}
    }
}
