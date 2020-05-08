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

#include <cstdio>
#include <cstdlib>
#include <cstring>
#include "aelf.h"
#include "defines.h"
#include "Vtop__Dpi.h"

// -----------------------------------------------------------------------------
// DPI function
void ram_c_dpi_load(const svOpenArrayHandle mem_ptr, const char *filename) {
        ELFSECTION **section;
        uint8_t     *mem = static_cast<uint8_t *>(svGetArrayPtr(mem_ptr));
        if (not isELF(filename)) {
                fprintf(stderr, ANSI_COLOR_RED "[RAM] Invalid elf: %s\n" ANSI_COLOR_RESET, filename);
                exit(EXIT_FAILURE);
        }
        elfread(filename, section);
        for (int s = 0; section[s] != nullptr; s++){
                auto start = section[s]->m_start;
                auto end   = section[s]->m_start + section[s]->m_len;
                if (start >= MEMSTART && end < MEMSTART + MEMSZ) {
                        uint32_t offset = section[s]->m_start - MEMSTART;
                        std::memcpy(mem + offset, section[s]->m_data, section[s]->m_len);
                } else {
                        fprintf(stderr, ANSI_COLOR_YELLOW "[RAM] WARNING: unable to fit section %d. Start: 0x%08x, End: 0x%08x\n" ANSI_COLOR_RESET, s, start, end);
                }
        }
        delete [] section;
}
