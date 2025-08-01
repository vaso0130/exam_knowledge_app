import re
from typing import Dict, Any

def detect_and_fence_indented_code(text: str) -> str:
    """
    Detects indented code blocks (e.g., pseudocode) and wraps them in ```pseudocode fences.
    Looks for lines with >= 4 spaces or 1 tab indentation, and common pseudocode keywords.
    If the input is a single line, it attempts to infer newlines based on pseudocode structure.
    """
    original_lines = text.splitlines()
    
    # If it's a single line, try to infer newlines
    if len(original_lines) == 1 and original_lines[0].strip():
        single_line_text = original_lines[0].strip()
        # Simple heuristic to insert newlines for pseudocode
        # This is a basic attempt and might need refinement based on more examples
        single_line_text = re.sub(r'(function\s+.*?(?:returns\s+\w+)?)\s*', r'\1\n', single_line_text, flags=re.IGNORECASE)
        single_line_text = re.sub(r'(if\s+.*?then)\s*', r'\1\n', single_line_text, flags=re.IGNORECASE)
        single_line_text = re.sub(r'((\b(?:return|[a-z])\s*<-\s*.*?)|(\b(?:return)\s+.*?))\s*', r'\1\n', single_line_text, flags=re.IGNORECASE)
        
        # Remove any multiple newlines that might have been introduced
        single_line_text = re.sub(r'\n+', '\n', single_line_text).strip()
        lines = single_line_text.splitlines()
    else:
        lines = original_lines

    fenced_lines = []
    in_indented_block = False
    indent_level = 0

    for i, line in enumerate(lines):
        current_indent = len(re.match(r"^[ \t]*", line).group(0))
        stripped_line = line.strip()

        # Check for start of an indented block
        if not in_indented_block and current_indent >= 4 and stripped_line:
            # Look for common pseudocode keywords or if the previous line was also indented
            # or if it's the start of a new block after a blank line
            if (re.search(r"^(for|if|while|begin|function|procedure)\b", stripped_line, re.IGNORECASE) or
                (i > 0 and (len(re.match(r"^[ \t]*", lines[i-1]).group(0)) > 0 or not lines[i-1].strip()))):
                
                in_indented_block = True
                indent_level = current_indent
                fenced_lines.append("```pseudocode")
                fenced_lines.append(line)
            else:
                fenced_lines.append(line)
        # Continue indented block
        elif in_indented_block:
            if stripped_line and current_indent >= indent_level:
                fenced_lines.append(line)
            else:
                # End of indented block
                fenced_lines.append("```")
                in_indented_block = False
                indent_level = 0
                fenced_lines.append(line)
        else:
            fenced_lines.append(line)
    
    # Close any open indented block at the end of the text
    if in_indented_block:
        fenced_lines.append("```")

    return "\n".join(fenced_lines)

def format_code_blocks(text: str) -> str:

    """
    Detects code blocks in the given text, attempts to identify the language,
    and ensures proper Markdown formatting with syntax highlighting.
    """
    text = detect_and_fence_indented_code(text)
    def replace_code_block(match):
        lang_specifier = match.group(1)
        code_content = match.group(2)

        if lang_specifier:
            lang = lang_specifier
        else:
            lang = guess_programming_language(code_content)

        return f"""```{lang}
{code_content}```"""

    # Regex to find code blocks.
    # It captures the language specifier (optional) and then all content until the closing ```
    # The `re.DOTALL` flag allows '.' to match newlines.
    # We make the newline after the language specifier part of the content capture.
    pattern = r"```\s*(\w+)?\n([\s\S]*?)```"
    return re.sub(pattern, replace_code_block, text, flags=re.DOTALL)

def format_answer_text(text: str) -> str:
    """Clean and wrap answer content in a consistent Markdown block."""
    if not text:
        return ""

    cleaned = text.strip()

    # 嘗試解析 JSON 並取出 answer 欄位
    try:
        if cleaned.startswith('{'):
            import json
            obj = json.loads(cleaned)
            if isinstance(obj, dict) and 'answer' in obj:
                cleaned = str(obj['answer']).strip()
    except Exception:
        pass

    if not cleaned.startswith('###'):
        cleaned = f"### 參考答案\n\n{cleaned}"

    return cleaned

