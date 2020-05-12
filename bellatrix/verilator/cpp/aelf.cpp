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

// File: elf.cpp
// ELF loader for RISC-V ELF files

#include <cstdio>
#include <cstring>
#include <cstdlib>
#include <cassert>
#include <gelf.h>
#include <libelf.h>
#include <fcntl.h>
#include <unistd.h>
#include "aelf.h"

// for windows...
#ifndef O_BINARY
#define O_BINARY 0
#endif

// -----------------------------------------------------------------------------
// check if a file is a ELF file.
bool isELF(const char *filename) {
        FILE *fp;
        fp = fopen(filename, "rb");

        if (fp == nullptr) {
                perror("[OS]");
                return false;
        }
        if (fgetc(fp) != 0x7f) {fclose(fp); return false;}
        if (fgetc(fp) != 'E')  {fclose(fp); return false;}
        if (fgetc(fp) != 'L')  {fclose(fp); return false;}
        if (fgetc(fp) != 'F')  {fclose(fp); return false;}
        fclose(fp);

        return true;
}

// -----------------------------------------------------------------------------
// load the ELF file into a custom data structure.
void elfread(const char *filename, ELFSECTION **&sections) {
        // Initialize library
        if (elf_version(EV_CURRENT) == EV_NONE) {
                fprintf(stderr, "[ELFLOADER] ELF library initialization failed: %s\n", elf_errmsg(-1));
                perror("[OS]");
                exit(EXIT_FAILURE);
        }
        // open filename
        int fd = open(filename, O_RDONLY | O_BINARY, 0);
        if (fd < 0) {
                fprintf(stderr, "[ELFLOADER] Unable to open file: %s\n", filename);
                perror("[OS]");
                exit(EXIT_FAILURE);
        }
        Elf *elf = elf_begin(fd, ELF_C_READ, nullptr);
        if (elf == nullptr) {
                fprintf(stderr, "[ELFLOADER] elf_begin(): %s\n", elf_errmsg(-1));
                exit(EXIT_FAILURE);
        }
        // Check ELF type
        Elf_Kind ek = elf_kind(elf);
        switch (ek) {
        case ELF_K_AR:
                fprintf(stderr, "[ELFLOADER] AR archive. Abort\n");
                exit(EXIT_FAILURE);
        case ELF_K_ELF:
                // OK, continue.
                break;
        case ELF_K_NONE:
                fprintf(stderr, "[ELFLOADER] ELF data ???\n");
                break;
        default:
                fprintf(stderr, "[ELFLOADER] Unknown file. Abort\n");
                exit(EXIT_FAILURE);
        }
        // Get ELF executable header
        GElf_Ehdr ehdr;
        if (gelf_getehdr(elf, &ehdr) == nullptr) {
                fprintf(stderr, "[ELFLOADER] getehdr() failed: %s\n", elf_errmsg(-1));
                exit(EXIT_FAILURE);
        }
        // check ELF class
        int elfclass = gelf_getclass(elf);
        if (elfclass == ELFCLASSNONE) {
                fprintf(stderr, "[ELFLOADER] getclass() failed: %s\n", elf_errmsg(-1));
                exit(EXIT_FAILURE);
        }
        if (elfclass != ELFCLASS32) {
                fprintf(stderr, "[ELFLOADER] 64-bit ELF file. Unsupported file. Abort.\n");
                exit(EXIT_FAILURE);
        }
        // get indent
        char *id = elf_getident(elf, nullptr);
        if (id == nullptr) {
                fprintf(stderr, "[ELFLOADER] getident() failed: %s\n", elf_errmsg(-1));
                exit(EXIT_FAILURE);
        }
#ifdef DEBUG
        printf("--------------------------------------------------------------------------------\n");
        printf("Executable header:\n");
        printf("   %-20s 0x%jx\n", "e_type",      (uintmax_t)ehdr.e_type);
        printf("   %-20s 0x%jx\n", "e_machine",   (uintmax_t)ehdr.e_machine);
        printf("   %-20s 0x%jx\n", "e_version",   (uintmax_t)ehdr.e_version);
        printf("   %-20s 0x%jx\n", "e_entry",     (uintmax_t)ehdr.e_entry);
        printf("   %-20s 0x%jx\n", "e_phoff",     (uintmax_t)ehdr.e_phoff);
        printf("   %-20s 0x%jx\n", "e_shoff",     (uintmax_t)ehdr.e_shoff);
        printf("   %-20s 0x%jx\n", "e_flags",     (uintmax_t)ehdr.e_flags);
        printf("   %-20s 0x%jx\n", "e_ehsize",    (uintmax_t)ehdr.e_ehsize);
        printf("   %-20s 0x%jx\n", "e_phentsize", (uintmax_t)ehdr.e_phentsize);
        printf("   %-20s 0x%jx\n", "e_shentsize", (uintmax_t)ehdr.e_shentsize);
#endif
        // check for a RISC-V ELF file (EM_RISCV == 243)
        if (ehdr.e_machine != 243) {
                fprintf(stderr, "[ELFLOADER] This is not a RISC-V ELF file: 0x%jx(%d)\n", (uintmax_t)ehdr.e_machine, ehdr.e_machine);
                exit(EXIT_FAILURE);
        }
        // get executable header
        size_t n;
        if (elf_getphdrnum(elf, &n) != 0) {
                fprintf(stderr, "[ELFLOADER] elf_getphdrnum() failed: %s\n", elf_errmsg(-1));
                exit(EXIT_FAILURE);
        }
        assert(n != 0);
        // program headers
        size_t total_bytes = 0;
        GElf_Phdr phdr;
#ifdef DEBUG
        printf("--------------------------------------------------------------------------------\n");
        printf("Section headers:\n");
#endif
        // read program header
        for (size_t i = 0; i < n; i++) {
                if (gelf_getphdr(elf, i, &phdr) != &phdr) {
                        fprintf(stderr, "[ELFLOADER] getphdr() failed: %s\n", elf_errmsg(-1));
                        exit(EXIT_FAILURE);
                }
#ifdef DEBUG
                printf("\n   Section %zu:\n", i);
                printf("   ----------\n");
                printf("   %-20s 0x%jx\n", "p_type",   (uintmax_t)phdr.p_type);
                printf("   %-20s 0x%jx\n", "p_offset", (uintmax_t)phdr.p_offset);
                printf("   %-20s 0x%jx\n", "p_vaddr",  (uintmax_t)phdr.p_vaddr);
                printf("   %-20s 0x%jx\n", "p_paddr",  (uintmax_t)phdr.p_paddr);
                printf("   %-20s 0x%jx\n", "p_filesz", (uintmax_t)phdr.p_filesz);
                printf("   %-20s 0x%jx\n", "p_memsz",  (uintmax_t)phdr.p_memsz);
                printf("   %-20s 0x%jx [", "p_flags",  (uintmax_t)phdr.p_flags);
                if (phdr.p_flags & PF_X) printf(" EX ");
                if (phdr.p_flags & PF_R) printf(" RD ");
                if (phdr.p_flags & PF_W) printf(" WR ");
                printf("]\n");
                printf("   %-20s 0x%jx\n", "p_align", (uintmax_t)phdr.p_align);
#endif
                total_bytes += sizeof(ELFSECTION *) + sizeof(ELFSECTION) + phdr.p_memsz;
        }
#ifdef DEBUG
        printf("--------------------------------------------------------------------------------\n");
#endif
        // reserve memory for a linked list (!?)
        char *data = new char[total_bytes + sizeof(ELFSECTION *)];
        memset(data, 0, total_bytes);

        // set the initial pointer
        sections              = (ELFSECTION **)data;
        size_t current_offset = (n + 1) * sizeof(ELFSECTION *);
        for (size_t i = 0; i < n; i++) {
                if (gelf_getphdr(elf, i, &phdr) != &phdr) {
                        fprintf(stderr, "[ELFLOADER] getphdr() failed: %s\n", elf_errmsg(-1));
                        exit(EXIT_FAILURE);
                }
                sections[i]          = (ELFSECTION *)(&data[current_offset]);
                sections[i]->m_start = phdr.p_paddr;
                sections[i]->m_len   = phdr.p_filesz;
                // read/copy section
                if (lseek(fd, phdr.p_offset, SEEK_SET) < 0) {
                        fprintf(stderr, "[ELFLOADER] Unable to seek file position 0x%08jx\n", (uintmax_t)phdr.p_offset);
                        perror("[OS]");
                        exit(EXIT_FAILURE);
                }
                if (phdr.p_filesz > phdr.p_memsz) {
                        fprintf(stderr, "[ELFLOADER][WARNING] filesz > p_memsz. Ignoring section %zu.\n", i);
                        phdr.p_filesz = 0;
                }
                if (read(fd, sections[i]->m_data, phdr.p_filesz) != (int)phdr.p_filesz) {
                        fprintf(stderr, "[ELFLOADER] Unable to read the entire section: %zu.\n", i);
                        perror("[OS]");
                        exit(EXIT_FAILURE);
                }
                current_offset += phdr.p_memsz + sizeof(ELFSECTION);
        }
        // final pointer. Invalid data.
        sections[n] = nullptr;
        // nuke
        elf_end(elf);
        close(fd);
}

