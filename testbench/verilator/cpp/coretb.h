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

#ifndef CORETB_H
#define CORETB_H

#include <mutex>
#include "Vtop.h"
#include "testbench.h"

class CORETB: public Testbench<Vtop> {
public:
        CORETB();
        int SimulateCore(const std::string &progfile, const unsigned long max_time, const std::string &signature);
private:
        uint32_t PrintExitMessage (const bool ok, const unsigned long max_time);
        bool     CheckTOHOST      (bool &ok);
        void     SyscallPrint     (const uint32_t base_addr) const;
        void     LoadMemory       (const std::string &progfile);
        void     DumpSignature    (const std::string &signature);
        //
        uint32_t m_exitCode;
        uint32_t m_tohost;
        uint32_t m_fromhost;
        uint32_t m_begin_signature;
        uint32_t m_end_signature;
};

#endif
