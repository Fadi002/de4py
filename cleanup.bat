for /d /r "." %%d in (__pycache__) do if exist "%%d" rd /s /q "%%d"
for /d /r "." %%d in (logs) do if exist "%%d" rd /s /q "%%d"
for /d /r "." %%d in (.vs) do if exist "%%d" rd /s /q "%%d"
pause