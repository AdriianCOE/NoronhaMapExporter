class CfgPatches
{
	class NoronhaMapExporter
	{
		units[] = {};
		weapons[] = {};
		requiredVersion = 0.1;
		requiredAddons[] = { "DZ_Data" };
	};
};

// A standalone MapWidget resolves its map palette and symbols through this
// global control class. The concrete values remain the vanilla MapDefaults.
class MapDefaults;
class RscMapControl: MapDefaults
{
};

class CfgMods
{
	class NoronhaMapExporter
	{
		type = "mod";
		dir = "NoronhaMapExporter";
		name = "Noronha Map Exporter (Development)";
		author = "Noronha";
		version = "0.1.0-dev";
		class defs
		{
			class missionScriptModule
			{
				value = "";
				files[] = { "NoronhaMapExporter/scripts/5_Mission" };
			};
		};
	};
};
