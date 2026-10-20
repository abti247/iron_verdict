# Stream overlay in OBS

The stream overlay is the Iron Verdict display as an OBS **browser source** on top of the camera picture. It shows lights, card colours and reasons, Good/No lift, the timer and — in VPortal sessions — lifter and attempt info, on a transparent background without controls. Technical details: [architecture.md](architecture.md), *Stream overlay*.

## 1. Get the URL

On role select of the session, click **Stream overlay (OBS)** and copy the URL. It looks like this:

```
https://<your-iron-verdict-host>/?session=AB12CD34&overlay=1
```

The URL contains the session code (like the QR code on role select). Keep it on the streaming PC; it is never visible in the stream.

## 2. Add the browser source

1. OBS → *Sources* → **+** → **Browser**.
2. **URL:** the copied URL.
3. **Width 1920, height 1080** (the layout is in percent of the source, so other sizes work too; keep the aspect ratio of your stream).
4. Leave *Custom CSS* empty. Leave *Shutdown source when not visible* off, so the overlay stays connected.
5. Put the source above the camera in the source list.

The overlay connects by itself. It counts as one display (`DISPLAY_CAP`). After an OBS restart, a reload of the source ("Refresh cache of current page") or a connection loss it reconnects on its own. While the connection is down, a small dot appears in the top right corner; it disappears once the overlay is connected again.

When the session ends the overlay shows "Session ended". With a wrong or old code it shows "Session not found". In both cases: copy the URL of the new session and enter it in the source.

## 3. Arrange the overlay

The overlay has its own layout, separate from the hall display. Without one it uses the default arrangement of the display. There are two ways to set it up:

**A — directly in OBS.** Right-click the source → **Interact**. In that window press **S** → **Edit layout**. Drag blocks with the mouse, resize them at the corner handle, bring the lights closer together or further apart at the handle beside them, hide blocks you do not need (e.g. the timer), then **Save**. The layout is stored in OBS's browser profile and survives restarts. While editing, the overlay shows a dark checkerboard and the frames — **in the stream as well**, so edit before going live or hide the source meanwhile.

**B — prepare in a browser, put it in the URL.** Open the overlay URL in Chrome, full screen (F11) on a 16:9 monitor. Press **S** → **Edit layout**, arrange the blocks, then **Layout code** and copy the code (`IV1.…`). Close the browser tab. Append the code to the URL in OBS:

```
https://<your-iron-verdict-host>/?session=AB12CD34&overlay=1&layout=IV1.eyJ2Ijox…
```

The layout from the URL is then the only one: the panel ("S") shows "Layout comes from the URL" instead of the edit button. To change it, repeat B with the new code. This way the same stream layout can be reused on another PC or at the next competition. If the code in the URL is invalid, the overlay uses its saved (or default) layout and the panel says so.

**Do not stack blocks.** Blocks may overlap, but their dark panels are translucent: where one block lies on another, the text underneath shows through (e.g. a long reason behind "No lift"). Leave some space around the lights for the reasons — long ones wrap to two or three lines. Check with the longest reasons of each discipline before going live.

## 4. VPortal (lifter and attempt info)

In a VPortal session the overlay needs its own VPortal login, because OBS has its own browser profile. Right-click the source → **Interact** → **S** → **Connect to comp software** → federation, user, password, platform. Like the editor, the settings panel and this dialog (including the typed user name) show in the stream while they are open — connect before going live or hide the source meanwhile. If the server could not be reached when the source started, the button appears as soon as the overlay could check the session again. Lifter and attempt info appear within a few seconds. The login stays stored in the OBS profile; after a reload the panel shows "Connected to … · <platform>".

## Checklist before going live

- [ ] Source 1920 × 1080, above the camera
- [ ] A test vote shows the lights and Good/No lift in the preview, and the background is transparent
- [ ] Layout arranged (A or B), no blocks on top of each other, checkerboard gone (editor closed)
- [ ] VPortal sessions: lifter and attempt info visible
- [ ] Right-click → *Refresh cache of current page*: the overlay comes back by itself
