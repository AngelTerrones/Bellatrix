/*
 * Copyright (C) 2018 Angel Terrones <angelterrones@gmail.com>
 *
 * Permission to use, copy, modify, and/or distribute this software for any
 * purpose with or without fee is hereby granted, provided that the above
 * copyright notice and this permission notice appear in all copies.
 *
 * THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES
 * WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF
 * MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR
 * ANY SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES
 * WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN
 * ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF
 * OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.
 */

#include <stdio.h>
#include <string.h>
#include <unistd.h>
#include <stdint.h>
#include <errno.h>
#include <sys/stat.h>
#include "riscv.h"
//
#define MAX_CAUSE 16  // No more than 16 interrupt/exception sources.
// Code placement
#define UNIMP_FUNC(__f) ".globl " #__f "\n.type " #__f ", @function\n" #__f ":\n"
// Private variables.
extern volatile uint64_t tohost;
extern volatile uint64_t fromhost;
//
static TRAPFUNC _interrupt_handler[MAX_CAUSE];
static TRAPFUNC _exception_handler[MAX_CAUSE];

// -----------------------------------------------------------------------------
// for simulation purposes: write to tohost address.
void tohost_exit(uintptr_t code) {
        tohost = (code << 1) | 1;
        while(1);
        __builtin_unreachable();
}

// -----------------------------------------------------------------------------
// default exception handler
uintptr_t default_handler(uintptr_t epc, uintptr_t regs[32]){
        printf("[SYSCALL] Default handler. Abort...\n");
        tohost_exit(-1);
        __builtin_unreachable();
        return epc;
}

// C trap handler
uintptr_t handle_trap(uintptr_t cause, uintptr_t epc, uintptr_t regs[32])
{
        uintptr_t npc;
        if (cause & 0x80000000)
                npc = _interrupt_handler[cause & 0xF](epc, regs);
        else
                npc = _exception_handler[cause & 0xF](epc, regs);
        return npc;
}

// -----------------------------------------------------------------------------
// Syscalls: Taken from the picorv32 repository (with some modifications)
// Copyright (C) 2015  Clifford Wolf <clifford@clifford.at>

// read syscall. Does nothing for now.
// TODO: implement for input device
ssize_t _read(int file, void *ptr, size_t len) {
        return 0;
}

// write syscall.
ssize_t _write(int file, const void *ptr, size_t len) {
        volatile uint64_t magic_mem[8] __attribute__((aligned(64)));
        magic_mem[0] = 64;  // Magic number.
        magic_mem[1] = 1;
        magic_mem[2] = (uintptr_t)ptr;
        magic_mem[3] = len;
        //
        tohost = (uintptr_t)magic_mem;
        while (fromhost == 0)
                ;
        fromhost = 0;
        //
        __sync_synchronize();
        return 0;
}

// close syscall
ssize_t _close(int file) {
        return 0;
}

//
ssize_t _fstat(int file, struct stat *st) {
        errno = ENOENT;
        return -1;
}

//
void *_sbrk(ptrdiff_t incr) {
        extern unsigned char _end[]; // defined by the linker
        static unsigned long heap_end = 0;

        if (heap_end == 0)
                heap_end = (long)_end;
        heap_end += incr;
        return (void *)(heap_end - incr);
}

// exit syscall
void _exit(int code) {
        tohost_exit(code);
        __builtin_unreachable();
}

asm (
        ".section .text;"
        ".align 2;"
        UNIMP_FUNC(_open)
        UNIMP_FUNC(_openat)
        UNIMP_FUNC(_lseek)
        UNIMP_FUNC(_stat)
        UNIMP_FUNC(_lstat)
        UNIMP_FUNC(_fstatat)
        UNIMP_FUNC(_isatty)
        UNIMP_FUNC(_access)
        UNIMP_FUNC(_faccessat)
        UNIMP_FUNC(_link)
        UNIMP_FUNC(_unlink)
        UNIMP_FUNC(_execve)
        UNIMP_FUNC(_getpid)
        UNIMP_FUNC(_fork)
        UNIMP_FUNC(_kill)
        UNIMP_FUNC(_wait)
        UNIMP_FUNC(_times)
        UNIMP_FUNC(_gettimeofday)
        UNIMP_FUNC(_ftime)
        UNIMP_FUNC(_utime)
        UNIMP_FUNC(_chown)
        UNIMP_FUNC(_chmod)
        UNIMP_FUNC(_chdir)
        UNIMP_FUNC(_getcwd)
        UNIMP_FUNC(_sysconf)
        "j unimplemented_syscall;"
        );

void unimplemented_syscall() {
        printf("[SYSCALL] Unimplemented syscall! Abort()\n");
        _exit(-1);
        __builtin_unreachable();
}

// -----------------------------------------------------------------------------
// placeholder.
int __attribute__((weak)) main(int argc, char* argv[]){
        printf("[SYSCALL] Weak main: implement your own!\n");
        return -1;
}

// configure the call to main()
void _init() {
        // set default trap handlers
        int ii;
        for (ii = 0; ii < MAX_CAUSE; ii++) {
                _interrupt_handler[ii] = default_handler;
                _exception_handler[ii] = default_handler;
        }
        // call main
        int rcode = main(0, 0);
        _exit(rcode);
        __builtin_unreachable();
}

// -----------------------------------------------------------------------------
// User functions
// Add a interrupt handler.
void insert_ihandler(uint32_t cause, TRAPFUNC func) {
        cause = cause & 0xFF;
        if (cause >= MAX_CAUSE) {
                printf("[SYSCALL] Out of bounds CAUSE index.\n");
                return;
        }
        _interrupt_handler[cause] = func;
}

// Add a exception handler.
void insert_xhandler(uint32_t cause, TRAPFUNC func) {
        if (cause >= MAX_CAUSE) {
                printf("[SYSCALL] Out of bounds CAUSE index.\n");
                return;
        }
        _exception_handler[cause] = func;
}

// Enable global interrupts
void enable_interrupts(){
        asm("csrsi mstatus, 0x8;");
}

// Disable global interrupts
void disable_interrupts(){
        asm("csrci mstatus, 0x8;");
}

// Enable Software Interrupts
void enable_si(){
        asm("csrsi mie, 0x8;");
}

// Disable Software Interrupts
void disable_si(){
        asm("csrci mie, 0x8;");
}

// Enable Timer interrupts
void enable_ti(){
        asm("li t0, 0x80;");
        asm("csrs mie, t0;");
}

// Disable Timer Interrupts
void disable_ti(){
        asm("li t0, 0x80;");
        asm("csrc mie, t0;");
}

// Enable External Interrupts
void enable_ei(){
        asm("li t0, 0x800;");
        asm("csrs mie, t0;");
}

// Disable External Interrupts
void disable_ei(){
        asm("li t0, 0x800;");
        asm("csrc mie, t0;");
}
