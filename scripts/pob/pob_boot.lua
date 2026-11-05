-- Boots Path of Building 2 (third_party/PathOfBuilding-PoE2) headless under LuaJIT. PoB's sources
-- start with a "#@" line its own launcher strips, so the loaders are wrapped to strip it too.
-- Run from PoB's src directory; see scripts/pob/run.sh.
local function strip_load(path)
  local f, e = io.open(path, "rb")
  if not f then return nil, e end
  local s = f:read("*a")
  f:close()
  s = s:gsub("^#[^\n]*\n", "\n", 1)
  return loadstring(s, "@" .. path)
end
local real_loadfile = loadfile
loadfile = function(path, ...)
  if path then return strip_load(path) end
  return real_loadfile(path, ...)
end
dofile = function(path, ...)
  return assert(strip_load(path))(...)
end
table.insert(package.loaders, 2, function(name)
  local rel = name:gsub("%.", "/")
  for tpl in package.path:gmatch("[^;]+") do
    local q = tpl:gsub("%?", rel)
    local f = io.open(q)
    if f then
      f:close()
      return strip_load(q)
    end
  end
end)
-- PoB prints its startup chatter to stdout; drivers print results to stderr-free stdout after this.
-- PoB reads `arg` as a build to open, so drivers get theirs through `pob_args`. A PoB error prompt
-- waits on stdin in the wrapper: make it end the run instead.
pob_args = arg
arg = {}
local real_read = io.read
io.read = function() return nil end
local real_print = print
print = function() end
dofile("HeadlessWrapper.lua")
print = real_print
io.read = real_read
if __mainObject__.promptMsg then
  io.stderr:write("PoB2 failed to start: ", tostring(__mainObject__.promptMsg), "\n")
  os.exit(1)
end
