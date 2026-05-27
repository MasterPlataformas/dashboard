@echo off
cd /d "C:\platform-tools"
adb connect 192.168.1.166:5555
adb shell input keyevent KEYCODE_POWER