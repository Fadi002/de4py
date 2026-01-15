#include "pch.h"
#include "SDK.h"
#include <Windows.h>
#include <stdio.h>
#include <detours.h>
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

void ANTI_HOOKS()
{
    HMODULE pythonModule = NULL;
    while (!pythonModule)
    {
        pythonModule = GetPyDll();
        if (!pythonModule)
        {
            Sleep(100);
        }
        else {
            Py_SetProgramName = (_Py_SetProgramName)(GetProcAddress(pythonModule, "Py_SetProgramName"));
            PyEval_InitThreads = (_PyEval_InitThreads)(GetProcAddress(pythonModule, "PyEval_InitThreads"));
            PyGILState_Ensure = (_PyGILState_Ensure)(GetProcAddress(pythonModule, "PyGILState_Ensure"));
            PyGILState_Release = (_PyGILState_Release)(GetProcAddress(pythonModule, "PyGILState_Release"));
            PyRun_SimpleStringFlags = (_PyRun_SimpleStringFlags)(GetProcAddress(pythonModule, "PyRun_SimpleStringFlags"));
        }
    }
}

#pragma comment(lib, "detours.lib")
typedef BOOL(WINAPI* PFnVirtualProtect)(LPVOID lpAddress, SIZE_T dwSize, DWORD flNewProtect, PDWORD lpflOldProtect);
typedef void* (__cdecl* PFnmemcpy)(void* dest, const void* src, size_t count);

PFnVirtualProtect TrueVirtualProtect = VirtualProtect;
PFnmemcpy Truememcpy = memcpy;
BOOL WINAPI HookedVirtualProtect(LPVOID lpAddress, SIZE_T dwSize, DWORD flNewProtect, PDWORD lpflOldProtect)
{
    if (lpAddress == Py_SetProgramName ||
        lpAddress == PyEval_InitThreads ||
        lpAddress == PyGILState_Ensure ||
        lpAddress == PyGILState_Release ||
        lpAddress == PyRun_SimpleStringFlags)
    {
        return TRUE; 
    }
    return TrueVirtualProtect(lpAddress, dwSize, flNewProtect, lpflOldProtect);
}
void* __cdecl Hookedmemcpy(void* dest, const void* src, size_t count)
{
    if (dest == Py_SetProgramName ||
        dest == PyEval_InitThreads ||
        dest == PyGILState_Ensure ||
        dest == PyGILState_Release ||
        dest == PyRun_SimpleStringFlags)
    {
        return NULL;
    }

    return Truememcpy(dest, src, count);
}

BOOL WINAPI DllMain(HINSTANCE hinstDLL, DWORD fdwReason, LPVOID lpReserved)
{
    ANTI_HOOKS();
    if (fdwReason == DLL_PROCESS_ATTACH)
    {
        DetourTransactionBegin();
        DetourUpdateThread(GetCurrentThread());
        DetourAttach(&(PVOID&)TrueVirtualProtect, HookedVirtualProtect);
        DetourAttach(&(PVOID&)Truememcpy, Hookedmemcpy);
        DetourTransactionCommit();
    }
    else if (fdwReason == DLL_PROCESS_DETACH)
    {
        DetourTransactionBegin();
        DetourUpdateThread(GetCurrentThread());
        DetourDetach(&(PVOID&)TrueVirtualProtect, HookedVirtualProtect);
        DetourDetach(&(PVOID&)Truememcpy, Hookedmemcpy);
        DetourTransactionCommit();
    }
    return TRUE;
}
