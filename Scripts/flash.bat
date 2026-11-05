@echo off
rem Прошивка готового hex из Build\ через загрузчик платы (avrdude без PlatformIO), Readme §8.
rem   Scripts\flash.bat [порт] [hex] [скорость] [протокол]   - в любом порядке, разбор по виду:
rem   порт     - COM5 и т. п. (не задан - спросит, покажет список портов)
rem   hex      - путь к файлу (не задан - список TempDisplay_* / ChipInfo_* из Build\ на выбор)
rem   скорость - 57600 по умолчанию; не задана и не прошилось - ещё попытки на MINBAUD (urboot подстраивается сам)
rem   протокол - urclock (urboot, по умолчанию) или arduino (Optiboot / ATmegaBOOT - скорость по таблице Readme §8)
rem   reset    - нет DTR (автосброса): Enter, затем, пока идут попытки avrdude, нажать и отпустить RESET платы
rem   пример:  Scripts\flash.bat COM5 Build\TempDisplay_nano16_240x320_ST7789.hex
rem avrdude - рядом с батником (архив Build\TempDisplay_flash.zip, там же и hex), затем Tools\avrdude\ проекта
rem (8.1, вместе с avrdude.conf), нет - PlatformIO, нет - PATH (7.1 и новее).
rem Файл - UTF-8 с CRLF; консоль на время работы - UTF-8 (chcp 65001), при выходе - прежняя кодовая страница.
rem Шрифт консоли мелкий после chcp 65001 - в консоли растровый шрифт: свойства окна - Шрифт - Consolas.
for /f "tokens=2 delims=:." %%c in ('chcp') do set "OLDCP=%%c"
chcp 65001 >nul
setlocal EnableDelayedExpansion

set "ROOT=%~dp0.."
set "PORT="
set "HEX="
set "BAUD=57600"
set "MINBAUD=19200"
set "BAUDSET="
set "PROTO=urclock"
set "TRIES=3"
set "ASK="
set "MANUAL="
if "%~1"=="" set "ASK=1"

rem параметры: *.hex - файл, COMn - порт, число - скорость, urclock / arduino - протокол
:args
if "%~1"=="" goto argsdone
set "A=%~1"
if /i "%~x1"==".hex" (
    set "HEX=%~f1"
) else if /i "!A:~0,3!"=="COM" (
    set "PORT=%~1"
) else if /i "%~1"=="urclock" (
    set "PROTO=urclock"
) else if /i "%~1"=="arduino" (
    set "PROTO=arduino"
) else if /i "%~1"=="reset" (
    set "MANUAL=1"
) else (
    echo %~1| findstr /r "^[0-9][0-9]*$" >nul || (echo Непонятный параметр "%~1": hex, COMn, скорость, протокол или reset & goto fail)
    set "BAUD=%~1"
    set "BAUDSET=1"
)
shift
goto args
:argsdone
set "OPT="
if /i "%PROTO%"=="urclock" set "OPT=-xnometadata"
rem ручной сброс: каждая попытка - с 0x30 (по нему urboot подстраивает скорость), иначе после первой - только 0x20
if defined MANUAL if /i "%PROTO%"=="urclock" set "OPT=%OPT% -xstrict -xnoautoreset"

set "HEXDIR=%ROOT%\Build"
if exist "%~dp0avrdude.exe" set "HEXDIR=%~dp0."
set "AVRDIR=%~dp0."
if not exist "%AVRDIR%\avrdude.exe" set "AVRDIR=%ROOT%\Tools\avrdude"
if not exist "%AVRDIR%\avrdude.exe" set "AVRDIR=%USERPROFILE%\.platformio\packages\tool-avrdude"
set "AVRDUDE=%AVRDIR%\avrdude.exe"
set "CONFARG=-C "%AVRDIR%\avrdude.conf""
if not exist "%AVRDUDE%" (
    where avrdude >nul 2>nul || (echo Нет avrdude: Tools\avrdude\ из репозитория или github.com/avrdudes/avrdude/releases & goto fail)
    set "AVRDUDE=avrdude"
    set "CONFARG="
)

if "%HEX%"=="" (
    set N=0
    for %%F in ("%HEXDIR%\TempDisplay_*.hex" "%HEXDIR%\ChipInfo_*.hex") do (
        set /a N+=1
        set "F!N!=%%~fF"
        echo   !N!. %%~nxF
    )
    if !N!==0 (echo Нет hex в Build\ - собрать прошивку ^(PlatformIO^) & goto fail)
    set /p SEL="Номер файла (nano8 - кварц 8 МГц, nano16 - 16 МГц): "
    for %%N in (!SEL!) do set "HEX=!F%%N!"
)
if not exist "%HEX%" (echo Нет файла "%HEX%" & goto fail)

if "%PORT%"=="" (
    echo Порты:
    powershell -NoProfile -Command "[System.IO.Ports.SerialPort]::GetPortNames() | Sort-Object"
    set /p PORT="Порт (например COM5): "
)
if defined ASK if not defined MANUAL (
    set "R="
    set /p R="Нет вывода DTR, сброс кнопкой RESET? r - да, Enter - нет: "
    if /i "!R!"=="r" (
        set "MANUAL=1"
        if /i "%PROTO%"=="urclock" set "OPT=!OPT! -xstrict -xnoautoreset"
    )
)

echo.
echo Файл: %HEX%
echo avrdude: %AVRDUDE%
echo Порт: %PORT%, %PROTO%. Монитор порта - закрыть, HLK - отключить.
:upload
for /l %%i in (1,1,%TRIES%) do (
    echo.
    echo === Попытка %%i из %TRIES%, %BAUD% бод
    if defined MANUAL (
        echo Нажать Enter, затем, пока идут строки "not in sync", нажать и отпустить RESET на плате
        pause >nul
    )
    "%AVRDUDE%" %CONFARG% -p m328p -c %PROTO% %OPT% -b %BAUD% -P %PORT% -D -U flash:w:"%HEX%":i
    if !errorlevel!==0 goto ok
    ping -n 3 127.0.0.1 >nul
)
rem скорость не задана, urboot - ещё раз на минимальной (у arduino скорость загрузчика постоянная)
if not defined BAUDSET if /i "%PROTO%"=="urclock" if not "%BAUD%"=="%MINBAUD%" (
    set "BAUD=%MINBAUD%"
    goto upload
)

:fail
echo.
echo *** НЕ ПРОШИТО. Разбор сообщений avrdude - Readme §8.
if defined ASK pause
chcp %OLDCP% >nul
exit /b 1

:ok
echo.
echo *** ГОТОВО: записано и сверено.
if defined ASK pause
chcp %OLDCP% >nul
exit /b 0
