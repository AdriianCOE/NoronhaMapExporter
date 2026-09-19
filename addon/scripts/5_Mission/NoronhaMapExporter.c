class NoronhaMapExporterTile
{
	int GridX;
	int GridZ;
	int Index;
	string Filename;
	vector RequestedCenter;
	vector GetMapPos;
	float GetScale;
	float WidgetPixelX;
	float WidgetPixelY;
	float WidgetPixelWidth;
	float WidgetPixelHeight;
	float Left;
	float Right;
	float Top;
	float Bottom;
	vector TopLeft;
	vector TopRight;
	vector BottomLeft;
	vector BottomRight;
	float VisibleWorldWidth;
	float VisibleWorldHeight;
	float MetersPerPixelX;
	float MetersPerPixelZ;
	string ZAxisDirection;
	float TargetScale;
	int PngWidth;
	int PngHeight;
	string Sha256;
	int RequestId;
};

class DayZMapDetailAuditConfig
{
	bool Enabled;
	float CenterX;
	float CenterZ;
	ref array<float> Scales;
};

class DayZMapExporterConfig
{
	string WorldName;
	float WorldSize;
	float WorldMinX;
	float WorldMaxX;
	float WorldMinZ;
	float WorldMaxZ;
	float ExportScale;
	float OverlapFraction;
	string OutputPrefix;
	bool AutoCaptureEnabled;
	int StabilizationFrames;
	float StabilizationTolerance;
	float CaptureTimeoutSeconds;
	ref DayZMapDetailAuditConfig DetailAudit;
};

class DayZMapCaptureAck
{
	// JsonFileLoader maps field names exactly. Keep these aligned with the
	// lower-camel-case ACK written by the external capture helper.
	int protocolVersion;
	string sessionId;
	int requestId;
	string filename;
	int width;
	int height;
	string sha256;
	string status;
	string error;
};

class NoronhaMapExporter
{
	protected const string LAYOUT_PATH = "DayZMapExporter/gui/layouts/noronha_map_exporter.layout";
	protected const string LOG_PREFIX = "[DayZMapExporter] ";
	protected const float CONSISTENCY_TOLERANCE = 0.01;
	protected const float SQUARE_PIXEL_TOLERANCE = 0.001;
	protected const int AUTO_STATE_IDLE = 0;
	protected const int AUTO_STATE_SETTLING = 1;
	protected const int AUTO_STATE_WAITING_FOR_ACK = 2;
	protected const int AUTO_STATE_CAPTURE_FAILED = 3;
	protected const int AUTO_STATE_EXPORT_COMPLETE = 4;
	protected const string CONFIG_PATH = "$profile:/DayZMapExporter/exporter-config.json";

	protected ref Widget m_Root;
	protected ref MapWidget m_Map;
	protected ref Widget m_DebugOverlay;
	protected ref TextWidget m_DebugText;
	protected ref NoronhaMapExporterTile m_CurrentTile;
	protected ref array<ref NoronhaMapExporterTile> m_VisitedTiles;
	protected ref array<ref NoronhaMapExporterTile> m_CapturedTiles;
	protected ref array<ref NoronhaMapExporterTile> m_CaptureSequence;
	protected ref DayZMapExporterConfig m_Config;
	protected vector m_RequestedCenter;
	protected bool m_IsOpen;
	protected bool m_DebugVisible;
	protected bool m_IsCalibrated;
	protected bool m_FullExportActive;
	protected bool m_FullExportCompleted;
	protected bool m_CaptureReady;
	protected bool m_AutomaticExportActive;
	protected bool m_AutoSmokeActive;
	protected bool m_DetailAuditActive;
	protected int m_CalibrationFramesRemaining;
	protected int m_TileReadFramesRemaining;
	protected int m_GridX;
	protected int m_GridZ;
	protected int m_GridColumns;
	protected int m_GridRows;
	protected int m_CaptureSequenceIndex;
	protected int m_SessionNonce;
	protected int m_AutoState;
	protected int m_AutoRequestId;
	protected int m_AutoCleanFramesRemaining;
	protected int m_ActiveGridColumns;
	protected int m_ActiveGridRows;
	protected float m_AckWaitSeconds;
	protected float m_ExpectedScale;
	protected bool m_AckFileSeen;
	protected bool m_AckFieldsLogged;
	protected float m_TileStepX;
	protected float m_TileStepZ;
	protected float m_TileZeroCenterX;
	protected float m_TileZeroCenterZ;
	protected string m_SessionDirectory;
	protected string m_SessionId;

	void NoronhaMapExporter()
	{
		m_VisitedTiles = new array<ref NoronhaMapExporterTile>();
		m_CapturedTiles = new array<ref NoronhaMapExporterTile>();
		m_CaptureSequence = new array<ref NoronhaMapExporterTile>();
	}

	bool IsOpen()
	{
		return m_IsOpen;
	}

	void Toggle()
	{
		if (m_IsOpen) Close();
		else Open();
	}

	void Open()
	{
		if (m_IsOpen) return;
		if (!LoadConfiguration()) return;
		m_Root = g_Game.GetWorkspace().CreateWidgets(LAYOUT_PATH);
		m_Map = MapWidget.Cast(m_Root.FindAnyWidget("NoronhaMap"));
		m_DebugOverlay = m_Root.FindAnyWidget("DebugOverlay");
		m_DebugText = TextWidget.Cast(m_Root.FindAnyWidget("DebugText"));
		if (!m_Map)
		{
			Print(LOG_PREFIX + "ERROR: MapWidget was not created.");
			m_Root.Unlink();
			m_Root = null;
			return;
		}
		m_IsOpen = true;
		m_IsCalibrated = false;
		m_FullExportActive = false;
		m_FullExportCompleted = false;
		m_CaptureReady = false;
		m_AutomaticExportActive = false;
		m_AutoSmokeActive = false;
		m_DetailAuditActive = false;
		m_AutoState = AUTO_STATE_IDLE;
		m_AutoRequestId = 0;
		m_GridX = 0;
		m_GridZ = 0;
		m_GridColumns = 0;
		m_GridRows = 0;
		m_CaptureSequenceIndex = -1;
		m_VisitedTiles.Clear();
		m_CapturedTiles.Clear();
		m_CaptureSequence.Clear();
		m_CalibrationFramesRemaining = m_Config.StabilizationFrames;
		m_RequestedCenter = Vector((m_Config.WorldMinX + m_Config.WorldMaxX) * 0.5, 0, (m_Config.WorldMinZ + m_Config.WorldMaxZ) * 0.5);
		m_ExpectedScale = m_Config.ExportScale;
		m_Root.Update();
		m_Map.ClearUserMarks();
		m_Map.SetScale(m_Config.ExportScale);
		m_Map.SetMapPos(m_RequestedCenter);
		ShowHud(false);
		ShowCursorWidget(false);
		SetDebugVisible(false);
		Print(LOG_PREFIX + "Opened. Calibrating from ScreenToMap after the map has rendered.");
	}

	void Close()
	{
		if (!m_IsOpen) return;
		ShowHud(true);
		ShowCursorWidget(true);
		m_Root.Unlink();
		m_Root = null;
		m_Map = null;
		m_DebugOverlay = null;
		m_DebugText = null;
		m_CurrentTile = null;
		m_IsOpen = false;
		Print(LOG_PREFIX + "Closed.");
	}

	void Update(float timeslice)
	{
		if (!m_IsOpen || !m_Map) return;
		if (!m_IsCalibrated)
		{
			m_CalibrationFramesRemaining--;
			if (m_CalibrationFramesRemaining <= 0) CalibrateGrid();
			return;
		}
		if (m_AutomaticExportActive && m_AutoState == AUTO_STATE_WAITING_FOR_ACK)
		{
			TickAutomaticAck(timeslice);
			return;
		}
		if (m_TileReadFramesRemaining > 0)
		{
			m_TileReadFramesRemaining--;
			if (m_TileReadFramesRemaining == 0)
			{
				RefreshCurrentTile();
				PrintCurrentTile();
				CheckRepeatability();
				if (!IsCurrentTileStable())
				{
					Print(LOG_PREFIX + "Waiting for stable MapWidget bounds before capture.");
					m_TileReadFramesRemaining = 1;
					return;
				}
				if (m_AutomaticExportActive && m_AutoCleanFramesRemaining > 0)
				{
					m_AutoCleanFramesRemaining--;
					m_TileReadFramesRemaining = 1;
					return;
				}
				m_CaptureReady = true;
				if (m_AutomaticExportActive) BeginAutomaticCapture();
				else if (m_FullExportActive) PrintCaptureReady();
			}
			return;
		}
		RefreshCurrentTile();
	}

