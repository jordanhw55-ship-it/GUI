#Requires AutoHotkey v2.0
#SingleInstance Force

; This script is designed to be called from the Python GUI.
; It accepts a single command-line argument, which is the key to be used in the macro.

if (A_Args.Length < 1) {
    ExitApp ; Exit if no key was provided
}

originalKey := A_Args[1]

; This is the same quickcast function from your original AHK script.
; It's extremely fast because it's pure AHK.
SendInput("{Ctrl Down}{9}{0}{Ctrl Up}")
SendInput("{" originalKey "}")
MouseClick("Left")
SendInput("{9}{0}")

ExitApp