uint32_t getSymbol (const char *filename, const char *symbolName) {
        // Initialize library
        if (elf_version(EV_CURRENT) == EV_NONE) {
                fprintf(stderr, "[ELFLOADER] ELF library initialization failed: %s\n", elf_errmsg(-1));
                perror("[OS]");
                exit(EXIT_FAILURE);
        }
        // open filename
        int fd = open(filename, O_RDONLY | O_BINARY, 0);
        if (fd < 0) {
                fprintf(stderr, "[ELFLOADER] Unable to open file: %s\n", filename);
                perror("[OS]");
                exit(EXIT_FAILURE);
        }
        Elf *elf = elf_begin(fd, ELF_C_READ, nullptr);
        if (elf == nullptr) {
                fprintf(stderr, "[ELFLOADER] elf_begin(): %s\n", elf_errmsg(-1));
                exit(EXIT_FAILURE);
        }
        // Check ELF type
        Elf_Kind ek = elf_kind(elf);
        if (ek != ELF_K_ELF) {
                fprintf(stderr, "[ELFLOADER] Not an ELF object. Abort\n");
                exit(EXIT_FAILURE);
        }
        // get section list
        Elf_Scn *scn = NULL;
        GElf_Shdr shdr;
        char *name;
        while ((scn = elf_nextscn(elf, scn)) != NULL) {
                gelf_getshdr(scn, &shdr);
                if (shdr.sh_type == SHT_SYMTAB) {
                        Elf_Data *edata = elf_getdata(scn, NULL);
                        uint32_t symbolCount = shdr.sh_size / shdr.sh_entsize;
                        GElf_Sym sym;
                        for (uint32_t ii = 0; ii < symbolCount; ii++) {
                                gelf_getsym(edata, ii, &sym);
                                name = elf_strptr(elf, shdr.sh_link, sym.st_name);
                                if (std::strcmp(symbolName, name) == 0) {
                                        // printf("Symbol found: 0x%jx\n", sym.st_value);
                                        elf_end(elf);
                                        close(fd);
                                        return sym.st_value;
                                }
                        }
                }
        }
        // FAILURE: return -1
        fprintf(stderr, "[ELFLOADER] Symbol %s does not exists.\n", elf_errmsg(-1));
        elf_end(elf);
        close(fd);
        return -1;
}
