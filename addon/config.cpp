class CfgPatches
{
	class DayZMapExporter
	{
		units[] = {};
		weapons[] = {};
		requiredVersion = 0.1;
		requiredAddons[] = { "DZ_Data", "DZ_Gear_Navigation" };
	};
};

class MapDefaults;

// The product build stages the generated public control and location overrides
// below. The committed source remains neutral for a raw/development build.
// PUBLIC_CARTOGRAPHY_OVERRIDE_PLACEHOLDER
// CLEAN_LOCATION_OVERRIDE_PLACEHOLDER

class RscMapControlRaw: MapDefaults
{
};

class RscMapControlStyleActive: RscMapControlRaw
{
};

class RscMapControl: RscMapControlStyleActive
{
};

class CfgMods
{
	class DayZMapExporter
	{
		type = "mod";
		dir = "DayZMapExporter";
		name = "Noronha Map Exporter";
		author = "NoronhaMapExporter contributors";
		version = "1.0.0-rc.2";
		class defs
		{
			class missionScriptModule
			{
				value = "";
				files[] = { "DayZMapExporter/scripts/5_Mission" };
			};
		};
	};
};
