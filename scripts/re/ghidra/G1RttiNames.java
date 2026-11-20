// G1 step 1: names vtables and vtable slot functions from the binary's MSVC RTTI.
// Finds every complete object locator (COL) by its self-RVA, the vtable after the qword that
// points to it, the class from the type descriptor's Ghidra namespace (the RTTI analyzer's
// Class::RTTI_Type_Descriptor), and the base classes from the class hierarchy descriptor.
// Labels each vtable `vftable` in its class namespace when it has no label, and names each slot
// function that still has a default name `Class::vf_XX` (XX = slot index in hex; `vf_XX_oNN`
// for the vtable of the subobject at offset NN). A function in several vtables is named only
// when one of those classes is a base of all the others at the same slot (inherited, not
// overridden); otherwise (identical-code-folded helpers) it stays unnamed.
// Args: <out dir> [apply]. Without `apply` it is a dry run. Writes <out dir>/rtti_slots.tsv.
//@category PoE2
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.*;
import ghidra.program.model.listing.*;
import ghidra.program.model.mem.*;
import ghidra.program.model.symbol.*;
import java.io.*;
import java.util.*;

public class G1RttiNames extends GhidraScript {
	static class Vt { Address at, col; long td; int off; Namespace cls; String tdName; Set<Long> bases = new HashSet<>(); List<Address> slots = new ArrayList<>(); }
	static class Occ { Vt vt; int slot; Occ(Vt v, int s) { vt = v; slot = s; } }

	Memory mem; long base;

	Address va(long rva) { return toAddr(base + (rva & 0xffffffffL)); }
	boolean exec(Address a) { MemoryBlock b = mem.getBlock(a); return b != null && b.isExecute() && b.isInitialized(); }

	String cstr(Address a) throws Exception {
		StringBuilder s = new StringBuilder();
		for (int i = 0; i < 4096; i++) { byte c = mem.getByte(a.add(i)); if (c == 0) break; s.append((char) (c & 0xff)); }
		return s.toString();
	}

