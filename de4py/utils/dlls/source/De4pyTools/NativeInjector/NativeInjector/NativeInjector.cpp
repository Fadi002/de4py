/*********************************************************************
      | De4py Injector : https://github.com/Fadi002/de4py  |
      |                  de4py project                     |
*********************************************************************/
#include <iostream>
#include <Windows.h>
#include "injector.h"
using namespace std;
bool Inject(DWORD PID, char* DllPath)
{
    HANDLE ProcessToInject = OpenProcess(PROCESS_ALL_ACCESS, false, PID);
    if (ProcessToInject)
    {
        LPVOID LoadLibAddr = (LPVOID)GetProcAddress(GetModuleHandleA("kernel32.dll"), "LoadLibraryA");
        LPVOID Allocation = VirtualAllocEx(ProcessToInject, NULL, strlen(DllPath), MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE);
        if (WriteProcessMemory(ProcessToInject, Allocation, DllPath, strlen(DllPath), NULL))
        {
            HANDLE Injecting = CreateRemoteThread(ProcessToInject, NULL, NULL, (LPTHREAD_START_ROUTINE)LoadLibAddr, Allocation, 0, NULL);
            if (Injecting != NULL)
            {
                WaitForSingleObject(Injecting, INFINITE);
                VirtualFreeEx(ProcessToInject, Allocation, strlen(DllPath), MEM_RELEASE);
                CloseHandle(Injecting);
                CloseHandle(ProcessToInject);
                return true;
            }
        }
    }
    return false;
}
bool Showconsole(int pid) {
    HWND hwnd = FindWindowW(NULL, NULL);
    while (hwnd != NULL) {
        DWORD found_pid;
        DWORD thread_id = GetWindowThreadProcessId(hwnd, &found_pid);
        if (found_pid == pid) {
            ShowWindow(hwnd, SW_RESTORE);
            return true;
        }
        hwnd = GetWindow(hwnd, GW_HWNDNEXT);
    }
    return false;

}
int main(int argc, char* argv[]) {
    if (strcmp(argv[1], "StealthInjection") == 0) {
        unsigned int pid = atoi(argv[3]);
        DWORD dwpid = static_cast<DWORD>(pid);
        char* dllpath = argv[2];
        HANDLE hProc = OpenProcess(PROCESS_ALL_ACCESS, FALSE, pid);
        std::ifstream File(dllpath, std::ios::binary | std::ios::ate);
        auto FileSize = File.tellg();
        BYTE* pSrcData = new BYTE[(UINT_PTR)FileSize];
        File.seekg(0, std::ios::beg);
        File.read((char*)(pSrcData), FileSize);
        File.close();
        if (!ManualMapDll(hProc, pSrcData, FileSize)) {
            delete[] pSrcData;
            CloseHandle(hProc);
            printf("Error while mapping.\n");
            return -8;
        } else {
            printf("OK.");
            return 0;
        }

    } else if (strcmp(argv[1], "Showconsole") == 0) {
        unsigned int pid = atoi(argv[2]);
        DWORD dwpid = static_cast<DWORD>(pid);
        if (Showconsole(pid)) {
            printf("OK.");
            return 0;
        }
        else {
            printf("NO.");
            return 4;
        }
    } else {
        char* dllpath = argv[1];
        unsigned int pid = atoi(argv[2]);
        DWORD dwpid = static_cast<DWORD>(pid);
        if (Inject(pid, dllpath)) {
            printf("OK.");
            return 0;
        }
        else {
            printf("NO.");
            return 4;
        }
    }
}
 
