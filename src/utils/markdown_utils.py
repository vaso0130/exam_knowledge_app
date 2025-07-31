import re

def format_code_blocks(text: str) -> str:
    """
    Detects code blocks in the given text, attempts to identify the language,
    and ensures proper Markdown formatting with syntax highlighting.
    """
    lines = text.splitlines()
    formatted_lines = []
    in_code_block = False
    code_block_content = []
    lang = ""

    for line in lines:
        if line.strip().startswith("```"):
            if in_code_block:
                # End of a code block
                if not lang:
                    # Attempt to guess language if not specified
                    lang = guess_programming_language("\n".join(code_block_content))
                formatted_lines.append(f"```{lang}")
                formatted_lines.extend(code_block_content)
                formatted_lines.append("```")
                code_block_content = []
                lang = ""
                in_code_block = False
            else:
                # Start of a code block
                match = re.match(r"```(\w+)?", line.strip())
                if match and match.group(1):
                    lang = match.group(1)
                in_code_block = True
        elif in_code_block:
            code_block_content.append(line)
        else:
            formatted_lines.append(line)

    # Handle case where code block might not be properly closed (e.g., at EOF)
    if in_code_block:
        if not lang:
            lang = guess_programming_language("\n".join(code_block_content))
        formatted_lines.append(f"```{lang}")
        formatted_lines.extend(code_block_content)
        formatted_lines.append("```")

    return "\n".join(formatted_lines)

def guess_programming_language(code: str) -> str:
    """
    Attempts to guess the programming language of a given code snippet.
    This is a very basic heuristic and can be expanded.
    """
    code = code.strip().lower()

    if not code:
        return ""

    # Python keywords
    if re.search(r"def |import |print\(|self\.", code):
        return "python"
    # C/C++ keywords
    if re.search(r"#include|<iostream>|int main\(|printf\(|std::cout", code):
        return "c"
    # Pseudocode indicators
    if re.search(r"algorithm|begin|end|read|write|if then else|for each|while do", code):
        return "pseudocode"
    # JavaScript keywords
    if re.search(r"function |const |let |var |console.log\(|document.getelementbyid", code):
        return "javascript"
    # Java keywords
    if re.search(r"public class |static void main|system.out.println", code):
        return "java"
    # SQL keywords
    if re.search(r"select |from |where |insert into |update |delete from", code):
        return "sql"
    # HTML indicators
    if re.search(r"<html|<body|<div|<p|<a href", code):
        return "html"
    # CSS indicators
    if re.search(r"body \{|\.class \{|#id \{|color:|font-size:", code):
        return "css"
    # PHP indicators
    if re.search(r"<?php|echo |$this->", code):
        return "php"
    # Ruby indicators
    if re.search(r"def |end |puts |require ", code):
        return "ruby"
    # Go indicators
    if re.search(r"package main|func main|fmt.println", code):
        return "go"
    # Swift indicators
    if re.search(r"import swift|func |var |let |print\(", code):
        return "swift"
    # Kotlin indicators
    if re.search(r"fun main|println\(|var |val |class ", code):
        return "kotlin"
    # Rust indicators
    if re.search(r"fn main|println!|let mut|struct ", code):
        return "rust"
    # Shell script indicators
    if re.search(r"#!/bin/bash|echo |if \[|for i in", code):
        return "bash"

    return "" # Default to no language if not recognized