	@Override
	public void run() throws Exception {
		String[] args = getScriptArgs();
		String outDir = args[0];
		boolean apply = args.length > 1 && args[1].equals("apply");
		mem = currentProgram.getMemory();
		base = currentProgram.getImageBase().getOffset();
		SymbolTable st = currentProgram.getSymbolTable();
		FunctionManager fm = currentProgram.getFunctionManager();

		// 1. COLs: signature 1, self RVA at +20 equals its own RVA, TD RVA lands in memory.
		Map<Long, long[]> cols = new HashMap<>(); // col va -> {offset, tdRva, chdRva}
		for (MemoryBlock b : mem.getBlocks()) {
			if (!b.isInitialized() || b.isExecute()) continue;
			long start = (b.getStart().getOffset() + 3) & ~3L, end = b.getEnd().getOffset() - 24;
			byte[] buf = new byte[(int) (b.getEnd().getOffset() - b.getStart().getOffset() + 1)];
			b.getBytes(b.getStart(), buf);
			long bs = b.getStart().getOffset();
			for (long p = start; p <= end; p += 4) {
				int i = (int) (p - bs);
				if (le32(buf, i) != 1) continue;
				long self = le32(buf, i + 20) & 0xffffffffL;
				if (self != p - base) continue;
				long td = le32(buf, i + 12) & 0xffffffffL;
				if (!mem.contains(va(td))) continue;
				cols.put(p, new long[] { le32(buf, i + 4), td, le32(buf, i + 16) & 0xffffffffL });
			}
		}
		println("COLs found: " + cols.size());

		// 2. Vtables: a qword pointing at a COL; the vtable starts 8 bytes later.
		List<Vt> vts = new ArrayList<>();
		for (MemoryBlock b : mem.getBlocks()) {
			if (!b.isInitialized() || b.isExecute()) continue;
			byte[] buf = new byte[(int) (b.getEnd().getOffset() - b.getStart().getOffset() + 1)];
			b.getBytes(b.getStart(), buf);
			long bs = b.getStart().getOffset();
			for (int i = (int) ((8 - (bs & 7)) & 7); i + 16 <= buf.length; i += 8) {
				long q = le64(buf, i);
				long[] c = cols.get(q);
				if (c == null) continue;
				Vt v = new Vt();
				v.at = toAddr(bs + i + 8); v.col = toAddr(q); v.off = (int) c[0]; v.td = c[1];
				v.tdName = cstr(va(c[1]).add(16));
				// bases from CHD -> BCA -> BCD.pTypeDescriptor
				Address chd = va(c[2]);
				int nb = mem.getInt(chd.add(8));
				Address bca = va(mem.getInt(chd.add(12)));
				for (int k = 0; k < nb && k < 512; k++) v.bases.add((long) mem.getInt(va(mem.getInt(bca.add(4 * k)))) & 0xffffffffL);
				vts.add(v);
			}
		}
		println("vtables found: " + vts.size());

		// 3. Class namespaces from the TD's Ghidra symbol.
		int noNs = 0;
		for (Vt v : vts) {
			for (Symbol s : st.getSymbols(va(v.td))) {
				if (s.getName().startsWith("RTTI_Type_Descriptor") && !s.getParentNamespace().isGlobal()) { v.cls = s.getParentNamespace(); break; }
			}
			if (v.cls == null) noNs++;
		}

		// 4. Slots: the length of the pointer array Ghidra's RTTI analyzer defined at the vtable;
		// without one, executable pointers up to a COL pointer, another vtable or a named symbol
		// (code reads single slots, so references to a slot do not end the vtable).
		Set<Address> vtStarts = new HashSet<>();
		for (Vt v : vts) vtStarts.add(v.at);
		Map<Address, List<Occ>> occ = new HashMap<>();
		int slots = 0, sizedByGhidra = 0;
		for (Vt v : vts) {
			int max = 4096;
			Data d = getDataAt(v.at);
			if (d != null && d.isArray() && d.getLength() % 8 == 0) { max = d.getLength() / 8; sizedByGhidra++; }
			for (int k = 0; k < max; k++) {
				Address a = v.at.add(8L * k);
				if (k > 0 && (cols.containsKey(mem.getLong(a)) || vtStarts.contains(a))) break;
				if (k > 0 && max == 4096) {
					boolean named = false;
					for (Symbol s : st.getSymbols(a)) if (s.getSource() != SourceType.DEFAULT) named = true;
					if (named) break;
				}
				Address t;
				try { t = toAddr(mem.getLong(a)); } catch (Exception e) { break; }
				if (t == null || !exec(t)) break;
				v.slots.add(t);
				occ.computeIfAbsent(t, x -> new ArrayList<>()).add(new Occ(v, k));
				slots++;
			}
		}
		println("slots: " + slots + ", distinct targets: " + occ.size() + ", vtables sized by Ghidra's array: " + sizedByGhidra);

		// 5. Labels for vtables without one.
		int vtLabelled = 0, vtHad = 0, vtNoNs = 0;
		for (Vt v : vts) {
			boolean has = false;
			for (Symbol s : st.getSymbols(v.at)) if (s.getSource() != SourceType.DEFAULT) has = true;
			if (has) { vtHad++; continue; }
			if (v.cls == null) { vtNoNs++; continue; }
			if (apply) st.createLabel(v.at, v.off == 0 ? "vftable" : String.format("vftable_o%x", v.off), v.cls, SourceType.ANALYSIS);
			vtLabelled++;
		}

		// 6. Name slot functions.
		int named = 0, keptName = 0, noFunc = 0, shared = 0, thunks = 0, noCls = 0, dup = 0;
		StringBuilder tsv = new StringBuilder("target\tresult\tname\toccurrences\n");
		for (Map.Entry<Address, List<Occ>> e : occ.entrySet()) {
			Address t = e.getKey();
			List<Occ> os = e.getValue();
			Function f = fm.getFunctionAt(t);
			String occs = describe(os);
			if (f == null) { noFunc++; tsv.append(t).append("\tno_function\t\t").append(occs).append('\n'); continue; }
			if (f.isThunk()) { thunks++; tsv.append(t).append("\tthunk\t").append(f.getName(true)).append('\t').append(occs).append('\n'); continue; }
			if (f.getSymbol().getSource() != SourceType.DEFAULT) { keptName++; tsv.append(t).append("\tkept\t").append(f.getName(true)).append('\t').append(occs).append('\n'); continue; }
			Occ owner = owner(os);
			if (owner == null) { shared++; tsv.append(t).append("\tshared\t\t").append(occs).append('\n'); continue; }
			if (owner.vt.cls == null) { noCls++; tsv.append(t).append("\tno_class\t\t").append(occs).append('\n'); continue; }
			String n = owner.vt.off == 0 ? String.format("vf_%02x", owner.slot) : String.format("vf_%02x_o%x", owner.slot, owner.vt.off);
			try {
				if (apply) { f.setParentNamespace(owner.vt.cls); f.setName(n, SourceType.ANALYSIS); }
				named++;
				tsv.append(t).append("\tnamed\t").append(owner.vt.cls.getName(true)).append("::").append(n).append('\t').append(occs).append('\n');
			} catch (Exception ex) {
				dup++;
				tsv.append(t).append("\terror\t").append(ex.getMessage()).append('\t').append(occs).append('\n');
			}
		}
		new File(outDir).mkdirs();
		try (Writer w = new FileWriter(new File(outDir, "rtti_slots.tsv"))) { w.write(tsv.toString()); }
		println((apply ? "APPLIED" : "DRY RUN") + ": COLs=" + cols.size() + " vtables=" + vts.size() + " (no class ns " + noNs + ")"
			+ " vtables labelled=" + vtLabelled + " already labelled=" + vtHad + " unlabelled(no ns)=" + vtNoNs
			+ " | slots=" + slots + " targets=" + occ.size() + " named=" + named + " kept existing name=" + keptName
			+ " shared(unrelated classes)=" + shared + " thunks=" + thunks + " no function=" + noFunc + " no class=" + noCls + " errors=" + dup);
	}

