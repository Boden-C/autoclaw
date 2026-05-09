#NoEnv
#SingleInstance Force
#InstallKeybdHook
#UseHook On
SendMode Event
SetKeyDelay, 0, 10
SetWinDelay, 0
SetControlDelay, 0
SetBatchLines, -1
ListLines, Off
SetTitleMatchMode, 2

global StopEntry := false
global IsRunning := false
global InputData := ""
global RowAction := "Tab"
global EntryGuiHwnd := 0
global CurrentSourceFile := ""
global DeleteFileAfterSuccess := false

#If (IsRunning)
Esc::
StopEntry := true
return

Pause::
StopEntry := true
return

Break::
StopEntry := true
return
#If

#If (EntryGuiHwnd && WinActive("ahk_id " EntryGuiHwnd))
Esc::
Gosub, CancelEntry
return
#If

F1::
HandleHotkey("F1")
return

F2::
HandleHotkey("F2")
return

F3::
HandleHotkey("F3")
return

F4::
HandleHotkey("F4")
return

F5::
HandleHotkey("F5")
return

F6::
HandleHotkey("F6")
return

F7::
HandleHotkey("F7")
return

F8::
HandleHotkey("F8")
return

F9::
HandleHotkey("F9")
return

F10::
HandleHotkey("F10")
return

F11::
HandleHotkey("F11")
return

F12::
HandleHotkey("F12")
return

StartWithTab:
RowAction := "Tab"
Gosub, StartEntryCommon
return

StartWithPgDn:
RowAction := "PgDn"
Gosub, StartEntryCommon
return

StartWithEnter:
RowAction := "Enter"
Gosub, StartEntryCommon
return

StartEntryCommon:
Gui, Submit, NoHide
Gui, Destroy
EntryGuiHwnd := 0

InputData := NormalizeLineEndings(InputBox)
InputData := RemoveBOM(InputData)
CurrentSourceFile := ""
DeleteFileAfterSuccess := false

RunEntryData(InputData)
return

CancelEntry:
Gui, Destroy
EntryGuiHwnd := 0
return

GuiClose:
GuiEscape:
Gui, Destroy
EntryGuiHwnd := 0
return

ExitAppNow:
Gui, Destroy
EntryGuiHwnd := 0
ExitApp
return

HandleHotkey(hotkeyName) {
    global StopEntry, IsRunning

    StopEntry := false
    if (IsRunning)
        return

    sourceFile := GetHotkeyCsvPath(hotkeyName)
    if (FileExist(sourceFile)) {
        StartFromFile(sourceFile)
        return
    }

    ShowEntryGui(hotkeyName)
}

GetHotkeyCsvPath(hotkeyName) {
    return A_ScriptDir "\" hotkeyName ".csv"
}

ShowEntryGui(hotkeyName := "F1") {
    global InputData, EntryGuiHwnd

    InputData := Clipboard
    InputData := NormalizeLineEndings(InputData)
    InputData := RemoveBOM(InputData)

    Gui, New, +AlwaysOnTop +HwndEntryGuiHwnd, Paste Raw CSV or TSV
    Gui, Margin, 12, 12
    Gui, Font, s10, Segoe UI
    Gui, Add, Text,, Paste raw CSV or TSV below. No headers needed.
    Gui, Add, Text, y+6, %hotkeyName% will auto-run %hotkeyName%.csv if that file exists in this folder.
    Gui, Add, Text, y+6, It will type each field with tabs in between. Choose how each new row advances.
    Gui, Font, s10, Consolas
    Gui, Add, Edit, w980 h420 vInputBox WantTab, %InputData%
    Gui, Font, s10, Segoe UI
    Gui, Add, Button, w150 Default gStartWithTab, Start with Tab
    Gui, Add, Button, x+10 w150 gStartWithPgDn, Start with PgDn
    Gui, Add, Button, x+10 w150 gStartWithEnter, Start with Enter
    Gui, Add, Button, x+10 w90 gCancelEntry, Cancel
    Gui, Add, Button, x+10 w70 gExitAppNow, Exit
    Gui, Add, Text, xm y+10, Esc cancels while typing. In this window, Esc closes the window.
    Gui, Show
}

StartFromFile(sourceFile) {
    global InputData, RowAction, CurrentSourceFile, DeleteFileAfterSuccess

    FileRead, fileText, %sourceFile%
    fileText := NormalizeLineEndings(fileText)
    fileText := RemoveBOM(fileText)

    settings := ParseSettingsLine(fileText)
    InputData := settings.Data
    RowAction := settings.Newline
    CurrentSourceFile := sourceFile
    DeleteFileAfterSuccess := settings.DeleteFileAfterSuccess

    RunEntryData(InputData)
}

