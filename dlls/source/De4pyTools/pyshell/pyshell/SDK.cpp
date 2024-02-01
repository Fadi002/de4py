/*********************************************************************
      | credits : https://github.com/call-042PE/PyInjector |
      | modded by 0xmrpepe : https://github.com/Fadi002    |
      |                  de4py project                     |
*********************************************************************/
#include "SDK.h"
#include <Psapi.h>
_Py_SetProgramName Py_SetProgramName;
_PyEval_InitThreads PyEval_InitThreads;
_PyGILState_Ensure PyGILState_Ensure;
_PyGILState_Release PyGILState_Release;
_PyRun_SimpleStringFlags PyRun_SimpleStringFlags;

HMODULE GetPyDll()
{
    HANDLE hProcess = GetCurrentProcess();
    HMODULE hModules[1024];
    DWORD cbNeeded;
    HMODULE Python = NULL;
    if (EnumProcessModules(hProcess, hModules, sizeof(hModules), &cbNeeded))
    {
        for (DWORD i = 0; i < (cbNeeded / sizeof(HMODULE)); i++) {
            char szModule[MAX_PATH];
            if (GetModuleFileNameExA(hProcess, hModules[i], szModule, sizeof(szModule) / sizeof(char))) {
                if (strstr(szModule, "python3") != NULL) {
                    Python = hModules[i];
                    break;
                }
            }
        }
    }
    CloseHandle(hProcess);
    return Python;
}

void SDK::InitCPython()
{
    HMODULE hPython = GetPyDll();
    Py_SetProgramName = (_Py_SetProgramName)(GetProcAddress(hPython, "Py_SetProgramName"));
    PyEval_InitThreads = (_PyEval_InitThreads)(GetProcAddress(hPython, "PyEval_InitThreads"));
    PyGILState_Ensure = (_PyGILState_Ensure)(GetProcAddress(hPython, "PyGILState_Ensure"));
    PyGILState_Release = (_PyGILState_Release)(GetProcAddress(hPython, "PyGILState_Release"));
    PyRun_SimpleStringFlags = (_PyRun_SimpleStringFlags)(GetProcAddress(hPython, "PyRun_SimpleStringFlags"));
}