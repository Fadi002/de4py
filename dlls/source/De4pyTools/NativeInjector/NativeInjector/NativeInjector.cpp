/*********************************************************************
      | De4py Injector : https://github.com/Fadi002/de4py  |
      |                  de4py project                     |
*********************************************************************/
#include <iostream>
#include <Windows.h>
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
    if (argc != 3) {
        return 4;
    }
    unsigned int pid = atoi(argv[2]);
    DWORD dwpid = static_cast<DWORD>(pid);
    if (strcmp(argv[1], "Showconsole") == 0) {
        if (Showconsole(pid)) {
            printf("OK.");
            return 0;
        }
        else {
            printf("NO.");
            return 4;
        }
    }
    char* dllpath = argv[1];
    if (Inject(pid, dllpath)) {
        printf("OK.");
        return 0;
    }
    else {
        printf("NO.");
        return 4;
    }
}