	// The occurrence whose class is a base of (or equal to) every other occurrence's class at the same slot index.
	Occ owner(List<Occ> os) {
		if (os.size() == 1) return os.get(0);
		int slot = os.get(0).slot;
		for (Occ o : os) if (o.slot != slot) return null;
		Occ found = null;
		for (Occ c : os) {
			boolean all = true;
			for (Occ o : os) if (o != c && !o.vt.bases.contains(c.vt.td)) { all = false; break; }
			if (!all) continue;
			if (found != null && found.vt.td != c.vt.td) return null;
			if (found != null) return null; // same class twice (two subobject vtables): ambiguous
			found = c;
		}
		return found;
	}

	String describe(List<Occ> os) {
		StringBuilder s = new StringBuilder();
		int n = 0;
		for (Occ o : os) {
			if (n++ == 6) { s.append(" +" + (os.size() - 6)); break; }
			if (s.length() > 0) s.append(", ");
			s.append(o.vt.cls != null ? o.vt.cls.getName(true) : o.vt.tdName).append('@').append(Integer.toHexString(o.vt.off)).append('#').append(Integer.toHexString(o.slot));
		}
		return s.toString();
	}

	static int le32(byte[] b, int i) { return (b[i] & 0xff) | (b[i + 1] & 0xff) << 8 | (b[i + 2] & 0xff) << 16 | (b[i + 3] & 0xff) << 24; }
	static long le64(byte[] b, int i) { return (le32(b, i) & 0xffffffffL) | ((long) le32(b, i + 4)) << 32; }
}
