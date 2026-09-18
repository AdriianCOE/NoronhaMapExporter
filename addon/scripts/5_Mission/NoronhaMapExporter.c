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
};

class NoronhaMapExporter
{
	protected const string LAYOUT_PATH = "NoronhaMapExporter/gui/layouts/noronha_map_exporter.layout";
	protected const string LOG_PREFIX = "[NoronhaMapExporter] ";
	protected const float EXPORT_SCALE = 0.33;
	protected const float TILE_OVERLAP_FRACTION = 0.10;
	protected const float WORLD_MIN_X = 0.0;
	protected const float WORLD_MAX_X = 10240.0;
	protected const float WORLD_MIN_Z = 0.0;
	protected const float WORLD_MAX_Z = 10240.0;
	protected const int CALIBRATION_FRAME_DELAY = 2;
	protected const float CONSISTENCY_TOLERANCE = 0.01;
	protected const float SQUARE_PIXEL_TOLERANCE = 0.001;

	protected ref Widget m_Root;
	protected ref MapWidget m_Map;
	protected ref Widget m_DebugOverlay;
	protected ref TextWidget m_DebugText;
	protected ref NoronhaMapExporterTile m_CurrentTile;
	protected ref array<ref NoronhaMapExporterTile> m_VisitedTiles;
	protected ref array<ref NoronhaMapExporterTile> m_CapturedTiles;
	protected ref array<ref NoronhaMapExporterTile> m_CaptureSequence;
	protected vector m_RequestedCenter;
	protected bool m_IsOpen;
	protected bool m_DebugVisible;
	protected bool m_IsCalibrated;
	protected bool m_FullExportActive;
	protected bool m_FullExportCompleted;
	protected bool m_CaptureReady;
	protected int m_CalibrationFramesRemaining;
	protected int m_TileReadFramesRemaining;
	protected int m_GridX;
	protected int m_GridZ;
	protected int m_GridColumns;
	protected int m_GridRows;
	protected int m_CaptureSequenceIndex;
	protected int m_SessionNonce;
	protected float m_TileStepX;
	protected float m_TileStepZ;
	protected float m_TileZeroCenterX;
	protected float m_TileZeroCenterZ;
	protected string m_SessionDirectory;

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
		m_GridX = 0;
		m_GridZ = 0;
		m_GridColumns = 0;
		m_GridRows = 0;
		m_CaptureSequenceIndex = -1;
		m_VisitedTiles.Clear();
		m_CapturedTiles.Clear();
		m_CaptureSequence.Clear();
		m_CalibrationFramesRemaining = CALIBRATION_FRAME_DELAY;
		m_RequestedCenter = Vector(5120, 0, 5120);
		m_Root.Update();
		m_Map.ClearUserMarks();
		m_Map.SetScale(EXPORT_SCALE);
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
		if (m_TileReadFramesRemaining > 0)
		{
			m_TileReadFramesRemaining--;
			if (m_TileReadFramesRemaining == 0)
			{
				RefreshCurrentTile();
				PrintCurrentTile();
				CheckRepeatability();
				m_CaptureReady = true;
				if (m_FullExportActive) PrintCaptureReady();
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
			case KeyCode.KC_F6: StartFullExport(); break;
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

	protected void CalibrateGrid()
	{
		NoronhaMapExporterTile calibration = ReadTileBounds();
		if (calibration.VisibleWorldWidth <= 0 || calibration.VisibleWorldHeight <= 0)
		{
			Print(LOG_PREFIX + "ERROR: ScreenToMap returned invalid viewport dimensions. Calibration stopped.");
			return;
		}
		m_TileStepX = calibration.VisibleWorldWidth * (1.0 - TILE_OVERLAP_FRACTION);
		m_TileStepZ = calibration.VisibleWorldHeight * (1.0 - TILE_OVERLAP_FRACTION);
		m_GridColumns = CalculateTileCount(WORLD_MAX_X - WORLD_MIN_X, calibration.VisibleWorldWidth, m_TileStepX);
		m_GridRows = CalculateTileCount(WORLD_MAX_Z - WORLD_MIN_Z, calibration.VisibleWorldHeight, m_TileStepZ);
		m_TileZeroCenterX = CalculateFirstCenter(WORLD_MIN_X, WORLD_MAX_X, calibration.VisibleWorldWidth, m_TileStepX, m_GridColumns);
		m_TileZeroCenterZ = CalculateFirstCenter(WORLD_MIN_Z, WORLD_MAX_Z, calibration.VisibleWorldHeight, m_TileStepZ, m_GridRows);
		BuildCaptureSequence();
		m_IsCalibrated = true;
		MoveToTile(0, 0);
		Print(LOG_PREFIX + string.Format("Calibration complete. visible=%1 x %2 m, step=%3 x %4 m, overlap=%5%%, grid=%6 x %7 (%8 tiles).", calibration.VisibleWorldWidth, calibration.VisibleWorldHeight, m_TileStepX, m_TileStepZ, TILE_OVERLAP_FRACTION * 100, m_GridColumns, m_GridRows, m_CaptureSequence.Count()));
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
		m_CaptureSequence.Insert(slot);
	}

	protected void MoveToTile(int gridX, int gridZ)
	{
		if (!m_IsCalibrated) return;
		m_GridX = Math.Clamp(gridX, 0, m_GridColumns - 1);
		m_GridZ = Math.Clamp(gridZ, 0, m_GridRows - 1);
		m_RequestedCenter = Vector(m_TileZeroCenterX + (m_GridX * m_TileStepX), 0, m_TileZeroCenterZ + (m_GridZ * m_TileStepZ));
		m_CaptureReady = false;
		m_Map.SetScale(EXPORT_SCALE);
		m_Map.SetMapPos(m_RequestedCenter);
		m_TileReadFramesRemaining = CALIBRATION_FRAME_DELAY;
	}

	protected void StartFullExport()
	{
		if (!m_IsCalibrated)
		{
			Print(LOG_PREFIX + "FULL EXPORT is unavailable while calibration is pending.");
			return;
		}
		CreateExportSession();
		m_FullExportActive = true;
		m_FullExportCompleted = false;
		m_CaptureSequenceIndex = 0;
		MoveToCurrentCaptureSlot();
		Print(LOG_PREFIX + string.Format("FULL EXPORT started: %1 tiles, serpentine north-to-south. Capture in CLEAN mode, then press N.", m_CaptureSequence.Count()));
	}

	protected void CreateExportSession()
	{
		int year; int month; int day; int hour; int minute; int second;
		GetYearMonthDay(year, month, day);
		GetHourMinuteSecond(hour, minute, second);
		string sessionBase = string.Format("$profile:/NoronhaMapExporter/map-exports/%1-%2-%3_%4-%5-%6", year, Pad2(month), Pad2(day), Pad2(hour), Pad2(minute), Pad2(second));
		m_SessionNonce++;
		m_SessionDirectory = sessionBase + "_" + Pad2(m_SessionNonce);
		while (FileExist(m_SessionDirectory + "/manifest.json"))
		{
			m_SessionNonce++;
			m_SessionDirectory = sessionBase + "_" + Pad2(m_SessionNonce);
		}
		MakeDirectory("$profile:/NoronhaMapExporter");
		MakeDirectory("$profile:/NoronhaMapExporter/map-exports");
		MakeDirectory(m_SessionDirectory);
		MakeDirectory(m_SessionDirectory + "/captures");
		MakeDirectory(m_SessionDirectory + "/output");
		MakeDirectory(m_SessionDirectory + "/logs");
		m_CapturedTiles.Clear();
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
			WriteManifest();
			Print(LOG_PREFIX + "FULL EXPORT complete. Copy the named screenshots into captures and run stitch_map.py.");
			return;
		}
		WriteManifest();
		MoveToCurrentCaptureSlot();
	}

	protected void MoveToPreviousCapture()
	{
		if (!m_FullExportActive) return;
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
		MoveToTile(slot.GridX, slot.GridZ);
	}

	protected void StoreCurrentCapture()
	{
		NoronhaMapExporterTile slot = m_CaptureSequence.Get(m_CaptureSequenceIndex);
		NoronhaMapExporterTile captured = CopyTile(m_CurrentTile);
		captured.Index = slot.Index;
		captured.GridX = slot.GridX;
		captured.GridZ = slot.GridZ;
		captured.Filename = slot.Filename;
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

	protected string BuildManifest(string validation)
	{
		string text = "{\n";
		text += "  \"version\": 1,\n  \"world\": \"Noronha\",\n";
		text += string.Format("  \"worldBounds\": {\"left\": %1, \"right\": %2, \"bottom\": %3, \"top\": %4},\n", WORLD_MIN_X, WORLD_MAX_X, WORLD_MIN_Z, WORLD_MAX_Z);
		text += string.Format("  \"exportScale\": %1,\n  \"overlapFraction\": %2,\n", EXPORT_SCALE, TILE_OVERLAP_FRACTION);
		text += string.Format("  \"grid\": {\"columns\": %1, \"rows\": %2, \"total\": %3, \"traversal\": \"serpentine north-to-south\"},\n", m_GridColumns, m_GridRows, m_CaptureSequence.Count());
		text += string.Format("  \"sessionDirectory\": \"%1\",\n  \"captureDirectory\": \"%1/captures\",\n", m_SessionDirectory);
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
		text += string.Format(" \"getScale\": %1, \"visibleWorldWidth\": %2, \"visibleWorldHeight\": %3,", tile.GetScale, tile.VisibleWorldWidth, tile.VisibleWorldHeight);
		text += string.Format(" \"metersPerPixel\": {\"x\": %1, \"z\": %2}, \"widget\": {\"x\": %3, \"y\": %4, \"width\": %5, \"height\": %6},", tile.MetersPerPixelX, tile.MetersPerPixelZ, tile.WidgetPixelX, tile.WidgetPixelY, tile.WidgetPixelWidth, tile.WidgetPixelHeight);
		text += " \"zAxisDirection\": \"" + tile.ZAxisDirection + "\"}";
		return text;
	}

	protected string ValidateCapturedTiles()
	{
		if (m_CapturedTiles.Count() != m_CaptureSequence.Count()) return "INCOMPLETE";
		NoronhaMapExporterTile first = m_CapturedTiles.Get(0);
		float left = first.Left; float right = first.Right; float bottom = first.Bottom; float top = first.Top;
		for (int i = 0; i < m_CapturedTiles.Count(); i++)
		{
			NoronhaMapExporterTile tile = m_CapturedTiles.Get(i);
			left = Math.Min(left, tile.Left); right = Math.Max(right, tile.Right); bottom = Math.Min(bottom, tile.Bottom); top = Math.Max(top, tile.Top);
			if (Absolute(tile.GetScale - first.GetScale) > CONSISTENCY_TOLERANCE || Absolute(tile.VisibleWorldWidth - first.VisibleWorldWidth) > CONSISTENCY_TOLERANCE || Absolute(tile.VisibleWorldHeight - first.VisibleWorldHeight) > CONSISTENCY_TOLERANCE || Absolute(tile.WidgetPixelWidth - first.WidgetPixelWidth) > CONSISTENCY_TOLERANCE || Absolute(tile.WidgetPixelHeight - first.WidgetPixelHeight) > CONSISTENCY_TOLERANCE)
				return "INVALID_VIEWPORT";
		}
		if (left > WORLD_MIN_X + CONSISTENCY_TOLERANCE || right < WORLD_MAX_X - CONSISTENCY_TOLERANCE || bottom > WORLD_MIN_Z + CONSISTENCY_TOLERANCE || top < WORLD_MAX_Z - CONSISTENCY_TOLERANCE) return "INVALID_COVERAGE";
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
		string text = "Noronha Map Exporter - DEBUG\n";
		if (m_FullExportActive)
		{
			if (m_CaptureReady) text += "FULL EXPORT | CAPTURE READY\n";
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
		return string.Format("noronha_x%1_z%2.png", Pad2(gridX), Pad2(gridZ));
	}

	protected string Pad2(int value)
	{
		if (value < 10) return "0" + value.ToString();
		return value.ToString();
	}

	protected string BoolJson(bool value)
	{
		if (value) return "true";
		return "false";
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
