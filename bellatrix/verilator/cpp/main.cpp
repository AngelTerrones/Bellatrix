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

#include <thread>
#include <sys/stat.h>
#include "coretb.h"
#include "defines.h"
#include "inputparser.h"

void printHelp() {
        printf("RISC-V CPU Verilator model.\n");
        printf("Using configuration file: " BCONFIG"\n");
        printf("Usage:\n");
        printf("\t" EXE ".exe --file <ELF file> [--timeout <max time>] [--signature <signature file>] [--trace]\n");
        printf("\t" EXE ".exe --help\n");
}

// -----------------------------------------------------------------------------
// Main
int main(int argc, char **argv) {
        INPUTPARSER input(argc, argv);
        const std::string &s_progfile  = input.GetCmdOption("--file");
        const std::string &s_timeout   = input.GetCmdOption("--timeout");
        const std::string &s_signature = input.GetCmdOption("--signature");
        const bool         trace       = input.CmdOptionExist("--trace");
        // help
        const bool         help        = input.CmdOptionExist("--help");
        //
        bool     badParams = false;
        uint32_t timeout   = 0;

        // ---------------------------------------------------------------------
        // process options
        if (s_progfile.empty())
                badParams = true;
        // check for help
        if (badParams || help) {
                printHelp();
                exit(EXIT_FAILURE);
        }
        printf("[MAIN] Using configuration file: " ANSI_COLOR_YELLOW BCONFIG "\n" ANSI_COLOR_RESET);
        if (s_timeout.empty()) {
                printf("[MAIN] Executing without time limit\n");
        } else {
                timeout = std::stoul(s_timeout);
        }
        // ---------------------------------------------------------------------
        CORETB *tb =new CORETB();
#ifdef DEBUG
        Verilated::scopesDump();
#endif
        const char* vcdFile = "build/trace_" EXE ".vcd";
        if (trace) {
                printf("[MAIN] Generate VCD file in build folder\n");
                tb->OpenTrace(vcdFile);
        }
        int exitCode = tb->SimulateCore(s_progfile, timeout, s_signature);
        tb->CloseTrace();
        delete tb;
        return exitCode;
}
// -----------------------------------------------------------------------------
