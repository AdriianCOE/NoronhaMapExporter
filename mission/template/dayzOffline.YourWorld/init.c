// Minimal offline mission used by NoronhaMapExporter for installed DayZ worlds.
// It initializes offline Hive data and creates the local player required by
// a DayZDiag -mission session. It deliberately does not copy terrain economy
// or CE data.

void main()
{
	Hive hive = CreateHive();
	if (hive)
	{
		hive.InitOffline();
	}
}

class DayZMapExporterMission: MissionGameplay
{
	override void OnInit()
	{
		super.OnInit();

		vector spawnPos = "7500 0 7500";
		spawnPos[1] = GetGame().SurfaceY(spawnPos[0], spawnPos[2]);

		PlayerBase player = PlayerBase.Cast(
			GetGame().CreatePlayer(NULL, GetGame().CreateRandomPlayer(), spawnPos, 0, "NONE") );

		if (player)
		{
			GetGame().SelectPlayer(NULL, player);
			Print("[DayZMapExporter] Local player created and selected at " + spawnPos);
		}
		else
		{
			Print("[DayZMapExporter] ERROR: local player creation failed.");
		}
	}
}

Mission CreateCustomMission(string path)
{
	return new DayZMapExporterMission();
}
