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

#ifndef INPUTPARSER_H
#define INPUTPARSER_H

#include <algorithm>

//  from https://stackoverflow.com/questions/865668/how-to-parse-command-line-arguments-in-c
//  author: iain
class INPUTPARSER {
public:
        INPUTPARSER(int &argc, char **argv) {
                for (int ii = 0; ii < argc; ii++)
                        m_tokens.push_back(std::string(argv[ii]));
        }
        const std::string &GetCmdOption(const std::string &option) const {
                std::vector<std::string>::const_iterator itr;
                itr = std::find(m_tokens.begin(), m_tokens.end(), option);
                if (itr != m_tokens.end() && ++itr != m_tokens.end())
                        return *itr;
                static const std::string empty("");
                return empty;
        }
        bool CmdOptionExist(const std::string &option) const {
                return std::find(m_tokens.begin(), m_tokens.end(), option) != m_tokens.end();
        }
private:
        std::vector<std::string> m_tokens;
};

#endif
