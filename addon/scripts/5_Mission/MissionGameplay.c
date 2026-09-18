modded class MissionGameplay
{
	protected ref NoronhaMapExporter m_NoronhaMapExporter;

	override void OnUpdate(float timeslice)
	{
		super.OnUpdate(timeslice);
		if (m_NoronhaMapExporter)
			m_NoronhaMapExporter.Update(timeslice);
	}

	override void OnKeyPress(int key)
	{
		super.OnKeyPress(key);

		if ((KeyState(KeyCode.KC_LCONTROL) || KeyState(KeyCode.KC_RCONTROL)) && key == KeyCode.KC_F8)
		{
			if (!m_NoronhaMapExporter)
				m_NoronhaMapExporter = new NoronhaMapExporter();
			m_NoronhaMapExporter.Toggle();
			return;
		}

		if (m_NoronhaMapExporter && m_NoronhaMapExporter.IsOpen())
			m_NoronhaMapExporter.HandleKeyPress(key);
	}
};
