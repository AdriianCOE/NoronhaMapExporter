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

// A standalone MapWidget resolves its map palette and symbols through this
// global control class.  DayZ's MapDefaults is runtime-provided: this PC's
// shipped PBO configs do not expose its source text.  The presets below are
// deliberately small runtime candidates, captured one at a time by the clean
// cartography audit.  Raw remains an empty MapDefaults-derived control.
class MapDefaults;

// The public product pipeline injects a generated, property-based map control
// here in an ignored staging copy. Development audit classes below remain
// internal and are never exposed as public presets.
// PUBLIC_CARTOGRAPHY_OVERRIDE_PLACEHOLDER

// The build script replaces this marker only in its ignored staging directory.
// Keeping the committed source empty makes a normal/raw build neutral.
// CLEAN_LOCATION_OVERRIDE_PLACEHOLDER

class RscMapControlRaw: MapDefaults
{
};

class RscMapControlNoGrid: RscMapControlRaw
{
	colorGrid[] = {0, 0, 0, 0};
	colorGridMap[] = {0, 0, 0, 0};
};

class RscMapControlNoLabels: RscMapControlRaw
{
	colorNames[] = {0, 0, 0, 0};
};

class RscMapControlNoIcons: RscMapControlRaw
{
	colorChurches[] = {0, 0, 0, 0};
	colorChapel[] = {0, 0, 0, 0};
	colorCross[] = {0, 0, 0, 0};
	colorFortress[] = {0, 0, 0, 0};
	colorFountain[] = {0, 0, 0, 0};
	colorHospital[] = {0, 0, 0, 0};
	colorFuelstation[] = {0, 0, 0, 0};
	colorViewPoint[] = {0, 0, 0, 0};
	colorTransmitter[] = {0, 0, 0, 0};
	colorBusStop[] = {0, 0, 0, 0};
	colorAirport[] = {0, 0, 0, 0};
	colorPower[] = {0, 0, 0, 0};
	colorShipwreck[] = {0, 0, 0, 0};
	colorTourism[] = {0, 0, 0, 0};
	colorWatertower[] = {0, 0, 0, 0};
	colorQuay[] = {0, 0, 0, 0};
	colorRock[] = {0, 0, 0, 0};
	colorRuine[] = {0, 0, 0, 0};
	colorStack[] = {0, 0, 0, 0};
	colorMilitary[] = {0, 0, 0, 0};
};

class RscMapControlReducedVegetation: RscMapControlRaw
{
	colorForest[] = {0.35, 0.55, 0.22, 0.16};
	colorForestBorder[] = {0.35, 0.55, 0.22, 0.08};
};

class RscMapControlSoftContours: RscMapControlRaw
{
	colorCountlines[] = {0.35, 0.35, 0.35, 0.16};
	colorMainCountlines[] = {0.25, 0.25, 0.25, 0.30};
};

class RscMapControlPalette: RscMapControlRaw
{
	colorBackground[] = {0.93, 0.92, 0.86, 1};
	colorOutside[] = {0.82, 0.84, 0.80, 1};
	colorSea[] = {0.62, 0.77, 0.84, 0.85};
	colorForest[] = {0.48, 0.66, 0.40, 0.30};
	colorForestBorder[] = {0.42, 0.58, 0.35, 0.16};
	colorRocks[] = {0.55, 0.52, 0.47, 0.18};
	colorRocksBorder[] = {0.46, 0.43, 0.39, 0.16};
	colorRoads[] = {0.86, 0.78, 0.62, 0.80};
	colorMainRoads[] = {0.78, 0.64, 0.42, 0.90};
	colorTracks[] = {0.62, 0.53, 0.42, 0.52};
	colorBuildings[] = {0.43, 0.43, 0.40, 0.90};
};

