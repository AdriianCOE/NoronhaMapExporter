using System.Text.Json;
using DayZMapCapture.Capture;
using DayZMapCapture.Protocol;

return await ProgramEntry.RunAsync(args);

internal static class ProgramEntry
{
    public static async Task<int> RunAsync(string[] args)
    {
        if (args.SequenceEqual(["--self-test"])) return RunSelfTests();
        if (args.Length != 2 || args[0] != "--sessions-root")
        {
            Console.Error.WriteLine("Usage: DayZMapCapture --sessions-root <profile\\DayZMapExporter\\map-exports> | --self-test");
            return 2;
        }
        var sessionsRoot = Path.GetFullPath(args[1]);
        Console.WriteLine($"Watching {sessionsRoot}. Keep the DayZ window visible, unminimized, and unobstructed.");
        var service = new CaptureService();
        using var cancellation = new CancellationTokenSource();
        Console.CancelKeyPress += (_, eventArgs) => { eventArgs.Cancel = true; cancellation.Cancel(); };
        try
        {
            while (!cancellation.Token.IsCancellationRequested)
            {
                if (Directory.Exists(sessionsRoot))
                    foreach (var session in Directory.EnumerateDirectories(sessionsRoot)) service.ProcessSession(session);
                await Task.Delay(200, cancellation.Token);
            }
        }
        catch (OperationCanceledException) { }
        return 0;
    }

    private static int RunSelfTests()
    {
        var request = new CaptureRequest { ProtocolVersion = 1, SessionId = "session", RequestId = 1, TileIndex = 0, TileCount = 4, Filename = "map_x00_z00.png", Status = "CAPTURE_READY", Widget = new CaptureWidget { Width = 1920, Height = 1080 } };
        Assert(FileProtocol.ValidateRequest(request, out _), "valid request");
        var unsafeRequest = new CaptureRequest { ProtocolVersion = 1, SessionId = "session", RequestId = 1, TileIndex = 0, TileCount = 4, Filename = "..\\escape.png", Status = "CAPTURE_READY", Widget = request.Widget };
        var invalidStatusRequest = new CaptureRequest { ProtocolVersion = 1, SessionId = "session", RequestId = 1, TileIndex = 0, TileCount = 4, Filename = request.Filename, Status = "MOVING", Widget = request.Widget };
        Assert(!FileProtocol.ValidateRequest(unsafeRequest, out var safetyError) && safetyError == "UNSAFE_FILENAME", "filename safety");
        Assert(!FileProtocol.ValidateRequest(invalidStatusRequest, out _), "invalid request status");
        var ack = new CaptureAck { SessionId = request.SessionId, RequestId = request.RequestId, Filename = request.Filename, Width = 1920, Height = 1080, Sha256 = "abc", Status = "OK" };
        var serialized = JsonSerializer.Serialize(ack);
        Assert(JsonSerializer.Deserialize<CaptureAck>(serialized)?.Status == "OK", "ACK serialization");
        var file = Path.GetTempFileName();
        try { File.WriteAllText(file, "hash"); Assert(FileProtocol.CalculateSha256(file).Length == 64, "SHA-256"); }
        finally { File.Delete(file); }
        var edgeWidget = new CaptureWidget { X = 0, Y = -0.5533f, Width = 1920, Height = 1080 };
        Assert(FileProtocol.ValidateRequest(edgeWidgetRequest(edgeWidget), out _), "subpixel edge widget");
        Assert(edgeWidget.TryGetPixelRectangle(out var edgeRectangle) && edgeRectangle == new PixelRectangle(0, 0, 1920, 1080), "subpixel edge normalization");
        Assert(!FileProtocol.ValidateRequest(edgeWidgetRequest(new CaptureWidget { X = 0, Y = -1.01f, Width = 1920, Height = 1080 }), out _), "negative widget rejection");
        Assert(!ScreenCapture.WidgetFitsClient(new PixelRectangle(0, 0, 101, 100), new ClientArea(nint.Zero, 0, 0, 100, 100)), "dimension validation");
        Console.WriteLine("Self-tests passed: valid/malformed request, filename safety, ACK serialization, SHA-256, dimension validation.");
        return 0;
    }

    private static void Assert(bool condition, string name)
    {
        if (!condition) throw new InvalidOperationException("Self-test failed: " + name);
    }

    private static CaptureRequest edgeWidgetRequest(CaptureWidget widget) => new()
    {
        ProtocolVersion = 1, SessionId = "session", RequestId = 1, TileIndex = 0, TileCount = 4,
        Filename = "map_x00_z00.png", Status = "CAPTURE_READY", Widget = widget
    };
}
