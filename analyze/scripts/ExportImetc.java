import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.*;
import ghidra.program.model.listing.*;
import ghidra.program.model.symbol.*;
import ghidra.program.model.address.*;
import java.io.*;
import java.nio.file.*;

public class ExportImetc extends GhidraScript {
    String q(Object s) { return "\"" + String.valueOf(s).replace("\"", "\"\"") + "\""; }
    PrintWriter out(Path dir, String name) throws Exception { return new PrintWriter(Files.newBufferedWriter(dir.resolve(name))); }
    public void run() throws Exception {
        Path dir = Paths.get(getScriptArgs()[0], currentProgram.getName());
        Files.createDirectories(dir);
        DecompInterface dec = new DecompInterface();
        dec.openProgram(currentProgram);
        try (PrintWriter c=out(dir,"decompiled.c"); PrintWriter asm=out(dir,"disassembly.txt");
             PrintWriter fun=out(dir,"functions.csv"); PrintWriter imp=out(dir,"imports.csv");
             PrintWriter exp=out(dir,"exports.csv"); PrintWriter str=out(dir,"strings.csv");
             PrintWriter ref=out(dir,"references.csv"); PrintWriter err=out(dir,"errors.txt")) {
            fun.println("address,name,size,status"); imp.println("address,name"); exp.println("address,name");
            str.println("address,value"); ref.println("from,to,type");
            for (Function f: currentProgram.getFunctionManager().getFunctions(true)) {
                monitor.checkCancelled();
                String status="ok";
                try {
                    DecompileResults r=dec.decompileFunction(f,120,monitor);
                    if(r.decompileCompleted() && r.getDecompiledFunction()!=null) {
                        c.println("\n/* " + f.getEntryPoint()+" "+f.getName()+" */");
                        c.println(r.getDecompiledFunction().getC());
                    } else { status="failed"; err.println(f.getEntryPoint()+" "+r.getErrorMessage()); }
                } catch(Exception e) { status="exception"; err.println(f.getEntryPoint()+" "+e); }
                fun.println(q(f.getEntryPoint())+","+q(f.getName(true))+","+f.getBody().getNumAddresses()+","+q(status));
            }
            for(Instruction i: currentProgram.getListing().getInstructions(true)) {
                monitor.checkCancelled(); asm.println(i.getAddress()+"  "+i);
                for(Reference r:i.getReferencesFrom()) ref.println(q(r.getFromAddress())+","+q(r.getToAddress())+","+q(r.getReferenceType()));
            }
            for(Data d:currentProgram.getListing().getDefinedData(true)) {
                if(d.hasStringValue()) str.println(q(d.getAddress())+","+q(d.getValue()));
            }
            SymbolIterator symbols=currentProgram.getSymbolTable().getAllSymbols(true);
            while(symbols.hasNext()) { Symbol s=symbols.next();
                if(s.isExternal()) imp.println(q(s.getAddress())+","+q(s.getName(true)));
                if(s.isExternalEntryPoint()) exp.println(q(s.getAddress())+","+q(s.getName(true)));
            }
        } finally { dec.dispose(); }
        try(PrintWriter meta=out(dir,"metadata.txt")) {
            meta.println("language="+currentProgram.getLanguageID());
            meta.println("compiler="+currentProgram.getCompilerSpec().getCompilerSpecID());
            meta.println("ghidra="+getGhidraVersion());
        }
        try(PrintWriter symbols=out(dir,"symbols.csv"); PrintWriter allrefs=out(dir,"all-references.csv")) {
            symbols.println("address,name,type");
            SymbolIterator all=currentProgram.getSymbolTable().getAllSymbols(true);
            while(all.hasNext()) { Symbol s=all.next(); symbols.println(q(s.getAddress())+","+q(s.getName(true))+","+q(s.getSymbolType())); }
            allrefs.println("from,to,type,owner");
            AddressIterator sources=currentProgram.getReferenceManager().getReferenceSourceIterator(currentProgram.getMinAddress(),true);
            while(sources.hasNext()) {
                Address source=sources.next(); Function owner=currentProgram.getFunctionManager().getFunctionContaining(source);
                for(Reference r:currentProgram.getReferenceManager().getReferencesFrom(source)) {
                    allrefs.println(q(source)+","+q(r.getToAddress())+","+q(r.getReferenceType())+","+q(owner==null?"":owner.getName(true)));
                }
            }
        }
    }
}
