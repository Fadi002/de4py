/*********************************************************************
      | credits : https://github.com/call-042PE/PyInjector |
      | modded by 0xmrpepe : https://github.com/Fadi002    |
      |                  de4py project                     |
*********************************************************************/
#include "SDK.h"

_Py_SetProgramName Py_SetProgramName;
_PyEval_InitThreads PyEval_InitThreads;
_PyGILState_Ensure PyGILState_Ensure;
_PyGILState_Release PyGILState_Release;
_PyRun_SimpleStringFlags PyRun_SimpleStringFlags;

void SDK::InitCPython()
{
    HMODULE hPython = 0x0;
    if (GetModuleHandleA("Python39.dll"))
        hPython = GetModuleHandleA("Python39.dll");
    else if (GetModuleHandleA("Python38.dll"))
        hPython = GetModuleHandleA("Python38.dll");
    else if (GetModuleHandleA("Python37.dll"))
        hPython = GetModuleHandleA("Python37.dll");
    else if (GetModuleHandleA("Python310.dll"))
        hPython = GetModuleHandleA("Python310.dll");
    else if (GetModuleHandleA("Python311.dll"))
        hPython = GetModuleHandleA("Python311.dll");
    else if (GetModuleHandleA("Python312.dll"))
        hPython = GetModuleHandleA("Python312.dll");
    else if (GetModuleHandleA("Python313.dll"))
        hPython = GetModuleHandleA("Python313.dll");
    Py_SetProgramName = (_Py_SetProgramName)(GetProcAddress(hPython, "Py_SetProgramName"));
    PyEval_InitThreads = (_PyEval_InitThreads)(GetProcAddress(hPython, "PyEval_InitThreads"));
    PyGILState_Ensure = (_PyGILState_Ensure)(GetProcAddress(hPython, "PyGILState_Ensure"));
    PyGILState_Release = (_PyGILState_Release)(GetProcAddress(hPython, "PyGILState_Release"));
    PyRun_SimpleStringFlags = (_PyRun_SimpleStringFlags)(GetProcAddress(hPython, "PyRun_SimpleStringFlags"));
}