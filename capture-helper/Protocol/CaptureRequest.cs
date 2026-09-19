using System.Text.Json.Serialization;

namespace DayZMapCapture.Protocol;

public sealed class CaptureRequest
{
    [JsonPropertyName("protocolVersion")] public int ProtocolVersion { get; init; }
    [JsonPropertyName("sessionId")] public string SessionId { get; init; } = "";
    [JsonPropertyName("requestId")] public int RequestId { get; init; }
    [JsonPropertyName("tileIndex")] public int TileIndex { get; init; }
    [JsonPropertyName("tileCount")] public int TileCount { get; init; }
    [JsonPropertyName("gridX")] public int GridX { get; init; }
    [JsonPropertyName("gridZ")] public int GridZ { get; init; }
    [JsonPropertyName("filename")] public string Filename { get; init; } = "";
    [JsonPropertyName("widget")] public CaptureWidget Widget { get; init; } = new();
    [JsonPropertyName("status")] public string Status { get; init; } = "";
}

public sealed class CaptureWidget
{
    [JsonPropertyName("x")] public float X { get; init; }
    [JsonPropertyName("y")] public float Y { get; init; }
    [JsonPropertyName("width")] public float Width { get; init; }
    [JsonPropertyName("height")] public float Height { get; init; }

    // DayZ MapWidget coordinates are floating point. A widget aligned to the
    // client edge can report a small negative subpixel origin (for example
    // -0.5533). Snap only that subpixel edge artifact to zero; a real negative
    // offset remains invalid so the helper cannot capture desktop pixels.
    public bool TryGetPixelRectangle(out PixelRectangle rectangle)
    {
        rectangle = default;
        if (!float.IsFinite(X) || !float.IsFinite(Y) || !float.IsFinite(Width) || !float.IsFinite(Height)) return false;
        if (X <= -1 || Y <= -1 || Width <= 0 || Height <= 0) return false;

        var x = (int)MathF.Round(MathF.Max(0, X));
        var y = (int)MathF.Round(MathF.Max(0, Y));
        var width = (int)MathF.Round(Width);
        var height = (int)MathF.Round(Height);
        if (width < 1 || height < 1) return false;

        rectangle = new PixelRectangle(x, y, width, height);
        return true;
    }
}

public readonly record struct PixelRectangle(int X, int Y, int Width, int Height);