	void HandleKeyPress(int key)
	{
		if (!m_IsOpen) return;
		switch (key)
		{
			case KeyCode.KC_ESCAPE: Close(); break;
			case KeyCode.KC_F3: LogCartographyConfigAudit(); break;
			case KeyCode.KC_F6: StartFullExport(); break;
			case KeyCode.KC_F4: StartDetailAudit(); break;
			case KeyCode.KC_F8: StartAutomaticExport(false); break;
			case KeyCode.KC_F5: StartAutomaticExport(true); break;
			case KeyCode.KC_F9: RetryAutomaticCapture(); break;
			case KeyCode.KC_F10: AbortAutomaticExport(); break;
			case KeyCode.KC_N: ConfirmCaptureAndMoveNext(); break;
			case KeyCode.KC_B: MoveToPreviousCapture(); break;
			case KeyCode.KC_F7: SetDebugVisible(!m_DebugVisible); break;
			case KeyCode.KC_P: PrintCurrentTile(); if (m_FullExportActive) PrintCaptureReady(); break;
			case KeyCode.KC_LEFT: if (!m_FullExportActive) MoveToTile(m_GridX - 1, m_GridZ); break;
			case KeyCode.KC_RIGHT: if (!m_FullExportActive) MoveToTile(m_GridX + 1, m_GridZ); break;
			case KeyCode.KC_UP: if (!m_FullExportActive) MoveToTile(m_GridX, m_GridZ + 1); break;
			case KeyCode.KC_DOWN: if (!m_FullExportActive) MoveToTile(m_GridX, m_GridZ - 1); break;
			case KeyCode.KC_R: if (!m_FullExportActive) MoveToTile(0, 0); break;
		}
	}

	protected bool IsCurrentTileStable()
	{
		if (!m_CurrentTile) return false;
		// MapWidget clamps SetMapPos at world edges. The actual center can therefore
		// differ from the requested center while the rendered bounds are stable.
		if (Absolute(m_CurrentTile.GetScale - m_ExpectedScale) > m_Config.StabilizationTolerance) return false;
		if (m_CurrentTile.WidgetPixelWidth <= 0 || m_CurrentTile.WidgetPixelHeight <= 0 || m_CurrentTile.VisibleWorldWidth <= 0 || m_CurrentTile.VisibleWorldHeight <= 0 || m_CurrentTile.MetersPerPixelX <= 0 || m_CurrentTile.MetersPerPixelZ <= 0) return false;
		if (Absolute(m_CurrentTile.MetersPerPixelX - m_CurrentTile.MetersPerPixelZ) > SQUARE_PIXEL_TOLERANCE) return false;
		return true;
	}

	protected void BeginAutomaticCapture()
	{
		if (!m_AutomaticExportActive || !m_CaptureReady || !m_CurrentTile) return;
		m_AckWaitSeconds = 0;
		m_AckFileSeen = false;
		m_AckFieldsLogged = false;
		string ackPath = m_SessionDirectory + "/capture_ack.json";
		if (FileExist(ackPath))
		{
			DeleteFile(ackPath);
			Print(LOG_PREFIX + "[AutoCapture] cleared stale ACK before request=" + m_AutoRequestId);
		}
		if (!WriteCaptureRequest()) return;
		m_AutoState = AUTO_STATE_WAITING_FOR_ACK;
		Print(LOG_PREFIX + string.Format("[AutoCapture] state=WAITING_FOR_ACK request=%1 tile=%2/%3 requestPath=%4", m_AutoRequestId, m_CaptureSequenceIndex + 1, m_CaptureSequence.Count(), m_SessionDirectory + "/capture_request.json"));
		Print(LOG_PREFIX + "[AutoCapture] ackPath=" + m_SessionDirectory + "/capture_ack.json");
	}

	protected void TickAutomaticAck(float timeslice)
	{
		m_AckWaitSeconds += timeslice;
		string ackPath = m_SessionDirectory + "/capture_ack.json";
		bool ackExists = FileExist(ackPath);
		if (!ackExists)
		{
			if (m_AckWaitSeconds >= m_Config.CaptureTimeoutSeconds)
			{
				m_AutoState = AUTO_STATE_CAPTURE_FAILED;
				Print(LOG_PREFIX + "CAPTURE_TIMEOUT. Tile was not advanced; press F9 to retry or F10 to abort.");
			}
			return;
		}
		if (!m_AckFileSeen)
		{
			m_AckFileSeen = true;
			Print(LOG_PREFIX + "[AutoCapture] FileExist=true");
			Print(LOG_PREFIX + "[AutoCapture] LoadFile begin");
		}
		DayZMapCaptureAck ack = new DayZMapCaptureAck();
		string ackLoadError;
		if (!JsonFileLoader<DayZMapCaptureAck>.LoadFile(ackPath, ack, ackLoadError))
		{
			Print(LOG_PREFIX + "[AutoCapture] LoadFile error=" + ackLoadError);
			m_AutoState = AUTO_STATE_CAPTURE_FAILED;
			return;
		}
		NoronhaMapExporterTile slot = m_CaptureSequence.Get(m_CaptureSequenceIndex);
		if (!m_AckFieldsLogged)
		{
			m_AckFieldsLogged = true;
			Print(LOG_PREFIX + "[AutoCapture] ack.sessionId=" + ack.sessionId);
			Print(LOG_PREFIX + "[AutoCapture] expected.sessionId=" + m_SessionId);
			Print(LOG_PREFIX + string.Format("[AutoCapture] ack.requestId=%1 expected.requestId=%2", ack.requestId, m_AutoRequestId));
			Print(LOG_PREFIX + "[AutoCapture] ack.filename=" + ack.filename);
			Print(LOG_PREFIX + "[AutoCapture] expected.filename=" + slot.Filename);
			Print(LOG_PREFIX + "[AutoCapture] ack.status=" + ack.status);
		}
		if (ack.protocolVersion != 1) { Print(LOG_PREFIX + "[AutoCapture] ACK_REJECTED protocolVersion"); m_AutoState = AUTO_STATE_CAPTURE_FAILED; return; }
		if (ack.sessionId != m_SessionId) { Print(LOG_PREFIX + "[AutoCapture] ACK_REJECTED sessionId"); m_AutoState = AUTO_STATE_CAPTURE_FAILED; return; }
		if (ack.requestId != m_AutoRequestId) { Print(LOG_PREFIX + "[AutoCapture] ACK_REJECTED requestId"); m_AutoState = AUTO_STATE_CAPTURE_FAILED; return; }
		if (ack.filename != slot.Filename) { Print(LOG_PREFIX + "[AutoCapture] ACK_REJECTED filename"); m_AutoState = AUTO_STATE_CAPTURE_FAILED; return; }
		if (ack.status != "OK") { Print(LOG_PREFIX + "[AutoCapture] ACK_REJECTED status=" + ack.status + " error=" + ack.error); m_AutoState = AUTO_STATE_CAPTURE_FAILED; return; }
		if (Absolute(ack.width - m_CurrentTile.WidgetPixelWidth) > CONSISTENCY_TOLERANCE || Absolute(ack.height - m_CurrentTile.WidgetPixelHeight) > CONSISTENCY_TOLERANCE || ack.sha256 == "") { Print(LOG_PREFIX + "[AutoCapture] ACK_REJECTED dimensions_or_sha256"); m_AutoState = AUTO_STATE_CAPTURE_FAILED; return; }
		m_CurrentTile.PngWidth = ack.width;
		m_CurrentTile.PngHeight = ack.height;
		m_CurrentTile.Sha256 = ack.sha256;
		m_CurrentTile.RequestId = ack.requestId;
		Print(LOG_PREFIX + "[AutoCapture] ACK ACCEPTED request=" + ack.requestId + " filename=" + ack.filename + " sha256=" + ack.sha256);
		ConfirmCaptureAndMoveNext();
	}

