# Nuclear Option Server Panel (Modern UI)

A Windows-based Python control panel for managing **Nuclear Option** dedicated servers from a web UI and optional Discord bot.

This panel can:
- deploy new dedicated servers with SteamCMD
- start, stop, and restart individual servers
- manage ports and basic server settings
- support local and remote cluster nodes
- manage NOBlackBox install / Tacview recording settings
- browse recordings in the Gallery
- optionally control servers from the Discord bot

## Requirements

- **Windows 10 or Windows 11**
- **Python 3.11 (64-bit) recommended**
  - If you already have a working Python 3.x install, the panel should usually work with that too
- Administrator rights when launching the panel if you want firewall automation and the smoothest setup

## Before you run it

1. Extract the ZIP to a normal folder such as:
   `C:\Server-Panel`
2. Right-click the extracted folder or the ZIP you downloaded, open **Properties**, and if you see **Unblock**, check it and click **Apply**.
   - If Windows marks the download as blocked, scripts inside the panel can be blocked too.
3. Install Python if needed.
   - During Python install, enable **Add Python to PATH**.

## First launch / install

1. Open the panel folder.
2. Right-click **start-panel.bat** and choose **Run as administrator**.
3. The batch file will:
   - elevate with UAC
   - find Python
   - start the panel
4. On first run, missing Python packages will be installed automatically.
5. Open the panel in your browser at:
   `http://127.0.0.1:5000`

## Default login

Default panel login:
- **Username:** `admin`
- **Password:** `changeme`

On first login, the panel will force you to change the default username and password before continuing.

## Basic setup flow

### 1) Deploy or add a server
Use the **Server Management** area to create a server entry and point it to its install folder.

Typical setup:
- choose a server name
- choose the install folder for that server
- assign the remote command port / game ports needed for that server
- deploy or update the server files with SteamCMD if needed

Recommended layout:
- one folder per server
- example:
  - `C:\Server-Panel\servers\Test`
  - `C:\Server-Panel\servers\Test 2`

Using a separate folder per server helps the panel keep process control, configs, and recordings separated correctly.

### 2) Start the panel-managed server
Use the **Start**, **Stop**, and **Restart** buttons in the web UI to control each server individually.

### 3) Configure NOBlackBox / Tacview
In the **NoBlackBox** section you can:
- install or uninstall NOBlackBox
- set the recording path
- save NOBlackBox config values
- install Tacview for reviewing recordings

If multiple servers use the same recording root folder, the panel will place each server's recordings into its own subfolder automatically.

Example:
- root path entered: `C:\Users\YourName\Desktop\Footage`
- resulting per-server paths:
  - `C:\Users\YourName\Desktop\Footage\Test`
  - `C:\Users\YourName\Desktop\Footage\Test 2`

### 4) Use the Gallery
The **Gallery** page lets you browse NOBlackBox recordings by server.

From Gallery you can:
- switch between server pills
- open a clip in Tacview or your default viewer
- use **Go to file path** to open the folder where that exact clip is stored

This is especially useful if a Discord upload is too large and you need to upload the file manually.

## Discord bot

The optional Discord bot can control servers and help with footage access.


## Cluster / remote nodes

The panel supports local and remote server nodes.

That means you can:
- manage servers on the same machine
- add remote nodes
- send panel actions to those nodes from one main panel

Keep the panel itself on trusted networks unless you intentionally place it behind a proper reverse proxy.

## Important notes

- The **panel web server** defaults to `127.0.0.1`.
- For best results, always launch the panel with **start-panel.bat** as administrator.

## Troubleshooting

### The batch file closes or Python is not found
Install Python 3.x and make sure **Add Python to PATH** was enabled during setup.


### Firewall or port rules do not work
Make sure you started the panel with **start-panel.bat** using administrator rights.

### Discord footage upload says file is too large
Use the **Gallery** page and click **Go to file path** for that clip, then upload it manually to your discord.

## Launch files

- `start-panel.bat` - recommended Windows launcher

