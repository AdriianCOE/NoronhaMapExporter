using System.Drawing;
using System.Drawing.Imaging;
using DayZMapCapture.Protocol;

namespace DayZMapCapture.Capture;

public static class ScreenCapture
{
    public static bool WidgetFitsClient(PixelRectangle widget, ClientArea client) =>
        widget.X >= 0 && widget.Y >= 0 && widget.Width > 0 && widget.Height > 0 &&
        widget.X + widget.Width <= client.Width && widget.Y + widget.Height <= client.Height;

    public static void SaveWidgetPng(ClientArea client, PixelRectangle widget, string destination)
    {
        // Screen capture has no useful alpha channel.  Use an RGB bitmap so
        // the lossless PNG is fully opaque for geometric compositing.
        using var bitmap = new Bitmap(widget.Width, widget.Height, PixelFormat.Format24bppRgb);
        using (var graphics = Graphics.FromImage(bitmap))
            graphics.CopyFromScreen(client.Left + widget.X, client.Top + widget.Y, 0, 0, bitmap.Size, CopyPixelOperation.SourceCopy);
        var temporary = destination + ".tmp";
        bitmap.Save(temporary, ImageFormat.Png);
        File.Move(temporary, destination, false);
    }

    public static bool HasExpectedDimensions(string path, int width, int height)
    {
        using var image = Image.FromFile(path);
        return image.Width == width && image.Height == height;
    }
}
