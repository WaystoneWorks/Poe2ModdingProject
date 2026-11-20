// G1 step 4: imports the names the docs and the DLL give (scripts/re/known_names.py) so the docs
// and Ghidra agree. Per name: the addresses it is written on are resolved against Ghidra's
// functions; sites inside the function whose entry carries the same name are the same function.
// A name is applied when it ends on one target (a function entry, or one address outside any
// function, which gets a label) and that target gets no other name. Doc versus DLL: the doc name
// is applied and the DLL label goes into a `dll label:` plate-comment line. Not applied, reported:
// several doc names for one target, a name written on different functions, a DLL name only on an
// address inside a function (a doc name there becomes a label at that site), and an existing non-default Ghidra name that differs (vf_ names
// from step 1 are replaced, keeping their class namespace; FID-applied names are not replaced).
// Args: <known_names.tsv> <out dir> [apply]. Writes <out dir>/known_names_result.tsv.
//@category PoE2
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.*;
import ghidra.program.model.symbol.*;
import java.io.*;
import java.util.*;

public class G1ImportNames extends GhidraScript {
	@Override
	public void run() throws Exception {
		String[] args = getScriptArgs();
		boolean apply = args.length > 2 && args[2].equals("apply");
		FunctionManager fm = currentProgram.getFunctionManager();
		SymbolTable st = currentProgram.getSymbolTable();
		Map<String, Map<Address, String>> byName = new TreeMap<>(); // name -> address -> sources
		try (BufferedReader r = new BufferedReader(new FileReader(args[0]))) {
			String line;
			while ((line = r.readLine()) != null) {
				String[] c = line.split("\t");
				if (c.length < 3) continue;
				byName.computeIfAbsent(c[1], k -> new LinkedHashMap<>()).put(toAddr(Long.parseUnsignedLong(c[0], 16)), c[2]);
			}
		}
		StringBuilder out = new StringBuilder("result\ttarget\tname\tdetail\n");
		Map<String, Integer> counts = new TreeMap<>();
		// 1. each name to one target
		Map<Address, Map<String, String>> byTarget = new TreeMap<>(); // target -> name -> sources
		for (Map.Entry<String, Map<Address, String>> e : byName.entrySet()) {
			Set<Address> entries = new TreeSet<>(), loose = new TreeSet<>(), sites = new TreeSet<>();
			String srcs = String.join(",", new TreeSet<>(e.getValue().values()));
			for (Address a : e.getValue().keySet()) {
				Function f = fm.getFunctionAt(a);
				if (f != null) { entries.add(a); continue; }
				Function c = fm.getFunctionContaining(a);
				if (c != null) sites.add(a); else loose.add(a);
			}
			Address target = null;
			String why = null;
			if (entries.size() == 1 && loose.isEmpty()) {
				target = entries.iterator().next();
				Function f = fm.getFunctionAt(target);
				for (Address s : sites) if (!f.getBody().contains(s)) { why = "also written on " + s + " in " + fm.getFunctionContaining(s).getName(true); target = null; break; }
			} else if (entries.isEmpty() && loose.size() == 1 && sites.isEmpty()) {
				target = loose.iterator().next();
			} else if (entries.size() > 1 || entries.size() + loose.size() > 1) {
				why = "written on several targets " + entries + loose;
			} else if (entries.isEmpty() && loose.isEmpty() && sites.size() == 1 && !srcs.equals("dll")) {
				target = sites.iterator().next(); // a doc-named site inside a function: a label there, the function keeps its name
			} else {
				Address s = sites.iterator().next();
				why = "only on " + sites + " inside " + fm.getFunctionContaining(s).getName(true) + " (entry " + fm.getFunctionContaining(s).getEntryPoint() + ")";
			}
			if (target == null) {
				counts.merge("conflict: name not resolved", 1, Integer::sum);
				out.append("conflict\t\t").append(e.getKey()).append('\t').append(why).append(" [").append(srcs).append("]\n");
				continue;
			}
			byTarget.computeIfAbsent(target, k -> new TreeMap<>()).put(e.getKey(), srcs);
		}
		// 2. each target to one name, then against Ghidra
		for (Map.Entry<Address, Map<String, String>> e : byTarget.entrySet()) {
			Address t = e.getKey();
			Map<String, String> names = e.getValue();
			List<String> doc = new ArrayList<>(), dll = new ArrayList<>();
			for (Map.Entry<String, String> n : names.entrySet()) (n.getValue().equals("dll") ? dll : doc).add(n.getKey());
			String name, note = null;
			if (doc.size() > 1 || (doc.isEmpty() && dll.size() > 1)) {
				counts.merge("conflict: several names for one address", 1, Integer::sum);
				out.append("conflict\t").append(t).append('\t').append(String.join(" | ", names.keySet())).append("\tseveral names ").append(names).append('\n');
				continue;
			}
			name = doc.isEmpty() ? dll.get(0) : doc.get(0);
			if (!doc.isEmpty() && !dll.isEmpty()) {
				note = "dll label: " + dll.get(0);
				counts.merge("doc vs dll (doc applied, dll label in comment)", 1, Integer::sum);
				out.append("doc_vs_dll\t").append(t).append('\t').append(name).append("\tdll ").append(dll.get(0)).append('\n');
			}
			String src = names.get(name);
			Function f = fm.getFunctionAt(t);
			Symbol cur = f != null ? f.getSymbol() : st.getPrimarySymbol(t);
			String curName = cur == null ? null : cur.getName();
			boolean replaceable = cur == null || cur.getSource() == SourceType.DEFAULT || (cur.getSource() == SourceType.ANALYSIS && curName.startsWith("vf_"));
			String simple = name.contains("::") ? name.substring(name.lastIndexOf("::") + 2) : name;
			if (cur != null && (curName.equals(name) || curName.equals(simple) || cur.getName(true).equals(name))) {
				counts.merge("already named so", 1, Integer::sum);
				out.append("same\t").append(t).append('\t').append(name).append('\t').append(src).append('\n');
			} else if (!replaceable) {
				counts.merge("conflict: Ghidra has another name", 1, Integer::sum);
				out.append("conflict\t").append(t).append('\t').append(name).append("\tGhidra: ").append(cur.getName(true)).append(" (").append(cur.getSource()).append(") [").append(src).append("]\n");
				continue;
			} else {
				if (apply) {
					Namespace ns = cur != null && !name.contains("::") ? cur.getParentNamespace() : currentProgram.getGlobalNamespace();
					String n = name;
					if (name.contains("::")) {
						ns = currentProgram.getGlobalNamespace();
						String[] parts = name.split("::");
						for (int i = 0; i < parts.length - 1; i++) {
							Namespace x = st.getNamespace(parts[i], ns);
							ns = x != null ? x : st.createNameSpace(ns, parts[i], SourceType.USER_DEFINED);
						}
						n = parts[parts.length - 1];
					}
					if (f != null) { f.setParentNamespace(ns); f.setName(n, SourceType.USER_DEFINED); }
					else { Symbol s = st.createLabel(t, n, ns, SourceType.USER_DEFINED); s.setPrimary(); }
				}
				String kind = f != null ? (curName.startsWith("vf_") ? "renamed (was " + cur.getName(true) + ")" : "renamed") : "label";
				counts.merge(f != null ? (curName.startsWith("vf_") ? "function renamed from vf_" : "function renamed") : "label created", 1, Integer::sum);
				out.append(kind.startsWith("renamed") ? "renamed" : "label").append('\t').append(t).append('\t').append(name).append('\t').append(kind).append(" [").append(src).append("]\n");
			}
			if (note != null && apply && f != null) {
				String old = f.getComment();
				if (old == null || !old.contains(note)) f.setComment(old == null ? note : old + "\n" + note);
			}
		}
		new File(args[1]).mkdirs();
		try (Writer w = new FileWriter(new File(args[1], "known_names_result.tsv"))) { w.write(out.toString()); }
		println((apply ? "APPLIED" : "DRY RUN") + ": names=" + byName.size() + " " + counts);
	}
}