	protected bool LoadConfiguration()
	{
		if (!FileExist(CONFIG_PATH))
		{
			Print(LOG_PREFIX + "ERROR: missing " + CONFIG_PATH + ". Run run-2d.ps1 so it can generate the profile configuration.");
			return false;
		}
		m_Config = new DayZMapExporterConfig();
		string configLoadError;
		if (!JsonFileLoader<DayZMapExporterConfig>.LoadFile(CONFIG_PATH, m_Config, configLoadError))
		{
			Print(LOG_PREFIX + "ERROR: could not read exporter-config.json: " + configLoadError);
			return false;
		}
		if (m_Config.WorldName == "" || m_Config.WorldMaxX <= m_Config.WorldMinX || m_Config.WorldMaxZ <= m_Config.WorldMinZ || m_Config.WorldSize <= 0 || m_Config.ExportScale <= 0 || m_Config.OverlapFraction < 0 || m_Config.OverlapFraction >= 1 || m_Config.OutputPrefix == "" || m_Config.StabilizationFrames < 1 || m_Config.CaptureTimeoutSeconds <= 0)
		{
			Print(LOG_PREFIX + "ERROR: exporter-config.json is invalid. Check world bounds, worldSize, scale, overlap, prefix, frames, and timeout.");
			return false;
		}
		return true;
	}

	protected void CalibrateGrid()
	{
		NoronhaMapExporterTile calibration = ReadTileBounds();
		if (calibration.VisibleWorldWidth <= 0 || calibration.VisibleWorldHeight <= 0)
		{
			Print(LOG_PREFIX + "ERROR: ScreenToMap returned invalid viewport dimensions. Calibration stopped.");
			return;
		}
		m_TileStepX = calibration.VisibleWorldWidth * (1.0 - m_Config.OverlapFraction);
		m_TileStepZ = calibration.VisibleWorldHeight * (1.0 - m_Config.OverlapFraction);
		m_GridColumns = CalculateTileCount(m_Config.WorldMaxX - m_Config.WorldMinX, calibration.VisibleWorldWidth, m_TileStepX);
		m_GridRows = CalculateTileCount(m_Config.WorldMaxZ - m_Config.WorldMinZ, calibration.VisibleWorldHeight, m_TileStepZ);
		m_TileZeroCenterX = CalculateFirstCenter(m_Config.WorldMinX, m_Config.WorldMaxX, calibration.VisibleWorldWidth, m_TileStepX, m_GridColumns);
		m_TileZeroCenterZ = CalculateFirstCenter(m_Config.WorldMinZ, m_Config.WorldMaxZ, calibration.VisibleWorldHeight, m_TileStepZ, m_GridRows);
		BuildCaptureSequence();
		m_IsCalibrated = true;
		MoveToTile(0, 0);
		Print(LOG_PREFIX + string.Format("Calibration complete. visible=%1 x %2 m, step=%3 x %4 m, overlap=%5%%, grid=%6 x %7 (%8 tiles).", calibration.VisibleWorldWidth, calibration.VisibleWorldHeight, m_TileStepX, m_TileStepZ, m_Config.OverlapFraction * 100, m_GridColumns, m_GridRows, m_CaptureSequence.Count()));
	}

	protected int CalculateTileCount(float worldSize, float visibleSize, float step)
	{
		if (visibleSize >= worldSize) return 1;
		return Math.Ceil((worldSize - visibleSize) / step) + 1;
	}

	protected float CalculateFirstCenter(float worldMin, float worldMax, float visibleSize, float step, int count)
	{
		float coverage = visibleSize + ((count - 1) * step);
		return worldMin - ((coverage - (worldMax - worldMin)) * 0.5) + (visibleSize * 0.5);
	}

	protected void BuildCaptureSequence()
	{
		m_CaptureSequence.Clear();
		int index = 0;
		for (int gridZ = m_GridRows - 1; gridZ >= 0; gridZ--)
		{
			int rowFromNorth = (m_GridRows - 1) - gridZ;
			if (rowFromNorth % 2 == 0)
			{
				for (int gridX = 0; gridX < m_GridColumns; gridX++) AddCaptureSlot(index++, gridX, gridZ);
			}
			else
			{
				for (int reverseX = m_GridColumns - 1; reverseX >= 0; reverseX--) AddCaptureSlot(index++, reverseX, gridZ);
			}
		}
	}

	protected void AddCaptureSlot(int index, int gridX, int gridZ)
	{
		NoronhaMapExporterTile slot = new NoronhaMapExporterTile();
		slot.Index = index;
		slot.GridX = gridX;
		slot.GridZ = gridZ;
		slot.Filename = GetFilename(gridX, gridZ);
		slot.TargetScale = m_Config.ExportScale;
		m_CaptureSequence.Insert(slot);
	}

	protected void BuildDetailAuditCaptureSequence()
	{
		m_CaptureSequence.Clear();
		for (int index = 0; index < m_Config.DetailAudit.Scales.Count(); index++)
		{
			NoronhaMapExporterTile slot = new NoronhaMapExporterTile();
			slot.Index = index;
			slot.GridX = index;
			slot.GridZ = 0;
			slot.TargetScale = m_Config.DetailAudit.Scales.Get(index);
			slot.Filename = GetDetailAuditFilename(slot.TargetScale);
			m_CaptureSequence.Insert(slot);
		}
	}

	protected void MoveToTile(int gridX, int gridZ)
	{
		if (!m_IsCalibrated) return;
		m_GridX = Math.Clamp(gridX, 0, m_GridColumns - 1);
		m_GridZ = Math.Clamp(gridZ, 0, m_GridRows - 1);
		m_RequestedCenter = Vector(m_TileZeroCenterX + (m_GridX * m_TileStepX), 0, m_TileZeroCenterZ + (m_GridZ * m_TileStepZ));
		m_CaptureReady = false;
		m_ExpectedScale = m_Config.ExportScale;
		m_Map.SetScale(m_Config.ExportScale);
		m_Map.SetMapPos(m_RequestedCenter);
		m_TileReadFramesRemaining = m_Config.StabilizationFrames;
	}

	protected void StartFullExport()
	{
		if (!m_IsCalibrated)
		{
			Print(LOG_PREFIX + "FULL EXPORT is unavailable while calibration is pending.");
			return;
		}
		CreateExportSession();
		m_AutomaticExportActive = false;
		m_AutoSmokeActive = false;
		m_DetailAuditActive = false;
		m_AutoState = AUTO_STATE_IDLE;
		m_FullExportActive = true;
		m_FullExportCompleted = false;
		m_ActiveGridColumns = m_GridColumns;
		m_ActiveGridRows = m_GridRows;
		m_CaptureSequenceIndex = 0;
		MoveToCurrentCaptureSlot();
		Print(LOG_PREFIX + string.Format("FULL EXPORT started: %1 tiles, serpentine north-to-south. Capture in CLEAN mode, then press N.", m_CaptureSequence.Count()));
	}