class RscMapControlCombinedV1: RscMapControlPalette
{
	colorGrid[] = {0, 0, 0, 0};
	colorGridMap[] = {0, 0, 0, 0};
	colorNames[] = {0, 0, 0, 0};
	colorChurches[] = {0, 0, 0, 0};
	colorChapel[] = {0, 0, 0, 0};
	colorCross[] = {0, 0, 0, 0};
	colorFortress[] = {0, 0, 0, 0};
	colorFountain[] = {0, 0, 0, 0};
	colorHospital[] = {0, 0, 0, 0};
	colorFuelstation[] = {0, 0, 0, 0};
	colorViewPoint[] = {0, 0, 0, 0};
	colorTransmitter[] = {0, 0, 0, 0};
	colorBusStop[] = {0, 0, 0, 0};
	colorAirport[] = {0, 0, 0, 0};
	colorPower[] = {0, 0, 0, 0};
	colorShipwreck[] = {0, 0, 0, 0};
	colorTourism[] = {0, 0, 0, 0};
	colorWatertower[] = {0, 0, 0, 0};
	colorQuay[] = {0, 0, 0, 0};
	colorRock[] = {0, 0, 0, 0};
	colorRuine[] = {0, 0, 0, 0};
	colorStack[] = {0, 0, 0, 0};
	colorMilitary[] = {0, 0, 0, 0};
	colorForest[] = {0.35, 0.55, 0.22, 0.16};
	colorForestBorder[] = {0.35, 0.55, 0.22, 0.08};
	colorCountlines[] = {0.35, 0.35, 0.35, 0.16};
	colorMainCountlines[] = {0.25, 0.25, 0.25, 0.30};
};

// Audit candidates for a terrain-rich engine-clean style. They retain the
// CombinedV1 hierarchy but restore useful vegetation mass and readable
// contours. Location text and NameIcon removal is injected only by the
// matching staged build variant.
class RscMapControlEngineCleanDetailAudit: RscMapControlCombinedV1
{
	// Calibrated against the runtime RAW forest fill (warm, living green),
	// while retaining the engine-clean detail hierarchy.
	colorForest[] = {0.68, 0.94, 0.42, 0.60};
	colorForestBorder[] = {0.50, 0.76, 0.24, 0.46};
	colorCountlines[] = {0.40, 0.33, 0.27, 0.42};
	colorMainCountlines[] = {0.30, 0.24, 0.20, 0.60};
};

class RscMapControlEngineCleanOverviewAudit: RscMapControlCombinedV1
{
	// At overview scale, a deeper green prevents the forest mass from washing
	// out when the full-world mosaic is reduced.
	colorForest[] = {0.58, 0.85, 0.34, 0.74};
	colorForestBorder[] = {0.42, 0.66, 0.20, 0.60};
	colorCountlines[] = {0.40, 0.33, 0.27, 0.50};
	colorMainCountlines[] = {0.30, 0.24, 0.20, 0.68};
};

// Frozen runtime-approved presets. Their separate hierarchy preserves
// terrain character at each export scale without altering terrain data.
class RscMapControlEngineCleanDetail: RscMapControlEngineCleanDetailAudit
{
};

class RscMapControlEngineCleanOverview: RscMapControlEngineCleanOverviewAudit
{
};

// Isolated runtime satellite-layer audit. These controls were identified as
// engine configuration candidates and are intentionally not public options
// until the local MapWidget proves that they have an observable effect.
class RscMapControlSatelliteForced: MapDefaults
{
	maxSatelliteAlpha = 1;
	alphaFadeStartScale = 1;
	alphaFadeEndScale = 1;
};

class RscMapControlSatelliteIsolated: RscMapControlSatelliteForced
{
	colorGrid[] = {0, 0, 0, 0};
	colorGridMap[] = {0, 0, 0, 0};
	colorForest[] = {0, 0, 0, 0};
	colorForestBorder[] = {0, 0, 0, 0};
	colorRocks[] = {0, 0, 0, 0};
	colorRocksBorder[] = {0, 0, 0, 0};
	colorCountlines[] = {0, 0, 0, 0};
	colorMainCountlines[] = {0, 0, 0, 0};
	colorCountlinesWater[] = {0, 0, 0, 0};
	colorMainCountlinesWater[] = {0, 0, 0, 0};
	colorRoads[] = {0, 0, 0, 0};
	colorMainRoads[] = {0, 0, 0, 0};
	colorTracks[] = {0, 0, 0, 0};
	colorPowerLines[] = {0, 0, 0, 0};
	colorRailWay[] = {0, 0, 0, 0};
	colorBuildings[] = {0, 0, 0, 0};
};

// The build script replaces only this base class in its ignored staged copy.
// Keep the committed source on Raw so a normal build remains the reference.
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
		name = "DayZ Map Exporter";
		author = "DayZMapExporter contributors";
		version = "0.1.0-dev";
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