RunEntryData(rawText) {
    global StopEntry, IsRunning, CurrentSourceFile, DeleteFileAfterSuccess

    lines := SplitLinesPreserveBlank(rawText)
    if (lines.MaxIndex() = 0)
        return

    lastIndex := lines.MaxIndex()
    if (lastIndex >= 1 && lines[lastIndex] = "")
        lines.RemoveAt(lastIndex)

    if (lines.MaxIndex() = 0)
        return

    IsRunning := true
    StopEntry := false
    completedSuccessfully := true

    for lineIndex, line in lines
    {
        if (StopEntry) {
            completedSuccessfully := false
            break
        }

        if (line = "")
        {
            if !AdvanceBlankRow() {
                completedSuccessfully := false
                break
            }
            continue
        }

        fields := ParseDelimitedLine(line)
        fieldCount := fields.MaxIndex()

        if (fieldCount = 0)
        {
            if !AdvanceBlankRow() {
                completedSuccessfully := false
                break
            }
            continue
        }

        for fieldIndex, field in fields
        {
            isLastField := (fieldIndex = fieldCount)
            if !TypeField(field, isLastField) {
                completedSuccessfully := false
                break 2
            }
        }
    }

    if (completedSuccessfully && DeleteFileAfterSuccess && CurrentSourceFile != "" && FileExist(CurrentSourceFile))
        FileDelete, %CurrentSourceFile%

    IsRunning := false
    StopEntry := false
    CurrentSourceFile := ""
    DeleteFileAfterSuccess := false
}

ParseSettingsLine(ByRef fileText) {
    settings := { Newline: "Tab", DeleteFileAfterSuccess: false, Data: fileText }
    lines := SplitLinesPreserveBlank(fileText)
    if (lines.MaxIndex() = 0)
        return settings

    firstLine := RemoveBOM(lines[1])
    if (SubStr(Trim(firstLine), 1, 1) != "#")
        return settings

    settingsJson := Trim(SubStr(firstLine, 2))
    newlineValue := ExtractJsonStringValue(settingsJson, "newline")
    if (newlineValue != "")
        settings.Newline := NormalizeNewlineSetting(newlineValue)

    deleteValue := ExtractJsonBooleanValue(settingsJson, "delete_file_after_success")
    if (deleteValue != "")
        settings.DeleteFileAfterSuccess := deleteValue

    lines.RemoveAt(1)
    rebuilt := ""
    for index, line in lines
    {
        if (index > 1)
            rebuilt .= "`n"
        rebuilt .= line
    }
    settings.Data := rebuilt
    return settings
}

ExtractJsonStringValue(jsonText, keyName) {
    pattern := """" keyName """" "\s*:\s*""([^""]*)"""
    if RegExMatch(jsonText, pattern, match)
        return match1
    return ""
}

ExtractJsonBooleanValue(jsonText, keyName) {
    pattern := """" keyName """" "\s*:\s*(true|false)"
    if RegExMatch(jsonText, pattern, match)
        return (match1 = "true")
    return ""
}

NormalizeNewlineSetting(value) {
    cleaned := Trim(value)
    StringLower, cleaned, cleaned
    if (cleaned = "pgdn" || cleaned = "pagedown")
        return "PgDn"
    if (cleaned = "enter")
        return "Enter"
    return "Tab"
}

TypeField(val, isLastField := false) {
    global StopEntry

    if (StopEntry)
        return false

    val := CleanupField(val)
    SendEvent {Raw}%val%
    Sleep, 10

    if (StopEntry)
        return false

    if (isLastField)
        return DoRowAdvance()

    SendEvent {Tab}
    Sleep, 10
    return true
}

AdvanceBlankRow() {
    return DoRowAdvance()
}

DoRowAdvance() {
    global StopEntry, RowAction

    if (StopEntry)
        return false

    if (RowAction = "PgDn")
        SendEvent {PgDn}
    else if (RowAction = "Enter")
        SendEvent {Enter}
    else
        SendEvent {Tab}

    Sleep, 20
    return !StopEntry
}

CleanupField(val) {
    val := StrReplace(val, "&amp;", "&")
    val := StrReplace(val, "&quot;", Chr(34))
    val := StrReplace(val, "&lt;", "<")
    val := StrReplace(val, "&gt;", ">")
    val := StrReplace(val, "&#39;", "'")

    if (SubStr(val, 1, 1) = Chr(0xFEFF))
        val := SubStr(val, 2)

    return val
}

NormalizeLineEndings(text) {
    text := StrReplace(text, "`r`n", "`n")
    text := StrReplace(text, "`r", "`n")
    return text
}

RemoveBOM(text) {
    if (SubStr(text, 1, 1) = Chr(0xFEFF))
        text := SubStr(text, 2)
    return text
}

SplitLinesPreserveBlank(text) {
    return StrSplit(text, "`n")
}

ParseDelimitedLine(line) {
    if InStr(line, "`t")
        return ParseTSVLine(line)
    return ParseCSVLine(line)
}

ParseTSVLine(line) {
    return StrSplit(line, "`t")
}

ParseCSVLine(line) {
    fields := []
    field := ""
    inQuotes := false
    i := 1
    len := StrLen(line)

    while (i <= len) {
        ch := SubStr(line, i, 1)

        if (ch = Chr(34)) {
            nextCh := (i < len) ? SubStr(line, i + 1, 1) : ""

            if (inQuotes) {
                if (nextCh = Chr(34)) {
                    field .= Chr(34)
                    i++
                } else {
                    inQuotes := false
                }
            } else {
                if (field = "")
                    inQuotes := true
                else
                    field .= ch
            }
        }
        else if (ch = "," && !inQuotes) {
            fields.Push(field)
            field := ""
        }
        else {
            field .= ch
        }

        i++
    }

    fields.Push(field)
    return fields
}