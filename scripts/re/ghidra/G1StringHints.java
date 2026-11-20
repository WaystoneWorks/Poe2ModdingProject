// G1 step 3: string hints. A debug, error or log message (or a __FILE__ source path) whose text
// is referenced from exactly one function is a strong hint at what that function does. Such a
// function gets a plate-comment line `str: <text>` per string (at most 3, errors and `::` names
// first) and the tag `str`. It is a hint only: nothing is renamed. Functions tagged `lib` are
// skipped. Existing plate comments are kept (the hints are appended once; a rerun replaces them).
// Messages: at least 10 characters, two words or a `::`, a format specifier or a source path;
// no asset paths, no data blobs.
// Args: <strings.tsv from scripts/re/strings_va.py> <out dir> [apply]. Writes <out dir>/string_hints.tsv.
//@category PoE2
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.*;
import ghidra.program.model.symbol.*;
import java.io.*;
import java.util.*;
import java.util.regex.*;

public class G1StringHints extends GhidraScript {
	static final Pattern SRC = Pattern.compile("[\\\\/][A-Za-z0-9_.+-]+\\.(cpp|cc|c|h|hpp|inl)$");
	static final Pattern FMT = Pattern.compile("%[-+ 0#]*[0-9.]*(l{0,2}|z|I64)[sdiuxXfgcp]|\\{[0-9:a-z]*\\}");
	static final Pattern ASSET = Pattern.compile("^[A-Za-z0-9_ ./-]+\\.(dat|datc64|ot|otc|ao|aoc|tgr|tgt|tdt|dds|png|hlsl|fx|ffx|mat|sm|smd|fmt|amd|ast|act|epk|pet|trl|rs|arm|et|json|txt|bank|ogg|bk2|ttf|csd|gft|gt|env|tsi|ecf|atlas|clt|fxgraph|tmo|tst|tmd)$", Pattern.CASE_INSENSITIVE);
	static final Pattern PRIO = Pattern.compile("(?i)error|fail|invalid|warn|assert|unable|cannot|can't|corrupt|missing|unexpected|::");

	static boolean isMessage(String s) {
		if (s.length() < 10 || s.length() > 400) return false;
		if (ASSET.matcher(s).find()) return false;
		if (SRC.matcher(s).find()) return true;
		int letters = 0, odd = 0;
		for (char c : s.toCharArray()) { if (Character.isLetter(c)) letters++; else if ("{}<>[]|^~`\\".indexOf(c) >= 0) odd++; }
		if (letters < s.length() * 0.6 || odd > 4) return false;
		if (s.contains("::") || FMT.matcher(s).find()) return true;
		String[] w = s.trim().split("\\s+");
		if (w.length < 2) return false;
		// prose, not a run of glued dictionary words: some word must be short enough to be a real word
		int real = 0;
		for (String x : w) if (x.length() >= 2 && x.length() <= 15) real++;
		return real >= 2;
	}

	@Override
	public void run() throws Exception {
		String[] args = getScriptArgs();
		boolean apply = args.length > 2 && args[2].equals("apply");
		FunctionManager fm = currentProgram.getFunctionManager();
		ReferenceManager rm = currentProgram.getReferenceManager();
		Map<String, Set<Function>> users = new HashMap<>();
		int messages = 0;
		try (BufferedReader r = new BufferedReader(new InputStreamReader(new FileInputStream(args[0]), "UTF-8"))) {
			String line;
			while ((line = r.readLine()) != null) {
				String[] c = line.split("\t", 3);
				if (c.length < 3 || !isMessage(c[2])) continue;
				messages++;
				Address a = toAddr(Long.parseUnsignedLong(c[0], 16));
				Set<Function> fs = users.computeIfAbsent(c[2], k -> new HashSet<>());
				for (Reference ref : rm.getReferencesTo(a)) {
					Function f = fm.getFunctionContaining(ref.getFromAddress());
					if (f != null) fs.add(f);
				}
			}
		}
		Map<Function, List<String>> hints = new HashMap<>();
		int unique = 0, shared = 0, unref = 0, libSkipped = 0;
		for (Map.Entry<String, Set<Function>> e : users.entrySet()) {
			Set<Function> fs = e.getValue();
			if (fs.isEmpty()) { unref++; continue; }
			if (fs.size() > 1) { shared++; continue; }
			Function f = fs.iterator().next();
			boolean lib = false;
			for (FunctionTag t : f.getTags()) if (t.getName().equals("lib")) lib = true;
			if (lib) { libSkipped++; continue; }
			unique++;
			hints.computeIfAbsent(f, k -> new ArrayList<>()).add(e.getKey());
		}
		StringBuilder tsv = new StringBuilder("address\tname\tcount\thints\n");
		int commented = 0;
		for (Map.Entry<Function, List<String>> e : hints.entrySet()) {
			Function f = e.getKey();
			List<String> hs = e.getValue();
			hs.sort((x, y) -> {
				int px = PRIO.matcher(x).find() ? 0 : 1, py = PRIO.matcher(y).find() ? 0 : 1;
				return px != py ? px - py : y.length() - x.length();
			});
			List<String> lines = new ArrayList<>();
			for (int i = 0; i < Math.min(3, hs.size()); i++) {
				String h = hs.get(i).replace("\n", " ");
				lines.add("str: " + (h.length() > 120 ? h.substring(0, 120) + "..." : h));
			}
			if (hs.size() > 3) lines.add("str: (+" + (hs.size() - 3) + " more unique strings)");
			if (apply) {
				String old = f.getComment();
				StringBuilder keep = new StringBuilder();
				if (old != null) for (String l : old.split("\n")) if (!l.startsWith("str: ")) { if (keep.length() > 0) keep.append('\n'); keep.append(l); }
				f.setComment((keep.length() > 0 ? keep + "\n" : "") + String.join("\n", lines));
				f.addTag("str");
			}
			commented++;
			tsv.append(f.getEntryPoint()).append('\t').append(f.getName(true)).append('\t').append(hs.size()).append('\t').append(String.join(" || ", lines)).append('\n');
		}
		if (apply) fm.getFunctionTagManager().getFunctionTag("str").setComment("Has str: plate-comment hints (G1 naming pass): unique debug/error/log strings; a hint, not a name");
		new File(args[1]).mkdirs();
		try (Writer w = new FileWriter(new File(args[1], "string_hints.tsv"))) { w.write(tsv.toString()); }
		println((apply ? "APPLIED" : "DRY RUN") + ": message strings=" + messages + " distinct texts=" + users.size() + " unique to one function=" + unique
			+ " shared by several=" + shared + " unreferenced=" + unref + " in lib functions (skipped)=" + libSkipped + " functions hinted=" + commented);
	}
}