	protected void StartDetailAudit()
	{
		if (!m_IsCalibrated || !m_Config.AutoCaptureEnabled)
		{
			Print(LOG_PREFIX + "DETAIL AUDIT is unavailable until calibration completes and autoCaptureEnabled is true.");
			return;
		}
		if (!m_Config.DetailAudit || !m_Config.DetailAudit.Enabled || !m_Config.DetailAudit.Scales || m_Config.DetailAudit.Scales.Count() == 0)
		{
			Print(LOG_PREFIX + "DETAIL AUDIT requires DetailAudit.Enabled and at least one DetailAudit.Scales value in exporter-config.json.");
			return;
		}
		if (m_Config.DetailAudit.CenterX < m_Config.WorldMinX || m_Config.DetailAudit.CenterX > m_Config.WorldMaxX || m_Config.DetailAudit.CenterZ < m_Config.WorldMinZ || m_Config.DetailAudit.CenterZ > m_Config.WorldMaxZ)
		{
			Print(LOG_PREFIX + "DETAIL AUDIT center is outside configured world bounds.");
			return;
		}
		for (int i = 0; i < m_Config.DetailAudit.Scales.Count(); i++)
		{
			if (m_Config.DetailAudit.Scales.Get(i) <= 0)
			{
				Print(LOG_PREFIX + "DETAIL AUDIT scale must be positive.");
				return;
			}
		}
		CreateExportSession();
		m_AutomaticExportActive = true;
		m_AutoSmokeActive = false;
		m_DetailAuditActive = true;
		m_AutoState = AUTO_STATE_SETTLING;
		m_FullExportActive = true;
		m_FullExportCompleted = false;
		m_CaptureSequenceIndex = 0;
		m_AutoRequestId = 1;
		m_AutoCleanFramesRemaining = m_Config.StabilizationFrames;
		m_ActiveGridColumns = m_Config.DetailAudit.Scales.Count();
		m_ActiveGridRows = 1;
		SetDebugVisible(false);
		BuildDetailAuditCaptureSequence();
		MoveToCurrentCaptureSlot();
		Print(LOG_PREFIX + string.Format("DETAIL AUDIT started: center X=%1 Z=%2, %3 scales. CLEAN is forced; waiting for helper ACKs.", m_Config.DetailAudit.CenterX, m_Config.DetailAudit.CenterZ, m_CaptureSequence.Count()));
	}

	protected void StartAutomaticExport(bool smoke)
	{
		if (!m_IsCalibrated || !m_Config.AutoCaptureEnabled)
		{
			Print(LOG_PREFIX + "AUTO EXPORT is unavailable until calibration completes and autoCaptureEnabled is true in exporter-config.json.");
			return;
		}
		if (smoke && (m_GridColumns < 2 || m_GridRows < 2))
		{
			Print(LOG_PREFIX + "AUTO SMOKE requires a grid of at least 2 x 2.");
			return;
		}
		CreateExportSession();
		m_AutomaticExportActive = true;
		m_AutoSmokeActive = smoke;
		m_DetailAuditActive = false;
		m_AutoState = AUTO_STATE_SETTLING;
		m_FullExportActive = true;
		m_FullExportCompleted = false;
		m_CaptureSequenceIndex = 0;
		m_AutoRequestId = 1;
		m_AutoCleanFramesRemaining = m_Config.StabilizationFrames;
		SetDebugVisible(false);
		if (smoke)
			BuildSmokeCaptureSequence();
		else
		{
			BuildCaptureSequence();
			m_ActiveGridColumns = m_GridColumns;
			m_ActiveGridRows = m_GridRows;
		}
		MoveToCurrentCaptureSlot();
		string exportMode = "EXPORT";
		if (smoke) exportMode = "SMOKE 2x2";
		Print(LOG_PREFIX + string.Format("AUTO %1 started: %2 tiles. CLEAN is forced; waiting for helper ACKs.", exportMode, m_CaptureSequence.Count()));
		Print(LOG_PREFIX + string.Format("[AutoCapture] state=SETTLING grid=%1,%2 request=%3", m_GridX, m_GridZ, m_AutoRequestId));
	}

	protected void BuildSmokeCaptureSequence()
	{
		m_CaptureSequence.Clear();
		m_ActiveGridColumns = 2;
		m_ActiveGridRows = 2;
		int index = 0;
		for (int gridZ = 0; gridZ < 2; gridZ++)
			for (int gridX = 0; gridX < 2; gridX++) AddCaptureSlot(index++, gridX, gridZ);
	}

	protected void RetryAutomaticCapture()
	{
		if (!m_AutomaticExportActive || m_AutoState != AUTO_STATE_CAPTURE_FAILED || !m_CaptureReady)
		{
			Print(LOG_PREFIX + "F9 retries only the failed automatic tile after it is stable.");
			return;
		}
		m_AutoCleanFramesRemaining = m_Config.StabilizationFrames;
		m_AutoState = AUTO_STATE_SETTLING;
		m_TileReadFramesRemaining = 1;
		Print(LOG_PREFIX + "Retrying current automatic tile.");
	}

	protected void AbortAutomaticExport()
	{
		if (!m_AutomaticExportActive) return;
		m_AutomaticExportActive = false;
		m_FullExportActive = false;
		m_AutoState = AUTO_STATE_CAPTURE_FAILED;
		WriteManifest();
		Print(LOG_PREFIX + "AUTO EXPORT aborted. The manifest remains incomplete; manual export can be started with F6.");
	}

	protected void CreateExportSession()
	{
		int year; int month; int day; int hour; int minute; int second;
		GetYearMonthDay(year, month, day);
		GetHourMinuteSecond(hour, minute, second);
		string sessionBase = string.Format("$profile:/DayZMapExporter/map-exports/%1-%2-%3_%4-%5-%6", year, Pad2(month), Pad2(day), Pad2(hour), Pad2(minute), Pad2(second));
		m_SessionNonce++;
		m_SessionDirectory = sessionBase + "_" + Pad2(m_SessionNonce);
		while (FileExist(m_SessionDirectory + "/manifest.json"))
		{
			m_SessionNonce++;
			m_SessionDirectory = sessionBase + "_" + Pad2(m_SessionNonce);
		}
		MakeDirectory("$profile:/DayZMapExporter");
		MakeDirectory("$profile:/DayZMapExporter/map-exports");
		MakeDirectory(m_SessionDirectory);
		MakeDirectory(m_SessionDirectory + "/captures");
		MakeDirectory(m_SessionDirectory + "/output");
		MakeDirectory(m_SessionDirectory + "/logs");
		m_CapturedTiles.Clear();
		m_SessionId = string.Format("%1-%2", year.ToString() + Pad2(month) + Pad2(day) + Pad2(hour) + Pad2(minute) + Pad2(second), m_SessionNonce);
	}

	protected void ConfirmCaptureAndMoveNext()
	{
		if (!m_FullExportActive || !m_CaptureReady)
		{
			Print(LOG_PREFIX + "N requires a CAPTURE READY tile in FULL EXPORT.");
			return;
		}
		if (m_FullExportCompleted)
		{
			Print(LOG_PREFIX + "FULL EXPORT already complete.");
			return;
		}
		StoreCurrentCapture();
		m_CaptureSequenceIndex++;
		if (m_CaptureSequenceIndex >= m_CaptureSequence.Count())
		{
			m_FullExportCompleted = true;
			if (m_AutomaticExportActive) m_AutoState = AUTO_STATE_EXPORT_COMPLETE;
			WriteManifest();
			if (m_AutoState == AUTO_STATE_EXPORT_COMPLETE) m_AutomaticExportActive = false;
			if (m_DetailAuditActive)
				Print(LOG_PREFIX + "DETAIL AUDIT complete. Run detail_audit.py on the session.");
			else
				Print(LOG_PREFIX + "FULL EXPORT complete. Run stitch_map.py on the session.");
			return;
		}
		WriteManifest();
		if (m_AutomaticExportActive)
		{
			m_AutoRequestId = m_CaptureSequenceIndex + 1;
			m_AutoState = AUTO_STATE_SETTLING;
			Print(LOG_PREFIX + string.Format("[AutoCapture] advancing to grid=%1,%2 request=%3", m_CaptureSequence.Get(m_CaptureSequenceIndex).GridX, m_CaptureSequence.Get(m_CaptureSequenceIndex).GridZ, m_AutoRequestId));
		}
		MoveToCurrentCaptureSlot();
	}

