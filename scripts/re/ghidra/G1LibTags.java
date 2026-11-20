// G1 step 2b: tags statically linked library code that FID does not know (it was built with a
// newer MSVC than Ghidra's databases). Two reliable sources, tags only (no renames):
//  - the RTTI class namespace of a function (step 1 put vtable slots in their class): exprtk,
//    spirv_cross, CryptoPP, and std / the CRT's undname classes as msvc;
//  - a reference to a string that only the library itself contains (its source paths, its own
//    error texts, its version banner), from the table below.
// Each such function gets the tags `lib` and `lib:<name>`.
// Args: <strings.tsv from scripts/re/strings_va.py> <out dir> [apply]. Writes <out dir>/lib_tags.tsv.
//@category PoE2
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.*;
import ghidra.program.model.symbol.*;
import java.io.*;
import java.util.*;
import java.util.regex.*;

public class G1LibTags extends GhidraScript {
	static final String[][] STRINGS = {
		{ "oodle", "OODLE ERROR|\\\\oodle2\\\\|^Oodle(LZ|Core|Net|Tex|X)[A-Za-z]*_" },
		{ "libcurl", "CURLOPT_|curl_multi_perform|^easy handle already used in multi handle$|^Curl_|libcurl|^CURLE_|^Connection #%|Re-using existing connection" },
		{ "cryptopp", "(?i)cryptopp|CryptoMaterial|BER decode|: message length of|Clone\\(\\) is not implemented| is not a valid key length" },
		{ "zlib", "^ ?(in|de)flate 1\\.|^incorrect header check$|^invalid distance too far back$|^invalid stored block lengths$|^invalid block type$|^incorrect data check$" },
		{ "stb_image", "^(bad png sig|bad zlib header|zlib corrupt|bad huffman code|unknown image type|bad IHDR len|corrupt JPEG|outofmem|bad codelengths|bad sizes|no SOI)$" },
		{ "mimalloc", "^mimalloc" },
		{ "brotli", "javascriptconditions|gustomentemariofirma" },
		{ "spirv_cross", "^SPIRV file too small\\.$|^Invalid SPIRV format\\.$|^SPIR-V instructions cannot consume|^SPIR-V instruction goes out of bounds|^There is no entry point in the SPIR-V module|^Likely cause: If this SPIR-V" },
		{ "exprtk", "(?i)exprtk" },
		{ "msvc", "^api-ms-win-|^ext-ms-win-|^mscoree\\.dll$|^CorExitProcess$|crts\\\\ucrt" },
	};
	static final Map<String, String> NAMESPACES = Map.of("exprtk", "exprtk", "spirv_cross", "spirv_cross", "CryptoPP", "cryptopp",
		"std", "msvc", "DName", "msvc", "DNameNode", "msvc", "charNode", "msvc", "pcharNode", "msvc", "pDNameNode", "msvc");

	@Override
	public void run() throws Exception {
		String[] args = getScriptArgs();
		boolean apply = args.length > 2 && args[2].equals("apply");
		FunctionManager fm = currentProgram.getFunctionManager();
		Map<Function, String> tag = new LinkedHashMap<>();
		Map<Function, String> via = new HashMap<>();
		Map<String, Integer> byNs = new TreeMap<>(), byStr = new TreeMap<>(), strHits = new TreeMap<>();

		for (Function f : fm.getFunctions(true)) {
			Namespace ns = f.getParentNamespace();
			if (ns == null || ns.isGlobal()) continue;
			while (!ns.getParentNamespace().isGlobal()) ns = ns.getParentNamespace();
			String lib = NAMESPACES.get(ns.getName());
			if (lib == null && ns.getName().startsWith("UnDecorator")) lib = "msvc";
			if (lib == null) continue;
			tag.put(f, lib); via.put(f, "namespace " + ns.getName());
			byNs.merge(lib, 1, Integer::sum);
		}

		Pattern[] ps = new Pattern[STRINGS.length];
		for (int i = 0; i < ps.length; i++) ps[i] = Pattern.compile(STRINGS[i][1]);
		ReferenceManager rm = currentProgram.getReferenceManager();
		try (BufferedReader r = new BufferedReader(new InputStreamReader(new FileInputStream(args[0]), "UTF-8"))) {
			String line;
			while ((line = r.readLine()) != null) {
				String[] c = line.split("\t", 3);
				if (c.length < 3) continue;
				for (int i = 0; i < ps.length; i++) {
					if (!ps[i].matcher(c[2]).find()) continue;
					strHits.merge(STRINGS[i][0], 1, Integer::sum);
					Address a = toAddr(Long.parseUnsignedLong(c[0], 16));
					for (Reference ref : rm.getReferencesTo(a)) {
						Function f = fm.getFunctionContaining(ref.getFromAddress());
						if (f == null || tag.containsKey(f)) continue;
						tag.put(f, STRINGS[i][0]); via.put(f, "string \"" + c[2].substring(0, Math.min(60, c[2].length())) + "\"");
						byStr.merge(STRINGS[i][0], 1, Integer::sum);
					}
					break;
				}
			}
		}

		StringBuilder tsv = new StringBuilder("address\tname\tlib\tvia\n");
		int added = 0;
		for (Map.Entry<Function, String> e : tag.entrySet()) {
			Function f = e.getKey();
			if (apply) { f.addTag("lib"); f.addTag("lib:" + e.getValue()); }
			added++;
			tsv.append(f.getEntryPoint()).append('\t').append(f.getName(true)).append('\t').append(e.getValue()).append('\t').append(via.get(f)).append('\n');
		}
		if (apply) {
			FunctionTagManager tm = fm.getFunctionTagManager();
			if (tm.getFunctionTag("lib") != null) tm.getFunctionTag("lib").setComment("Statically linked library code (G1 naming pass); skip in searches");
		}
		new File(args[1]).mkdirs();
		try (Writer w = new FileWriter(new File(args[1], "lib_tags.tsv"))) { w.write(tsv.toString()); }
		println((apply ? "APPLIED" : "DRY RUN") + ": functions tagged=" + added + " by namespace=" + byNs + " by string=" + byStr + " matching strings=" + strHits);
	}
}
