// Minimal offline mission used by NoronhaMapExporter for installed DayZ worlds.
// It creates and selects the local player without copying economy or CE data.

class DayZMapExporterMission: MissionServer
{
	override PlayerBase CreateCharacter(PlayerIdentity identity, vector pos, ParamsReadContext ctx, string characterName)
	{
		Entity playerEntity = GetGame().CreatePlayer(identity, characterName, pos, 0, "NONE");
		Class.CastTo(m_player, playerEntity);
		GetGame().SelectPlayer(identity, m_player);
		return m_player;
	}
};

Mission CreateCustomMission(string path)
{
	return new DayZMapExporterMission();
}
