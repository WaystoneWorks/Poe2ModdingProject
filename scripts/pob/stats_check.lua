-- Runs fixture characters through headless PoB2. `query <out.json>` writes what the generator needs
-- (item bases, class ids, tree links); `eval <in.jsonl> <out.jsonl>` writes each build's outputs.
-- Used by `cargo xtask stats-check`.
require("pob_boot")
local json = require("dkjson")
local mode, input, output = pob_args[1], pob_args[2], pob_args[3]

local KEYS = { "Life", "Mana", "Spirit", "EnergyShield", "Armour", "Evasion", "Ward", "FireResist", "ColdResist",
  "LightningResist", "ChaosResist", "BlockChance", "LifeRegen", "ManaRegen", "EnergyShieldRecharge", "Str", "Dex", "Int",
  "Accuracy", "AverageHit", "Speed", "CritChance", "CritMultiplier", "MovementSpeedMod", "StunThreshold", "AilmentThreshold" }

local function quest_config()
  local s = {}
  for _, quest in ipairs(build.data.questRewards) do
    if quest.useConfig ~= false then
      local key = "quest" .. quest.Description .. quest.Area .. quest.Info
      s[#s + 1] = ('<Input name="%s" boolean="false"/>'):format(key:gsub("&", "&amp;"):gsub('"', "&quot;"))
    end
  end
  return table.concat(s)
end

if mode == "query" then
  local q = { bases = {}, classes = {}, starts = {}, links = {} }
  for name in pairs(build.data.itemBases) do q.bases[#q.bases + 1] = name end
  table.sort(q.bases)
  for id, c in pairs(build.spec.tree.classes) do
    q.classes[c.name] = c.integerId or id
    q.starts[c.name] = c.startNodeId
  end
  for id, node in pairs(build.spec.tree.nodes) do
    local l = {}
    for _, other in ipairs(node.linked or {}) do l[#l + 1] = other.id end
    q.links[tostring(id)] = l
  end
  local f = assert(io.open(input, "w"))
  f:write(json.encode(q))
  f:close()
  os.exit(0)
end

local quests = quest_config()
local out = assert(io.open(output, "w"))
for line in io.lines(input) do
  local fx = json.decode(line)
  local xml = fx.xml:gsub("<!%-%-QUESTS%-%->", function() return quests end)
  __mainObject__.promptMsg = nil
  loadBuildFromXML(xml, fx.name)
  local res = { name = fx.name }
  if __mainObject__.promptMsg then
    res.error = tostring(__mainObject__.promptMsg)
  else
    local b = __mainObject__.main.modes["BUILD"]
    local o = b.calcsTab.mainOutput
    local mh = o.MainHand or {}
    local sk = b.calcsTab.mainEnv.player.mainSkill
    for _, k in ipairs(KEYS) do
      local v = o[k]
      if v == nil then v = mh[k] end
      res[k] = v
    end
    res.skill = sk.activeEffect.grantedEffect.name
    res.skill_multiplier = sk.activeEffect.grantedEffectLevel.baseMultiplier or sk.skillData.baseMultiplier or 1
    res.class = b.spec.curClassName
    res.nodes = 0
    for _ in pairs(b.spec.allocNodes) do res.nodes = res.nodes + 1 end
  end
  out:write(json.encode(res), "\n")
end
out:close()