def guess_programming_language(code: str) -> str:
    """
    Attempts to guess the programming language of a given code snippet.
    This is a very basic heuristic and can be expanded.
    """
    code = code.strip().lower()

    if not code:
        return ""

    # Python keywords
    if re.search(r"def |import |print\(|self\.|elif |for |while |class |async |await ", code):
        return "python"
    # C/C++ keywords
    if re.search(r"#include|<iostream>|int main\(|printf\(|std::cout|void |class |struct |new |delete |nullptr ", code):
        return "c"
    # Pseudocode indicators
    if re.search(r"algorithm|begin|end|read|write|if then else|for each|while do|function |procedure |return ", code):
        return "pseudocode"
    # JavaScript keywords
    if re.search(r"function |const |let |var |console\.log\(|document\.getelementbyid|=> |async |await |import |export |class ", code):
        return "javascript"
    # Java keywords
    if re.search(r"public class |static void main|system\.out\.println|import |package |new |try |catch |finally ", code):
        return "java"
    # SQL keywords
    if re.search(r"select |from |where |insert into |update |delete from|create table |alter table |join |group by |order by ", code):
        return "sql"
    # HTML indicators
    if re.search(r"<html|<body|<div|<p|<a href|<script|<style|<head|<title ", code):
        return "html"
    # CSS indicators
    if re.search(r"body \{|\.class \{|#id \{|color:|font-size:|background-color:|display:|padding:|margin: ", code):
        return "css"
    # PHP indicators
    if re.search(r"<\?php|echo |\$this->|function |class |namespace |use |require |include ", code):
        return "php"
    # Ruby indicators
    if re.search(r"def |end |puts |require |class |module |do |if |unless ", code):
        return "ruby"
    # Go indicators
    if re.search(r"package main|func main|fmt\.println|import |var |const |type |struct |interface ", code):
        return "go"
    # Swift indicators
    if re.search(r"import swift|func |var |let |print\(|class |struct |enum |protocol ", code):
        return "swift"
    # Kotlin indicators
    if re.search(r"fun main|println\(|var |val |class |object |interface |import |package ", code):
        return "kotlin"
    # Rust indicators
    if re.search(r"fn main|println!|let mut|struct |enum |impl |trait |mod |use ", code):
        return "rust"
    # Shell script indicators
    if re.search(r"#!/bin/bash|echo |if \[|for i in|fi |esac |case |while |do |done ", code):
        return "bash"
    # JSON indicators
    if re.search(r"\{|\}|\[|\]|\"\\w+\": ", code):
        return "json"
    # XML indicators
    if re.search(r"<\?xml|<root>|<element attribute=\"value\"> ", code):
        return "xml"
    # Markdown indicators (basic)
    if re.search(r"^#+ |^- |^\* |^> |^``` ", code, re.MULTILINE):
        return "markdown"

    return "text" # Default to text if not recognized

def format_summary_to_markdown(summary_data: Dict[str, Any]) -> str:
    """
    將AI生成的摘要JSON數據轉換為結構化的Markdown格式。
    """
    markdown_output = []

    if not summary_data:
        return ""

    # 總結 (summary)
    if "summary" in summary_data and summary_data["summary"]:
        markdown_output.append(f"## 總結\n\n{summary_data["summary"]}\n")

    # 核心概念 (key_concepts)
    if "key_concepts" in summary_data and isinstance(summary_data["key_concepts"], list):
        if summary_data["key_concepts"]:
            markdown_output.append("## 核心概念\n")
            for concept in summary_data["key_concepts"]:
                if isinstance(concept, dict) and "name" in concept and "description" in concept:
                    markdown_output.append(f"- **{concept["name"]}**: {concept["description"]}")
                elif isinstance(concept, str):
                    markdown_output.append(f"- {concept}")
            markdown_output.append("") # Add a newline for spacing

    # 技術術語 (technical_terms)
    if "technical_terms" in summary_data and isinstance(summary_data["technical_terms"], list):
        if summary_data["technical_terms"]:
            markdown_output.append("## 技術術語\n")
            for term in summary_data["technical_terms"]:
                if isinstance(term, dict) and "name" in term and "description" in term:
                    markdown_output.append(f"- **{term["name"]}**: {term["description"]}")
                elif isinstance(term, str):
                    markdown_output.append(f"- {term}")
            markdown_output.append("")

    # 分類資訊 (classification_info)
    if "classification_info" in summary_data and isinstance(summary_data["classification_info"], list):
        if summary_data["classification_info"]:
            markdown_output.append("## 分類資訊\n")
            for info in summary_data["classification_info"]:
                if isinstance(info, dict) and "name" in info and "description" in info:
                    markdown_output.append(f"- **{info["name"]}**: {info["description"]}")
                elif isinstance(info, str):
                    markdown_output.append(f"- {info}")
            markdown_output.append("")

    # 實務應用 (practical_applications)
    if "practical_applications" in summary_data and isinstance(summary_data["practical_applications"], list):
        if summary_data["practical_applications"]:
            markdown_output.append("## 實務應用\n")
            for app in summary_data["practical_applications"]:
                if isinstance(app, dict) and "name" in app and "description" in app:
                    markdown_output.append(f"- **{app["name"]}**: {app["description"]}")
                elif isinstance(app, str):
                    markdown_output.append(f"- {app}")
            markdown_output.append("")

    # 條列式重點 (bullets)
    if "bullets" in summary_data and isinstance(summary_data["bullets"], list):
        if summary_data["bullets"]:
            markdown_output.append("## 條列式重點\n")
            for bullet in summary_data["bullets"]:
                markdown_output.append(f"- {bullet}")
            markdown_output.append("")

    return "\n".join(markdown_output).strip()