	protected void MoveToPreviousCapture()
	{
		if (!m_FullExportActive) return;
		if (m_AutomaticExportActive) return;
		if (m_FullExportCompleted)
		{
			m_FullExportCompleted = false;
			m_CaptureSequenceIndex = m_CaptureSequence.Count() - 1;
		}
		else if (m_CaptureSequenceIndex > 0)
			m_CaptureSequenceIndex--;
		else
			return;
		MoveToCurrentCaptureSlot();
	}

	protected void MoveToCurrentCaptureSlot()
	{
		NoronhaMapExporterTile slot = m_CaptureSequence.Get(m_CaptureSequenceIndex);
		if (m_DetailAuditActive)
			MoveToDetailAuditSlot(slot);
		else
			MoveToTile(slot.GridX, slot.GridZ);
	}

	protected void MoveToDetailAuditSlot(NoronhaMapExporterTile slot)
	{
		m_GridX = slot.GridX;
		m_GridZ = slot.GridZ;
		m_RequestedCenter = Vector(m_Config.DetailAudit.CenterX, 0, m_Config.DetailAudit.CenterZ);
		m_CaptureReady = false;
		m_ExpectedScale = slot.TargetScale;
		m_Map.SetScale(slot.TargetScale);
		m_Map.SetMapPos(m_RequestedCenter);
		m_TileReadFramesRemaining = m_Config.StabilizationFrames;
	}

	protected void StoreCurrentCapture()
	{
		NoronhaMapExporterTile slot = m_CaptureSequence.Get(m_CaptureSequenceIndex);
		NoronhaMapExporterTile captured = CopyTile(m_CurrentTile);
		captured.Index = slot.Index;
		captured.GridX = slot.GridX;
		captured.GridZ = slot.GridZ;
		captured.Filename = slot.Filename;
		captured.TargetScale = slot.TargetScale;
		for (int i = 0; i < m_CapturedTiles.Count(); i++)
		{
			NoronhaMapExporterTile previous = m_CapturedTiles.Get(i);
			if (previous.GridX == captured.GridX && previous.GridZ == captured.GridZ)
			{
				m_CapturedTiles.Set(i, captured);
				Print(LOG_PREFIX + "Capture re-confirmed: " + captured.Filename);
				return;
			}
		}
		m_CapturedTiles.Insert(captured);
		Print(LOG_PREFIX + string.Format("Capture confirmed %1/%2: %3", captured.Index + 1, m_CaptureSequence.Count(), captured.Filename));
	}

	protected NoronhaMapExporterTile CopyTile(NoronhaMapExporterTile source)
	{
		NoronhaMapExporterTile target = new NoronhaMapExporterTile();
		target.RequestedCenter = source.RequestedCenter;
		target.GetMapPos = source.GetMapPos;
		target.GetScale = source.GetScale;
		target.WidgetPixelX = source.WidgetPixelX;
		target.WidgetPixelY = source.WidgetPixelY;
		target.WidgetPixelWidth = source.WidgetPixelWidth;
		target.WidgetPixelHeight = source.WidgetPixelHeight;
		target.Left = source.Left; target.Right = source.Right; target.Top = source.Top; target.Bottom = source.Bottom;
		target.TopLeft = source.TopLeft; target.TopRight = source.TopRight; target.BottomLeft = source.BottomLeft; target.BottomRight = source.BottomRight;
		target.VisibleWorldWidth = source.VisibleWorldWidth;
		target.VisibleWorldHeight = source.VisibleWorldHeight;
		target.MetersPerPixelX = source.MetersPerPixelX;
		target.MetersPerPixelZ = source.MetersPerPixelZ;
		target.ZAxisDirection = source.ZAxisDirection;
		target.TargetScale = source.TargetScale;
		target.PngWidth = source.PngWidth;
		target.PngHeight = source.PngHeight;
		target.Sha256 = source.Sha256;
		target.RequestId = source.RequestId;
		return target;
	}

	protected void WriteManifest()
	{
		if (m_SessionDirectory == "") return;
		string validation = ValidateCapturedTiles();
		FileHandle file = OpenFile(m_SessionDirectory + "/manifest.json", FileMode.WRITE);
		if (file == 0)
		{
			Print(LOG_PREFIX + "ERROR: could not write manifest.json.");
			return;
		}
		FPrint(file, BuildManifest(validation));
		CloseFile(file);
		Print(LOG_PREFIX + "Manifest: " + m_SessionDirectory + "/manifest.json");
	}

	protected bool WriteCaptureRequest()
	{
		NoronhaMapExporterTile slot = m_CaptureSequence.Get(m_CaptureSequenceIndex);
		string path = m_SessionDirectory + "/capture_request.json";
		FileHandle file = OpenFile(path, FileMode.WRITE);
		if (file == 0)
		{
			m_AutoState = AUTO_STATE_CAPTURE_FAILED;
			Print(LOG_PREFIX + "ERROR: could not write capture_request.json.");
			return false;
		}
		string text = "{\n";
		text += "  \"protocolVersion\": 1,\n";
		text += "  \"sessionId\": \"" + m_SessionId + "\",\n";
		text += string.Format("  \"requestId\": %1,\n  \"tileIndex\": %2,\n  \"tileCount\": %3,\n", m_AutoRequestId, slot.Index, m_CaptureSequence.Count());
		text += string.Format("  \"gridX\": %1,\n  \"gridZ\": %2,\n  \"filename\": \"%3\",\n", slot.GridX, slot.GridZ, slot.Filename);
		text += string.Format("  \"targetScale\": %1,\n", slot.TargetScale);
		text += string.Format("  \"requestedCenter\": {\"x\": %1, \"z\": %2},\n", m_CurrentTile.RequestedCenter[0], m_CurrentTile.RequestedCenter[2]);
		text += string.Format("  \"actualCenter\": {\"x\": %1, \"z\": %2},\n", m_CurrentTile.GetMapPos[0], m_CurrentTile.GetMapPos[2]);
		text += string.Format("  \"bounds\": {\"left\": %1, \"right\": %2, \"bottom\": %3, \"top\": %4},\n", m_CurrentTile.Left, m_CurrentTile.Right, m_CurrentTile.Bottom, m_CurrentTile.Top);
		text += string.Format("  \"widget\": {\"x\": %1, \"y\": %2, \"width\": %3, \"height\": %4},\n", m_CurrentTile.WidgetPixelX, m_CurrentTile.WidgetPixelY, m_CurrentTile.WidgetPixelWidth, m_CurrentTile.WidgetPixelHeight);
		text += "  \"status\": \"CAPTURE_READY\"\n}";
		FPrint(file, text);
		CloseFile(file);
		return true;
	}

	protected string BuildManifest(string validation)
	{
		string text = "{\n";
		text += "  \"version\": 2,\n  \"world\": \"" + m_Config.WorldName + "\",\n";
		text += "  \"mode\": \"" + GetExportModeName() + "\",\n";
		text += string.Format("  \"worldBounds\": {\"left\": %1, \"right\": %2, \"bottom\": %3, \"top\": %4},\n", GetManifestWorldLeft(), GetManifestWorldRight(), GetManifestWorldBottom(), GetManifestWorldTop());
		text += string.Format("  \"exportScale\": %1,\n  \"overlapFraction\": %2,\n", m_Config.ExportScale, m_Config.OverlapFraction);
		if (m_DetailAuditActive)
			text += string.Format("  \"detailAudit\": {\"centerX\": %1, \"centerZ\": %2},\n", m_Config.DetailAudit.CenterX, m_Config.DetailAudit.CenterZ);
		else
			text += "  \"detailAudit\": null,\n";
		text += string.Format("  \"grid\": {\"columns\": %1, \"rows\": %2, \"total\": %3, \"traversal\": \"serpentine north-to-south\"},\n", m_ActiveGridColumns, m_ActiveGridRows, m_CaptureSequence.Count());
		text += string.Format("  \"sessionDirectory\": \"%1\",\n  \"captureDirectory\": \"%1/captures\",\n", m_SessionDirectory);
		text += string.Format("  \"automaticCapture\": %1,\n  \"sessionId\": \"%2\",\n", BoolJson(m_AutomaticExportActive || m_AutoState == AUTO_STATE_EXPORT_COMPLETE), m_SessionId);
		text += string.Format("  \"captureComplete\": %1,\n  \"valid\": %2,\n  \"validationMessage\": \"%3\",\n", BoolJson(m_CapturedTiles.Count() == m_CaptureSequence.Count()), BoolJson(validation == "PASS"), validation);
		text += "  \"capturedCoverage\": " + GetCapturedCoverageJson() + ",\n";
		text += "  \"tiles\": [\n";
		for (int i = 0; i < m_CapturedTiles.Count(); i++)
		{
			text += BuildManifestTile(m_CapturedTiles.Get(i));
			if (i < m_CapturedTiles.Count() - 1) text += ",";
			text += "\n";
		}
		text += "  ]\n}";
		return text;
	}

