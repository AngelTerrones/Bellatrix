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

#ifndef DEFINES_H
#define DEFINES_H

// -----------------------------------------------------------------------------
#if defined(__WIN32__) || defined(__MINGW32__)
#define mkdir(a, b) mkdir(a) /* mkdir command on Win32 does not support file permissions */
#endif
// -----------------------------------------------------------------------------
#define ANSI_COLOR_RED     "\x1b[31m"
#define ANSI_COLOR_GREEN   "\x1b[32m"
#define ANSI_COLOR_YELLOW  "\x1b[33m"
#define ANSI_COLOR_BLUE    "\x1b[34m"
#define ANSI_COLOR_MAGENTA "\x1b[35m"
#define ANSI_COLOR_CYAN    "\x1b[36m"
#define ANSI_COLOR_RESET   "\x1b[0m"
// -----------------------------------------------------------------------------
// Fixed parameters from TOP.v
#define TBFREQ   100e6
#define TBTS     1e-9
#define MEMSTART 0x80000000u    // Initial address
#define MEMSZ    0x01000000u    // size: 16 MB
// -----------------------------------------------------------------------------
// syscall (benchmarks)
#define SYSCALL  64
// For interrupt simulation
#define XINT_S   0x80002000u
#define XINT_T   0x80002004u
#define XINT_E   0x80002008u

#endif
