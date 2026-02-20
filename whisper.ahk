#Requires AutoHotkey v2.0
#SingleInstance Force
DetectHiddenWindows True

; --- Setup Paths ---
PythonPath   := A_ScriptDir . "\whisper-env\Scripts\pythonw.exe"
ScriptPath   := A_ScriptDir . "\pythonscript.pyw"
OutputFile   := A_ScriptDir . "\output.txt"
StartFlag    := A_ScriptDir . "\start.flag"
StopFlag     := A_ScriptDir . "\stop.flag"
ShowFlag     := A_ScriptDir . "\show.flag"
MuteFlag     := A_ScriptDir . "\mute.flag"
HotkeyFlag   := A_ScriptDir . "\hotkey_change.flag"
ConfigFile   := A_ScriptDir . "\config.json"

; --- Startup: Launch Python in background if not running ---
if !WinExist("Whisper Transcription") {
    Run('"' . PythonPath . '" "' . ScriptPath . '"')
}

; --- State ---
global IsRecording     := false
global CurrentHotkey   := "``"   ; backtick (escaped for AHK)
global LastActiveWindow := 0

; --- Register initial hotkey (backtick) ---
Hotkey("*``", HotkeyDown)
Hotkey("*`` Up", HotkeyUp)

; --- Poll for hotkey changes every 500ms ---
SetTimer(CheckHotkeyChange, 500)

; --------- Alt+G: Show the GUI ---------
!g:: {
    FileAppend("", ShowFlag)
}

; ════════════════════════════════════════
; Hotkey handlers (named functions)
; ════════════════════════════════════════

HotkeyDown(*) {
    global IsRecording, LastActiveWindow
    if IsRecording
        return
    IsRecording := true
    LastActiveWindow := WinActive("A")
    if FileExist(OutputFile)
        FileDelete(OutputFile)
    FileAppend("", StartFlag)
    if !FileExist(MuteFlag)
        SoundBeep(750, 100)
}

HotkeyUp(*) {
    global IsRecording
    IsRecording := false
    FileAppend("", StopFlag)
    if !FileExist(MuteFlag)
        SoundBeep(500, 100)
    if (WaitForResult())
        PasteText()
}

; ════════════════════════════════════════
; Hotkey change handler
; ════════════════════════════════════════

CheckHotkeyChange() {
    global HotkeyFlag, ConfigFile, CurrentHotkey
    if !FileExist(HotkeyFlag)
        return
    FileDelete(HotkeyFlag)

    raw := FileRead(ConfigFile)
    if RegExMatch(raw, '"hotkey"\s*:\s*"([^"]+)"', &m) {
        newKey := m[1]
        if (newKey = CurrentHotkey)
            return
        ; Disable old bindings
        try Hotkey("*" . CurrentHotkey, "Off")
        try Hotkey("*" . CurrentHotkey . " Up", "Off")
        ; Map display names back to AHK key names
        ahkKey := (newKey = "``") ? "``" : newKey
        CurrentHotkey := ahkKey
        ; Register new bindings
        Hotkey("*" . ahkKey, HotkeyDown)
        Hotkey("*" . ahkKey . " Up", HotkeyUp)
    }
}

; ════════════════════════════════════════
; Utility functions
; ════════════════════════════════════════

WaitForResult() {
    timeout := 0
    while !FileExist(OutputFile) && timeout < 40 {
        Sleep(250)
        timeout++
    }
    return FileExist(OutputFile)
}

PasteText() {
    global LastActiveWindow
    WinActivate("ahk_id " . LastActiveWindow)
    Sleep(100)

    ClipboardBackup := A_Clipboard
    A_Clipboard := ""
    text := Trim(FileRead(OutputFile))
    A_Clipboard := text

    if ClipWait(2) {
        Send("^v")
        Sleep(300)
    }

    A_Clipboard := ClipboardBackup
    FileDelete(OutputFile)
}
