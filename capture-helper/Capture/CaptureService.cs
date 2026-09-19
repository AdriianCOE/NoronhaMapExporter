using DayZMapCapture.Protocol;

namespace DayZMapCapture.Capture;

public sealed class CaptureService
{
    private readonly Dictionary<string, CaptureAck> processed = new(StringComparer.Ordinal);

    public void ProcessSession(string sessionDirectory)
    {
        var requestPath = Path.Combine(sessionDirectory, FileProtocol.RequestFileName);
        if (!File.Exists(requestPath)) return;
        if (!FileProtocol.TryReadRequest(requestPath, out var request, out _)) return;
        var key = request!.SessionId + ":" + request.RequestId;
        if (processed.TryGetValue(key, out var duplicate))
        {
            FileProtocol.WriteAckAtomically(sessionDirectory, duplicate);
            return;
        }
        if (FileProtocol.TryReadReceipt(sessionDirectory, request, out var receipt))
        {
            processed[key] = receipt!;
            FileProtocol.WriteAckAtomically(sessionDirectory, receipt!);
            return;
        }
        var ack = Capture(sessionDirectory, request);
        processed[key] = ack;
        if (ack.Status == "OK") FileProtocol.WriteReceiptAtomically(sessionDirectory, ack);
        FileProtocol.WriteAckAtomically(sessionDirectory, ack);
        Console.WriteLine($"{ack.Status} session={ack.SessionId} request={ack.RequestId} file={ack.Filename} {ack.Error}");
    }

    private static CaptureAck Capture(string sessionDirectory, CaptureRequest request)
    {
        try
        {
            if (!request.Widget.TryGetPixelRectangle(out var widget)) return Error(request, "ERROR_INVALID_WIDGET");
            var capturesDirectory = Path.Combine(sessionDirectory, "captures");
            Directory.CreateDirectory(capturesDirectory);
            var output = Path.Combine(capturesDirectory, request.Filename);
            if (File.Exists(output))
            {
                if (!ScreenCapture.HasExpectedDimensions(output, widget.Width, widget.Height)) return Error(request, "ERROR_DIMENSION_MISMATCH");
                return Error(request, "ERROR_CAPTURE_ALREADY_EXISTS");
            }
            if (!DayZWindow.TryFindClientArea(out var client, out var windowError)) return Error(request, windowError);
            if (!ScreenCapture.WidgetFitsClient(widget, client)) return Error(request, "ERROR_WIDGET_OUTSIDE_CLIENT");
            ScreenCapture.SaveWidgetPng(client, widget, output);
            if (!ScreenCapture.HasExpectedDimensions(output, widget.Width, widget.Height)) return Error(request, "ERROR_DIMENSION_MISMATCH");
            return Ok(request, output);
        }
        catch (Exception exception)
        {
            return Error(request, "ERROR_CAPTURE: " + exception.GetType().Name);
        }
    }

    private static CaptureAck Ok(CaptureRequest request, string output) => new()
    {
        SessionId = request.SessionId, RequestId = request.RequestId, Filename = request.Filename,
        Width = request.Widget.TryGetPixelRectangle(out var widget) ? widget.Width : 0,
        Height = request.Widget.TryGetPixelRectangle(out widget) ? widget.Height : 0,
        Sha256 = FileProtocol.CalculateSha256(output), Status = "OK"
    };

    private static CaptureAck Error(CaptureRequest request, string error) => new()
    {
        SessionId = request.SessionId, RequestId = request.RequestId, Filename = request.Filename, Status = error, Error = error
    };
}
