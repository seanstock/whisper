#Requires AutoHotkey v2.0

AppName := "Whisper Transcription"
outputFile := A_ScriptDir . "\output.txt"

!g:: {
    ; If window already exists, just activate it.
    if WinExist(AppName) {
        WinActivate(AppName)
        return
    }

    ; Delete old output file to prevent false positives from a previous run
    if FileExist(outputFile) {
        FileDelete(outputFile)
    }

    pythonPath := A_ScriptDir . "\whisper-env\Scripts\pythonw.exe"
    scriptPath := A_ScriptDir . "\pythonscript.pyw"
    
    ; Run the script and get its Process ID (PID)
    Run('"' . pythonPath . '" "' . scriptPath . '"', "", "", &PID)

    ; Wait for either the output file to be created or the process to close
    Loop {
        Sleep(250)
        if FileExist(outputFile) {
            break  ; Found the result, proceed.
        }
        if !ProcessExist(PID) {
            ; The user closed the window manually. Nothing to do.
            return
        }
    }

    ; Read the result, send it, and clean up.
    text := Trim(FileRead(outputFile))
    if (text != "") {
        SendText(text)
    } else {
        TrayTip("Whisper", "Transcription was empty.", 2)
    }
    FileDelete(outputFile)
} 