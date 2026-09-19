using System.Diagnostics;
using System.Runtime.InteropServices;

namespace DayZMapCapture.Capture;

public readonly record struct ClientArea(nint WindowHandle, int Left, int Top, int Width, int Height);

public static class DayZWindow
{
    private static readonly string[] ProcessNames = ["DayZDiag_x64", "DayZ_x64"];

    public static bool TryFindClientArea(out ClientArea clientArea, out string error)
    {
        foreach (var processName in ProcessNames)
        {
            foreach (var process in Process.GetProcessesByName(processName))
            using (process)
            {
                process.Refresh();
                if (process.MainWindowHandle == nint.Zero) continue;
                if (!GetClientRect(process.MainWindowHandle, out var rect)) continue;
                var point = new POINT { X = 0, Y = 0 };
                if (!ClientToScreen(process.MainWindowHandle, ref point)) continue;
                var width = rect.Right - rect.Left;
                var height = rect.Bottom - rect.Top;
                if (width > 0 && height > 0)
                {
                    clientArea = new ClientArea(process.MainWindowHandle, point.X, point.Y, width, height);
                    error = "";
                    return true;
                }
            }
        }
        clientArea = default;
        error = "DAYZ_WINDOW_NOT_FOUND";
        return false;
    }

    [StructLayout(LayoutKind.Sequential)] private struct RECT { public int Left; public int Top; public int Right; public int Bottom; }
    [StructLayout(LayoutKind.Sequential)] private struct POINT { public int X; public int Y; }
    [DllImport("user32.dll", SetLastError = true)] private static extern bool GetClientRect(nint hWnd, out RECT lpRect);
    [DllImport("user32.dll", SetLastError = true)] private static extern bool ClientToScreen(nint hWnd, ref POINT lpPoint);
}