	protected string GetExportModeName()
	{
		if (m_DetailAuditActive) return "detail-audit";
		if (m_AutoSmokeActive) return "smoke-2x2";
		if (m_AutomaticExportActive || m_AutoState == AUTO_STATE_EXPORT_COMPLETE) return "automatic-export";
		return "manual-export";
	}

	protected float GetManifestWorldLeft()
	{
		if (m_AutoSmokeActive && m_CapturedTiles.Count() > 0) return m_CapturedTiles.Get(0).Left;
		return m_Config.WorldMinX;
	}

	protected float GetManifestWorldRight()
	{
		if (m_AutoSmokeActive && m_CapturedTiles.Count() > 0) return m_CapturedTiles.Get(m_CapturedTiles.Count() - 1).Right;
		return m_Config.WorldMaxX;
	}

	protected float GetManifestWorldBottom()
	{
		if (m_AutoSmokeActive && m_CapturedTiles.Count() > 0) return m_CapturedTiles.Get(0).Bottom;
		return m_Config.WorldMinZ;
	}

	protected float GetManifestWorldTop()
	{
		if (m_AutoSmokeActive && m_CapturedTiles.Count() > 0) return m_CapturedTiles.Get(m_CapturedTiles.Count() - 1).Top;
		return m_Config.WorldMaxZ;
	}

	protected string GetCapturedCoverageJson()
	{
		if (m_CapturedTiles.Count() == 0) return "null";
		NoronhaMapExporterTile first = m_CapturedTiles.Get(0);
		float left = first.Left; float right = first.Right; float bottom = first.Bottom; float top = first.Top;
		for (int i = 1; i < m_CapturedTiles.Count(); i++)
		{
			NoronhaMapExporterTile tile = m_CapturedTiles.Get(i);
			left = Math.Min(left, tile.Left);
			right = Math.Max(right, tile.Right);
			bottom = Math.Min(bottom, tile.Bottom);
			top = Math.Max(top, tile.Top);
		}
		return string.Format("{\"left\": %1, \"right\": %2, \"bottom\": %3, \"top\": %4}", left, right, bottom, top);
	}

	protected string BuildManifestTile(NoronhaMapExporterTile tile)
	{
		// Keep each Format call below the engine's single-digit placeholder range.
		string text = "    {";
		text += string.Format("\"index\": %1, \"gridX\": %2, \"gridZ\": %3, \"filename\": \"%4\",", tile.Index, tile.GridX, tile.GridZ, tile.Filename);
		text += string.Format(" \"requestedCenter\": {\"x\": %1, \"z\": %2}, \"actualCenter\": {\"x\": %3, \"z\": %4},", tile.RequestedCenter[0], tile.RequestedCenter[2], tile.GetMapPos[0], tile.GetMapPos[2]);
		text += string.Format(" \"bounds\": {\"left\": %1, \"right\": %2, \"bottom\": %3, \"top\": %4},", tile.Left, tile.Right, tile.Bottom, tile.Top);
		text += string.Format(" \"corners\": {\"topLeft\": [%1, %2], \"topRight\": [%3, %4], \"bottomLeft\": [%5, %6], \"bottomRight\": [%7, %8]},", tile.TopLeft[0], tile.TopLeft[2], tile.TopRight[0], tile.TopRight[2], tile.BottomLeft[0], tile.BottomLeft[2], tile.BottomRight[0], tile.BottomRight[2]);
		text += string.Format(" \"targetScale\": %1, \"getScale\": %2, \"visibleWorldWidth\": %3, \"visibleWorldHeight\": %4,", tile.TargetScale, tile.GetScale, tile.VisibleWorldWidth, tile.VisibleWorldHeight);
		text += string.Format(" \"metersPerPixel\": {\"x\": %1, \"z\": %2}, \"widget\": {\"x\": %3, \"y\": %4, \"width\": %5, \"height\": %6},", tile.MetersPerPixelX, tile.MetersPerPixelZ, tile.WidgetPixelX, tile.WidgetPixelY, tile.WidgetPixelWidth, tile.WidgetPixelHeight);
		text += string.Format(" \"requestId\": %1, \"png\": {\"width\": %2, \"height\": %3, \"sha256\": \"%4\"},", tile.RequestId, tile.PngWidth, tile.PngHeight, tile.Sha256);
		text += " \"zAxisDirection\": \"" + tile.ZAxisDirection + "\"}";
		return text;
	}

	protected string ValidateCapturedTiles()
	{
		if (m_CapturedTiles.Count() != m_CaptureSequence.Count()) return "INCOMPLETE";
		if (m_DetailAuditActive)
		{
			for (int detailIndex = 0; detailIndex < m_CapturedTiles.Count(); detailIndex++)
			{
				NoronhaMapExporterTile detailTile = m_CapturedTiles.Get(detailIndex);
				if (Absolute(detailTile.RequestedCenter[0] - m_Config.DetailAudit.CenterX) > CONSISTENCY_TOLERANCE || Absolute(detailTile.RequestedCenter[2] - m_Config.DetailAudit.CenterZ) > CONSISTENCY_TOLERANCE) return "INVALID_AUDIT_CENTER";
				if (Absolute(detailTile.GetScale - detailTile.TargetScale) > m_Config.StabilizationTolerance) return "INVALID_AUDIT_SCALE";
				if (detailTile.RequestId != detailIndex + 1 || detailTile.PngWidth != detailTile.WidgetPixelWidth || detailTile.PngHeight != detailTile.WidgetPixelHeight || detailTile.Sha256 == "") return "INVALID_CAPTURE_METADATA";
			}
			return "PASS";
		}
		NoronhaMapExporterTile first = m_CapturedTiles.Get(0);
		float left = first.Left; float right = first.Right; float bottom = first.Bottom; float top = first.Top;
		for (int i = 0; i < m_CapturedTiles.Count(); i++)
		{
			NoronhaMapExporterTile tile = m_CapturedTiles.Get(i);
			left = Math.Min(left, tile.Left); right = Math.Max(right, tile.Right); bottom = Math.Min(bottom, tile.Bottom); top = Math.Max(top, tile.Top);
			if (Absolute(tile.GetScale - first.GetScale) > CONSISTENCY_TOLERANCE || Absolute(tile.VisibleWorldWidth - first.VisibleWorldWidth) > CONSISTENCY_TOLERANCE || Absolute(tile.VisibleWorldHeight - first.VisibleWorldHeight) > CONSISTENCY_TOLERANCE || Absolute(tile.WidgetPixelWidth - first.WidgetPixelWidth) > CONSISTENCY_TOLERANCE || Absolute(tile.WidgetPixelHeight - first.WidgetPixelHeight) > CONSISTENCY_TOLERANCE)
				return "INVALID_VIEWPORT";
		}
		if (!m_AutoSmokeActive && (left > m_Config.WorldMinX + CONSISTENCY_TOLERANCE || right < m_Config.WorldMaxX - CONSISTENCY_TOLERANCE || bottom > m_Config.WorldMinZ + CONSISTENCY_TOLERANCE || top < m_Config.WorldMaxZ - CONSISTENCY_TOLERANCE)) return "INVALID_COVERAGE";
		if (Absolute(first.MetersPerPixelX - first.MetersPerPixelZ) > SQUARE_PIXEL_TOLERANCE) return "INVALID_NON_SQUARE_PIXELS";
		return "PASS";
	}

