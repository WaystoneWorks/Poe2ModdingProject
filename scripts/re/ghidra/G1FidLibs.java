// G1 step 2a: statically linked MSVC library code by Ghidra's Function ID databases (the
// vs*_x64.fidbf files shipped with Ghidra). A function whose matches at or above the default
// score threshold all carry one name is renamed to it (mangled names are demangled and applied
// with their namespace); with several candidate names it gets a `fid?:` plate-comment hint
// listing them instead. Existing names are kept. Every match except a user-named function is
// tagged `lib` and `lib:msvc` (the databases do not separate the CRT from the STL).
// Args: <out dir> [apply]. Writes <out dir>/fid_matches.tsv.
//@category PoE2
import ghidra.app.script.GhidraScript;
import ghidra.app.util.demangler.*;
import ghidra.feature.fid.db.*;
import ghidra.feature.fid.service.*;
import ghidra.program.model.listing.*;
import ghidra.program.model.symbol.SourceType;
import java.io.*;
import java.util.*;

public class G1FidLibs extends GhidraScript {
	@Override
	public void run() throws Exception {
		String[] args = getScriptArgs();
		String outDir = args[0];
		boolean apply = args.length > 1 && args[1].equals("apply");
		FidService svc = new FidService();
		float threshold = svc.getDefaultScoreThreshold();
		FidQueryService q = svc.openFidQueryService(currentProgram.getLanguage(), false);
		try { process(svc, q, threshold, outDir, apply); } finally { q.close(); }
	}

	void process(FidService svc, FidQueryService q, float threshold, String outDir, boolean apply) throws Exception {
		List<FidSearchResult> res = svc.processProgram(currentProgram, q, threshold, monitor);
		FunctionTagManager tm = currentProgram.getFunctionManager().getFunctionTagManager();
		int renamed = 0, multi = 0, keptName = 0, demangleFail = 0, considered = 0;
		Map<String, Integer> perLib = new TreeMap<>();
		StringBuilder tsv = new StringBuilder("address\tresult\tname\tlibrary\tscore\tcandidates\n");
		for (FidSearchResult r : res) {
			if (r.matches == null || r.matches.isEmpty()) continue;
			Function f = r.function;
			Set<String> names = new TreeSet<>();
			Set<String> libs = new TreeSet<>();
			float best = 0;
			for (FidMatch m : r.matches) {
				if (m.getOverallScore() < threshold) continue;
				names.add(m.getFunctionRecord().getName());
				LibraryRecord lr = m.getLibraryRecord();
				libs.add(lr.getLibraryFamilyName() + " " + lr.getLibraryVersion() + " " + lr.getLibraryVariant());
				best = Math.max(best, m.getOverallScore());
			}
			if (names.isEmpty()) continue;
			considered++;
			String lib = "msvc"; // the FID databases are all Visual Studio runtime libraries; they do not separate CRT from STL
			boolean isDefault = f.getSymbol().getSource() == SourceType.DEFAULT || f.getName().startsWith("vf_");
			boolean tag = f.getSymbol().getSource() != SourceType.USER_DEFINED;
			String result;
			if (!isDefault) { keptName++; result = "kept"; }
			else if (names.size() == 1) {
				String n = names.iterator().next();
				result = "renamed";
				if (apply && !applyName(f, n)) { demangleFail++; result = "name_failed"; }
				else renamed++;
			} else {
				multi++; result = "multi";
				if (apply) {
					String hint = "fid?: " + String.join(" | ", names.size() > 8 ? new ArrayList<>(names).subList(0, 8) : names) + (names.size() > 8 ? " +" + (names.size() - 8) : "");
					String old = f.getComment();
					f.setComment(old == null ? hint : old + "\n" + hint);
				}
			}
			if (tag && apply) { f.addTag("lib"); f.addTag("lib:" + lib); }
			if (tag) perLib.merge(lib + " " + result, 1, Integer::sum);
			tsv.append(f.getEntryPoint()).append('\t').append(result).append('\t').append(f.getName(true)).append('\t').append(String.join(";", libs))
				.append('\t').append(best).append('\t').append(String.join(" | ", names)).append('\n');
		}
		if (apply && tm.getFunctionTag("lib") != null) tm.getFunctionTag("lib").setComment("Statically linked library code (G1 naming pass); skip in searches");
		new File(outDir).mkdirs();
		try (Writer w = new FileWriter(new File(outDir, "fid_matches.tsv"))) { w.write(tsv.toString()); }
		println((apply ? "APPLIED" : "DRY RUN") + ": threshold=" + threshold + " results=" + res.size() + " with matches>=threshold=" + considered
			+ " renamed(unique name)=" + renamed + " tagged only(several names)=" + multi + " kept existing name=" + keptName + " name failures=" + demangleFail);
		println("per library: " + perLib);
	}


	boolean applyName(Function f, String n) throws Exception {
		if (n.startsWith("?") || n.startsWith("_?")) {
			try {
				List<DemangledObject> ds = DemanglerUtil.demangle(currentProgram, n, f.getEntryPoint());
				if (ds != null && !ds.isEmpty()) {
					DemanglerOptions o = new DemanglerOptions();
					o.setApplySignature(false);
					if (ds.get(0).applyTo(currentProgram, f.getEntryPoint(), o, monitor)) {
						// applyTo adds a label; make it the function's name
						ghidra.program.model.symbol.Symbol p = currentProgram.getSymbolTable().getPrimarySymbol(f.getEntryPoint());
						if (p != null && p.getSource() != SourceType.DEFAULT) return true;
					}
				}
			} catch (Exception e) { /* fall through to the raw name */ }
		}
		try { f.setName(n, SourceType.ANALYSIS); return true; } catch (Exception e) { return false; }
	}
}
