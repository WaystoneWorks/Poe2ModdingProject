// Writes every function with a non-default name as {"results":[{"address","name"}...]} to the
// file given as the argument, the input of scripts/re/export_symbols.py
// (dumps/<version>/ghidra/ghidra_named_functions_p1.json). Same content as the MCP's
// search_functions_enhanced(has_custom_name=true), without passing it through the MCP.
//@category PoE2
import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.*;
import ghidra.program.model.symbol.SourceType;
import java.io.*;

public class ExportNamedFunctions extends GhidraScript {
	@Override
	public void run() throws Exception {
		String out = getScriptArgs()[0];
		StringBuilder b = new StringBuilder("{\"results\":[");
		int n = 0;
		for (Function f : currentProgram.getFunctionManager().getFunctions(true)) {
			if (f.getSymbol().getSource() == SourceType.DEFAULT) continue;
			String name = f.getName(true).replace("\\", "\\\\").replace("\"", "\\\"");
			if (n++ > 0) b.append(',');
			b.append("{\"address\":\"").append(f.getEntryPoint().toString()).append("\",\"name\":\"").append(name).append("\"}");
		}
		b.append("]}");
		try (Writer w = new FileWriter(out)) { w.write(b.toString()); }
		println("wrote " + n + " named functions to " + out);
	}
}