	protected float Absolute(float value)
	{
		if (value < 0) return -value;
		return value;
	}

	protected void RefreshCurrentTile()
	{
		m_CurrentTile = ReadTileBounds();
		m_CurrentTile.GridX = m_GridX;
		m_CurrentTile.GridZ = m_GridZ;
		UpdateDebugText();
	}

	protected NoronhaMapExporterTile ReadTileBounds()
	{
		float screenX; float screenY; float screenWidth; float screenHeight;
		m_Map.GetScreenPos(screenX, screenY);
		m_Map.GetScreenSize(screenWidth, screenHeight);
		NoronhaMapExporterTile tile = new NoronhaMapExporterTile();
		tile.RequestedCenter = m_RequestedCenter;
		tile.GetMapPos = m_Map.GetMapPos();
		tile.GetScale = m_Map.GetScale();
		tile.WidgetPixelX = screenX; tile.WidgetPixelY = screenY; tile.WidgetPixelWidth = screenWidth; tile.WidgetPixelHeight = screenHeight;
		tile.TopLeft = m_Map.ScreenToMap(Vector(screenX, screenY, 0));
		tile.TopRight = m_Map.ScreenToMap(Vector(screenX + screenWidth, screenY, 0));
		tile.BottomLeft = m_Map.ScreenToMap(Vector(screenX, screenY + screenHeight, 0));
		tile.BottomRight = m_Map.ScreenToMap(Vector(screenX + screenWidth, screenY + screenHeight, 0));
		tile.Left = Math.Min(Math.Min(tile.TopLeft[0], tile.TopRight[0]), Math.Min(tile.BottomLeft[0], tile.BottomRight[0]));
		tile.Right = Math.Max(Math.Max(tile.TopLeft[0], tile.TopRight[0]), Math.Max(tile.BottomLeft[0], tile.BottomRight[0]));
		tile.Bottom = Math.Min(Math.Min(tile.TopLeft[2], tile.TopRight[2]), Math.Min(tile.BottomLeft[2], tile.BottomRight[2]));
		tile.Top = Math.Max(Math.Max(tile.TopLeft[2], tile.TopRight[2]), Math.Max(tile.BottomLeft[2], tile.BottomRight[2]));
		tile.VisibleWorldWidth = tile.Right - tile.Left;
		tile.VisibleWorldHeight = tile.Top - tile.Bottom;
		tile.MetersPerPixelX = tile.VisibleWorldWidth / tile.WidgetPixelWidth;
		tile.MetersPerPixelZ = tile.VisibleWorldHeight / tile.WidgetPixelHeight;
		tile.ZAxisDirection = GetZAxisDirection(tile);
		return tile;
	}

	protected string GetZAxisDirection(NoronhaMapExporterTile tile)
	{
		float leftDelta = tile.BottomLeft[2] - tile.TopLeft[2];
		float rightDelta = tile.BottomRight[2] - tile.TopRight[2];
		if (leftDelta > 0 && rightDelta > 0) return "Z increases from top to bottom";
		if (leftDelta < 0 && rightDelta < 0) return "Z decreases from top to bottom";
		return "Z orientation indeterminate or non-uniform";
	}

	protected void SetDebugVisible(bool visible)
	{
		m_DebugVisible = visible;
		if (m_DebugOverlay) m_DebugOverlay.Show(visible);
		UpdateDebugText();
		if (visible) Print(LOG_PREFIX + "Mode: DEBUG.");
		else Print(LOG_PREFIX + "Mode: CLEAN.");
	}

	protected void UpdateDebugText()
	{
		if (!m_DebugVisible || !m_DebugText || !m_CurrentTile) return;
		string text = "DayZ Map Exporter - DEBUG\n";
		if (m_FullExportActive)
		{
			if (m_AutomaticExportActive && m_AutoState == AUTO_STATE_WAITING_FOR_ACK) text += "AUTO EXPORT | WAITING FOR ACK\n";
			else if (m_AutomaticExportActive && m_AutoState == AUTO_STATE_CAPTURE_FAILED) text += "AUTO EXPORT | FAILED (F9 retry / F10 abort)\n";
			else if (m_CaptureReady) text += "FULL EXPORT | CAPTURE READY\n";
			else text += "FULL EXPORT | STABILIZING\n";
			text += string.Format("Tile %1 / %2 | Grid: %3,%4\n", m_CaptureSequenceIndex + 1, m_CaptureSequence.Count(), m_GridX, m_GridZ);
			if (m_CaptureSequenceIndex >= 0 && m_CaptureSequenceIndex < m_CaptureSequence.Count()) text += "Expected: " + m_CaptureSequence.Get(m_CaptureSequenceIndex).Filename + "\n";
		}
		text += string.Format("Requested: X=%1 Z=%2\nActual: X=%3 Z=%4 | Scale=%5\n", m_CurrentTile.RequestedCenter[0], m_CurrentTile.RequestedCenter[2], m_CurrentTile.GetMapPos[0], m_CurrentTile.GetMapPos[2], m_CurrentTile.GetScale);
		text += string.Format("TL X=%1 Z=%2 | BR X=%3 Z=%4\n", m_CurrentTile.TopLeft[0], m_CurrentTile.TopLeft[2], m_CurrentTile.BottomRight[0], m_CurrentTile.BottomRight[2]);
		text += string.Format("Widget %1x%2 | World %3x%4\nMPP X/Z %5 / %6\n%7", m_CurrentTile.WidgetPixelWidth, m_CurrentTile.WidgetPixelHeight, m_CurrentTile.VisibleWorldWidth, m_CurrentTile.VisibleWorldHeight, m_CurrentTile.MetersPerPixelX, m_CurrentTile.MetersPerPixelZ, m_CurrentTile.ZAxisDirection);
		m_DebugText.SetText(text);
	}

	protected void PrintCaptureReady()
	{
		if (!m_FullExportActive || m_CaptureSequenceIndex < 0 || m_CaptureSequenceIndex >= m_CaptureSequence.Count()) return;
		NoronhaMapExporterTile slot = m_CaptureSequence.Get(m_CaptureSequenceIndex);
		Print(LOG_PREFIX + string.Format("CAPTURE READY | Tile %1 / %2 | Grid: %3,%4 | Expected filename: %5", slot.Index + 1, m_CaptureSequence.Count(), slot.GridX, slot.GridZ, slot.Filename));
	}

	protected void PrintCurrentTile()
	{
		if (m_TileReadFramesRemaining > 0 || !m_CurrentTile) return;
		Print(LOG_PREFIX + string.Format("Tile: %1,%2", m_CurrentTile.GridX, m_CurrentTile.GridZ));
		Print(LOG_PREFIX + string.Format("RequestedCenter: X=%1 Z=%2", m_CurrentTile.RequestedCenter[0], m_CurrentTile.RequestedCenter[2]));
		Print(LOG_PREFIX + string.Format("GetMapPos: X=%1 Z=%2", m_CurrentTile.GetMapPos[0], m_CurrentTile.GetMapPos[2]));
		Print(LOG_PREFIX + string.Format("GetScale: %1", m_CurrentTile.GetScale));
		Print(LOG_PREFIX + string.Format("TL world: X=%1 Z=%2 | TR world: X=%3 Z=%4", m_CurrentTile.TopLeft[0], m_CurrentTile.TopLeft[2], m_CurrentTile.TopRight[0], m_CurrentTile.TopRight[2]));
		Print(LOG_PREFIX + string.Format("BL world: X=%1 Z=%2 | BR world: X=%3 Z=%4", m_CurrentTile.BottomLeft[0], m_CurrentTile.BottomLeft[2], m_CurrentTile.BottomRight[0], m_CurrentTile.BottomRight[2]));
		Print(LOG_PREFIX + string.Format("Widget pixel X/Y: %1 / %2 | width/height: %3 / %4", m_CurrentTile.WidgetPixelX, m_CurrentTile.WidgetPixelY, m_CurrentTile.WidgetPixelWidth, m_CurrentTile.WidgetPixelHeight));
		Print(LOG_PREFIX + string.Format("VisibleWorldWidth/Height: %1 / %2 | MetersPerPixel X/Z: %3 / %4", m_CurrentTile.VisibleWorldWidth, m_CurrentTile.VisibleWorldHeight, m_CurrentTile.MetersPerPixelX, m_CurrentTile.MetersPerPixelZ));
		Print(LOG_PREFIX + "Z orientation: " + m_CurrentTile.ZAxisDirection);
		Print(LOG_PREFIX + string.Format("Bounds: left=%1 right=%2 bottom=%3 top=%4", m_CurrentTile.Left, m_CurrentTile.Right, m_CurrentTile.Bottom, m_CurrentTile.Top));
	}

