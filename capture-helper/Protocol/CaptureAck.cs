using System.Text.Json.Serialization;

namespace DayZMapCapture.Protocol;

public sealed class CaptureAck
{
    [JsonPropertyName("protocolVersion")] public int ProtocolVersion { get; init; } = 1;
    [JsonPropertyName("sessionId")] public string SessionId { get; init; } = "";
    [JsonPropertyName("requestId")] public int RequestId { get; init; }
    [JsonPropertyName("filename")] public string Filename { get; init; } = "";
    [JsonPropertyName("width")] public int Width { get; init; }
    [JsonPropertyName("height")] public int Height { get; init; }
    [JsonPropertyName("sha256")] public string Sha256 { get; init; } = "";
    [JsonPropertyName("status")] public string Status { get; init; } = "";
    [JsonPropertyName("error")] public string? Error { get; init; }
}
