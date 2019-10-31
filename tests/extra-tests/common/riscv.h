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

// File: riscv.h

#ifndef RISCV_H
#define RISCV_H

// -----------------------------------------------------------------------------
// Constants
// exception cause values
#define X_INST_ADDRESS_MISA    0
#define X_INST_ACCESS_FAULT    1
#define X_ILLEGAL_INSTRUCTION  2
#define X_BREAKPOINT           3
#define X_LOAD_ADDRESS_MISA    4
#define X_LOAD_ACCESS_FAULT    5
#define X_STORE_ADDRESS_MISA   6
#define X_STORE_ACCESS_FAULT   7
#define X_UCALL                8
#define X_SCALL                9
#define X_MCALL                11
// interrupt cause values
#define I_USER_SW_INT          ((1 << 31) | 0)
#define I_SUPERVISOR_SW_INT    ((1 << 31) | 1)
#define I_MACHINE_SW_INT       ((1 << 31) | 3)
#define I_USER_TIMER_INT       ((1 << 31) | 4)
#define I_SUPERVISOR_TIMER_INT ((1 << 31) | 5)
#define I_MACHINE_TIMER_INT    ((1 << 31) | 7)
#define I_USER_X_INT           ((1 << 31) | 8)
#define I_SUPERVISOR_X_INT     ((1 << 31) | 9)
#define I_MACHINE_X_INT        ((1 << 31) | 11)

// -----------------------------------------------------------------------------
// typedef
typedef uintptr_t (*TRAPFUNC)(uintptr_t epc, uintptr_t regs[32]);

// -----------------------------------------------------------------------------
// Public functions
void insert_ihandler(uint32_t cause, TRAPFUNC func);
void insert_xhandler(uint32_t cause, TRAPFUNC func);
void enable_interrupts();
void disable_interrupts();
void enable_si();
void disable_si();
void enable_ti();
void disable_ti();
void enable_ei();
void disable_ei();

#endif