	protected void CheckRepeatability()
	{
		for (int i = 0; i < m_VisitedTiles.Count(); i++)
		{
			NoronhaMapExporterTile previous = m_VisitedTiles.Get(i);
			if (previous.GridX == m_CurrentTile.GridX && previous.GridZ == m_CurrentTile.GridZ)
			{
				Print(LOG_PREFIX + string.Format("Repeatability tile %1,%2 | dLeft=%3 dRight=%4 dBottom=%5 dTop=%6", m_CurrentTile.GridX, m_CurrentTile.GridZ, m_CurrentTile.Left - previous.Left, m_CurrentTile.Right - previous.Right, m_CurrentTile.Bottom - previous.Bottom, m_CurrentTile.Top - previous.Top));
				m_VisitedTiles.Set(i, CopyTile(m_CurrentTile));
				return;
			}
		}
		m_VisitedTiles.Insert(CopyTile(m_CurrentTile));
	}

	protected string GetFilename(int gridX, int gridZ)
	{
		return string.Format("%1_x%2_z%3.png", m_Config.OutputPrefix, Pad2(gridX), Pad2(gridZ));
	}

	protected string GetDetailAuditFilename(float scale)
	{
		int scaleHundredths = Math.Round(scale * 100);
		return "detail_scale_" + Pad3(scaleHundredths) + ".png";
	}

	protected string Pad2(int value)
	{
		if (value < 10) return "0" + value.ToString();
		return value.ToString();
	}

	protected string Pad3(int value)
	{
		if (value < 10) return "00" + value.ToString();
		if (value < 100) return "0" + value.ToString();
		return value.ToString();
	}

	protected string BoolJson(bool value)
	{
		if (value) return "true";
		return "false";
	}

	// This is an audit-only diagnostic. DayZ keeps MapDefaults in its runtime
	// configuration, so the actual class tree must be observed in the running
	// client before an export-only override can be considered safe.
	protected void LogCartographyConfigAudit()
	{
		Print(LOG_PREFIX + "CARTOGRAPHY_CONFIG_AUDIT BEGIN");
		LogConfigClass("CfgLocationTypes", 64);
		LogConfigClass("CfgLocationTypes Name", 0);
		LogConfigClass("CfgLocationTypes NameIcon", 0);
		LogConfigClass("CfgLocationTypes Capital", 0);
		LogConfigClass("CfgLocationTypes City", 0);
		LogConfigClass("CfgLocationTypes Village", 0);
		LogConfigClass("CfgLocationTypes Local", 0);
		LogConfigClass("CfgLocationTypes Marine", 0);
		LogConfigClass("CfgLocationTypes Ruin", 0);
		LogConfigClass("CfgLocationTypes Camp", 0);
		LogConfigClass("CfgLocationTypes Hill", 0);
		LogConfigClass("CfgLocationTypes ViewPoint", 0);
		LogConfigClass("CfgLocationTypes RockArea", 0);
		LogConfigClass("CfgLocationTypes RailroadStation", 0);
		LogConfigClass("CfgLocationTypes IndustrialSite", 0);
		LogConfigClass("CfgLocationTypes LocalOffice", 0);
		LogConfigClass("CfgLocationTypes BorderCrossing", 0);
		LogConfigClass("CfgLocationTypes VegetationBroadleaf", 0);
		LogConfigClass("CfgLocationTypes VegetationFir", 0);
		LogConfigClass("CfgLocationTypes VegetationPalm", 0);
		LogConfigClass("CfgLocationTypes VegetationVineyard", 0);
		LogConfigClass("MapDefaults", 96);
		LogConfigClass("RscMapControl", 96);

		array<string> mapObjectCandidates = new array<string>();
		mapObjectCandidates.Insert("Fuelstation");
		mapObjectCandidates.Insert("Lighthouse");
		mapObjectCandidates.Insert("Stack");
		mapObjectCandidates.Insert("Transmitter");
		mapObjectCandidates.Insert("Watertower");
		mapObjectCandidates.Insert("Shipwreck");
		mapObjectCandidates.Insert("Monument");
		mapObjectCandidates.Insert("BusStop");
		mapObjectCandidates.Insert("Hospital");
		mapObjectCandidates.Insert("Church");
		mapObjectCandidates.Insert("Chapel");
		mapObjectCandidates.Insert("Cross");
		mapObjectCandidates.Insert("Fortress");
		mapObjectCandidates.Insert("Fountain");
		mapObjectCandidates.Insert("Tourism");
		mapObjectCandidates.Insert("ViewTower");
		for (int candidateIndex = 0; candidateIndex < mapObjectCandidates.Count(); candidateIndex++)
		{
			string candidate = mapObjectCandidates.Get(candidateIndex);
			LogConfigClass("MapDefaults " + candidate, 0);
			LogConfigClass("RscMapControl " + candidate, 0);
		}
		Print(LOG_PREFIX + "CARTOGRAPHY_CONFIG_AUDIT END");
	}

	protected void LogConfigClass(string path, int maxChildren)
	{
		bool exists = g_Game.ConfigIsExisting(path);
		Print(LOG_PREFIX + "CONFIG path=" + path + " exists=" + BoolJson(exists));
		if (!exists) return;

		string baseName;
		if (g_Game.ConfigGetBaseName(path, baseName)) Print(LOG_PREFIX + "CONFIG base path=" + path + " value=" + baseName);
		int childCount = g_Game.ConfigGetChildrenCount(path);
		Print(LOG_PREFIX + "CONFIG children path=" + path + " count=" + childCount);
		int childLimit = Math.Min(childCount, maxChildren);
		for (int childIndex = 0; childIndex < childLimit; childIndex++)
		{
			string childName;
			if (g_Game.ConfigGetChildName(path, childIndex, childName)) Print(LOG_PREFIX + "CONFIG child path=" + path + " name=" + childName);
		}

		string drawStyle;
		if (g_Game.ConfigGetText(path + " drawStyle", drawStyle)) Print(LOG_PREFIX + "CONFIG drawStyle path=" + path + " value=" + drawStyle);
		string icon;
		if (g_Game.ConfigGetText(path + " icon", icon)) Print(LOG_PREFIX + "CONFIG icon path=" + path + " value=" + icon);
		string texture;
		if (g_Game.ConfigGetText(path + " texture", texture)) Print(LOG_PREFIX + "CONFIG texture path=" + path + " value=" + texture);
		int sizeType = g_Game.ConfigGetType(path + " size");
		int textSizeType = g_Game.ConfigGetType(path + " textSize");
		int importanceType = g_Game.ConfigGetType(path + " importance");
		if (sizeType != 0) Print(LOG_PREFIX + "CONFIG size path=" + path + " value=" + g_Game.ConfigGetFloat(path + " size"));
		if (textSizeType != 0) Print(LOG_PREFIX + "CONFIG textSize path=" + path + " value=" + g_Game.ConfigGetFloat(path + " textSize"));
		if (importanceType != 0) Print(LOG_PREFIX + "CONFIG importance path=" + path + " value=" + g_Game.ConfigGetFloat(path + " importance"));
	}

	protected void ShowHud(bool visible)
	{
		Hud hud = g_Game.GetMission().GetHud();
		if (hud)
		{
			hud.ShowHudUI(visible);
			hud.ShowQuickbarUI(visible);
		}
	}
};
