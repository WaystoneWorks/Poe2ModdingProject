-- Feeds stat description text to PoB2's ModParser. Input TSV: stat ids (comma separated), sample
-- values, text. Output TSV: stat ids, status, text, mods. Used by `cargo xtask stats-map`.
require("pob_boot")
local input, output = pob_args[1], pob_args[2]

local function tag_text(t)
  local parts = {}
  for k, v in pairs(t) do
    if type(v) ~= "table" then parts[#parts + 1] = k .. "=" .. tostring(v) end
  end
  table.sort(parts)
  return "{" .. table.concat(parts, ",") .. "}"
end

local function mod_text(m)
  local s = m.name .. ":" .. tostring(m.type) .. ":" .. tostring(type(m.value) == "table" and "table" or m.value)
  if (m.flags or 0) ~= 0 then s = s .. ":flags=" .. m.flags end
  if (m.keywordFlags or 0) ~= 0 then s = s .. ":kw=" .. m.keywordFlags end
  for _, t in ipairs(m) do s = s .. ":" .. tag_text(t) end
  return s
end

local out = assert(io.open(output, "w"))
for line in io.lines(input) do
  local ids, values, text = line:match("^([^\t]*)\t([^\t]*)\t(.*)$")
  local mods, status = {}, "ok"
  for part in (text .. "\\n"):gmatch("(.-)\\n") do
    local list, extra = modLib.parseMod(part)
    if not list then
      status = "unparsed"
    else
      if extra then status = "partial" end
      for _, m in ipairs(list) do mods[#mods + 1] = mod_text(m) end
    end
  end
  if status == "ok" and #mods == 0 then status = "no_mods" end
  out:write(ids, "\t", values, "\t", status, "\t", text, "\t", table.concat(mods, " ; "), "\n")
end
out:close()
