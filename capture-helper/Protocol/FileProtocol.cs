using System.Security.Cryptography;
using System.Text.Json;

namespace DayZMapCapture.Protocol;

public static class FileProtocol
{
    public const string RequestFileName = "capture_request.json";
    public const string AckFileName = "capture_ack.json";
    private static readonly JsonSerializerOptions JsonOptions = new() { WriteIndented = true };

    public static bool TryReadRequest(string path, out CaptureRequest? request, out string error)
    {
        request = null;
        error = "";
        try
        {
            request = JsonSerializer.Deserialize<CaptureRequest>(File.ReadAllText(path), JsonOptions);
            if (request is null) { error = "EMPTY_REQUEST"; return false; }
            return ValidateRequest(request, out error);
        }
        catch (JsonException) { error = "MALFORMED_REQUEST"; return false; }
        catch (IOException) { error = "REQUEST_NOT_READY"; return false; }
    }

    public static bool ValidateRequest(CaptureRequest request, out string error)
    {
        error = "";
        if (request.ProtocolVersion != 1 || request.SessionId.Length == 0 || request.RequestId < 1 || request.TileIndex < 0 || request.TileCount < 1 || request.TileIndex >= request.TileCount || request.Status != "CAPTURE_READY") { error = "INVALID_REQUEST"; return false; }
        if (!IsSafeFileName(request.Filename)) { error = "UNSAFE_FILENAME"; return false; }
        if (!request.Widget.TryGetPixelRectangle(out _)) { error = "INVALID_WIDGET"; return false; }
        return true;
    }

    public static bool IsSafeFileName(string filename) =>
        filename.EndsWith(".png", StringComparison.OrdinalIgnoreCase) &&
        !Path.IsPathRooted(filename) &&
        Path.GetFileName(filename) == filename &&
        !filename.Contains("..", StringComparison.Ordinal);

    public static void WriteAckAtomically(string sessionDirectory, CaptureAck ack)
    {
        var destination = Path.Combine(sessionDirectory, AckFileName);
        WriteJsonAtomically(destination, ack);
    }

    public static void WriteReceiptAtomically(string sessionDirectory, CaptureAck ack)
    {
        var directory = Path.Combine(sessionDirectory, ".capture-receipts");
        Directory.CreateDirectory(directory);
        WriteJsonAtomically(Path.Combine(directory, ack.RequestId + ".json"), ack);
    }

    public static bool TryReadReceipt(string sessionDirectory, CaptureRequest request, out CaptureAck? ack)
    {
        ack = null;
        var path = Path.Combine(sessionDirectory, ".capture-receipts", request.RequestId + ".json");
        if (!File.Exists(path)) return false;
        try
        {
            ack = JsonSerializer.Deserialize<CaptureAck>(File.ReadAllText(path), JsonOptions);
            return ack is not null && ack.SessionId == request.SessionId && ack.RequestId == request.RequestId && ack.Filename == request.Filename;
        }
        catch (JsonException) { return false; }
        catch (IOException) { return false; }
    }

    private static void WriteJsonAtomically(string destination, CaptureAck ack)
    {
        var temporary = destination + ".tmp";
        File.WriteAllText(temporary, JsonSerializer.Serialize(ack, JsonOptions));
        File.Move(temporary, destination, true);
    }

    public static string CalculateSha256(string path)
    {
        using var stream = File.OpenRead(path);
        return Convert.ToHexString(SHA256.HashData(stream)).ToLowerInvariant();
    }
}
