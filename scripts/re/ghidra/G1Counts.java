// G1: prints the function count, how many still have a default FUN_ name, the name sources and
// the function count per tag. Args: [label] (printed with the line, e.g. "after step 1").
//@category PoE2
import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.*;
import ghidra.program.model.symbol.SourceType;
import java.util.*;

public class G1Counts extends GhidraScript {
	@Override
	public void run() throws Exception {
		String label = getScriptArgs().length > 0 ? String.join(" ", getScriptArgs()) : "";
		int total = 0, fun = 0, user = 0, imp = 0, anal = 0, plate = 0;
		Map<String, Integer> tags = new TreeMap<>();
		for (Function f : currentProgram.getFunctionManager().getFunctions(true)) {
			total++;
			if (f.getName().startsWith("FUN_")) fun++;
			SourceType s = f.getSymbol().getSource();
			if (s == SourceType.USER_DEFINED) user++; else if (s == SourceType.IMPORTED) imp++; else if (s == SourceType.ANALYSIS) anal++;
			if (f.getComment() != null) plate++;
			for (FunctionTag t : f.getTags()) tags.merge(t.getName(), 1, Integer::sum);
		}
		println("COUNTS " + label + ": functions=" + total + " FUN_=" + fun + " named=" + (total - fun)
			+ " (user=" + user + " imported=" + imp + " analysis=" + anal + ") plate_comments=" + plate + " tags=" + tags);
	}
}
